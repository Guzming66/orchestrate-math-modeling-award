#!/usr/bin/env python3
"""Audit paper seams that deterministic checks can locate without guessing authorship."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from build_latex import INTERNAL_PAPER_PATTERNS, strip_tex_comments
from evidence_utils import artifact_errors, split_ids
from latex_sources import loaded_tex_sources


CHAT_LABELS = {
    "chat-assistant self-reference", "chat-assistant request reference", "chat-assistant closing phrase",
    "tool or chat transcript residue", "unresolved citation placeholder", "Markdown code fence leaked into LaTeX source",
}
CHAT_PATTERNS = tuple(
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in INTERNAL_PAPER_PATTERNS if label in CHAT_LABELS
)
CONTROL_META_PATTERNS = (
    (re.compile(r"(?:总控|控制层)(?:验收|审核|门禁|结论|记录)"), "control-plane review language"),
    (re.compile(r"(?:工作流|流程)(?:阶段|状态).{0,8}(?:已|为)(?:完成|通过|冻结|提交)"), "workflow-state language"),
    (re.compile(r"(?:上游|下游)(?:接口|结果).{0,8}(?:冻结|验收|放行)"), "internal interface-state language"),
    (re.compile(r"(?:审计|复现|证据)(?:台账|状态).{0,8}(?:完成|通过|闭合)"), "internal audit-state language"),
    (re.compile(r"(?:本小问|本问题|该模型|该结果).{0,12}(?:具备|达到)(?:交付|提交)(?:条件|资格)"), "internal handoff language"),
    (re.compile(r"跨问题一致性核对"), "control-plane cross-question audit heading"),
    (re.compile(r"最短充分验证"), "internal evidence-budget terminology"),
    (re.compile(r"向后续(?:问题|小问)传递"), "internal downstream-transfer terminology"),
    (re.compile(r"本问没有规定必须.{0,16}(?:传递|输出|沿用)"), "internal question-contract commentary"),
)
CJK_REPEAT = re.compile(r"(?P<phrase>[\u3400-\u9fff]{2,8})(?P=phrase)")
# Repeated two-character idioms can be intentional; keep the allowlist narrow.
CJK_REPEAT_ALLOWLIST = {"人人", "年年", "天天", "时时", "处处", "事事", "层层", "步步"}
VAGUE_SENTENCES = (
    re.compile(r"(?:结果|效果|性能)(?:较为|非常|十分)?(?:良好|优秀|理想)"),
    re.compile(r"精度(?:较高|很高|显著提高)"),
    re.compile(r"具有(?:较强|良好)的(?:鲁棒性|稳健性|普适性|适用性)"),
)
DERIVATION_JUMPS = re.compile(r"(?:显然|容易得到|简单变换后|由此可得|经过变换可得)[，,:：]?")
EQUATION_SIGNAL = re.compile(r"\\begin\{(?:equation|align|gather|multline)\*?\}|\\\[|\$\$")
HEADING = re.compile(r"\\(?:sub)*section\*?\{([^{}]+)\}")
LATEX_COMMAND = re.compile(r"\\(?:cite|ref|eqref|autoref|cref|Cref|label|includegraphics|input|begin|end)(?:\[[^\]]*\])?\{[^{}]*\}")
MATH_BLOCK = re.compile(r"\\begin\{(?:equation|align|gather|multline|table|figure|lstlisting)\*?\}.*?\\end\{(?:equation|align|gather|multline|table|figure|lstlisting)\*?\}", re.DOTALL)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def paper_sources(workspace: Path) -> list[Path]:
    paper = workspace / "paper"
    sources = loaded_tex_sources(paper)
    if not sources and paper.is_dir():
        sources = [
            path for path in paper.rglob("*.tex")
            if "build" not in path.relative_to(paper).parts
        ]
    return [path for path in sources if path.name != "ai_usage_details.tex"]


def visible_text(path: Path) -> str:
    return strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))


def prose(text: str) -> str:
    text = MATH_BLOCK.sub(" ", text)
    text = LATEX_COMMAND.sub(" ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}$&_^~#%]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def adjacent_cjk_repetitions(text: str) -> list[str]:
    """Return high-confidence adjacent repeated Chinese phrases."""
    return sorted(
        {
            match.group("phrase")
            for match in CJK_REPEAT.finditer(prose(text))
            if match.group("phrase") not in CJK_REPEAT_ALLOWLIST
        }
    )


def validate_traceability(workspace: Path) -> list[str]:
    errors: list[str] = []
    rows = read_csv(workspace / "synthesis" / "implementation_trace.csv")
    code_suffixes = {".py", ".m", ".r", ".jl", ".c", ".cc", ".cpp", ".java", ".ipynb", ".xlsx", ".xlsm"}
    implementation_files = [
        path
        for folder in (workspace / "support", workspace / "branches")
        if folder.is_dir()
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in code_suffixes
    ]
    if not rows:
        return ["implementation_trace.csv has no equation/code/result mappings"] if implementation_files else []
    seen: set[str] = set()
    result_ids = {row.get("result_id", "").strip() for row in read_csv(workspace / "synthesis" / "result_manifest.csv")}
    source_text = "\n".join(visible_text(path) for path in paper_sources(workspace))
    for index, row in enumerate(rows, start=2):
        trace_id = row.get("trace_id", "").strip() or f"trace row {index}"
        if trace_id in seen:
            errors.append(f"duplicate implementation trace_id: {trace_id}")
        seen.add(trace_id)
        for field in ("question_id", "paper_section", "equation_or_claim_anchor", "mathematical_role", "implementation_path", "implementation_symbol", "test_artifact_path", "test_sha256", "test_command", "result_ids", "reviewer", "checked_at"):
            if not row.get(field, "").strip():
                errors.append(f"{trace_id}: {field} is empty")
        section_rel = row.get("paper_section", "").replace("\\", "/").strip()
        try:
            section = (workspace / section_rel).resolve()
            section.relative_to(workspace)
        except ValueError:
            errors.append(f"{trace_id}: paper_section escapes workspace")
        else:
            if not section.is_file():
                errors.append(f"{trace_id}: paper_section is missing")
            else:
                anchor = row.get("equation_or_claim_anchor", "").strip()
                if anchor and anchor not in visible_text(section):
                    errors.append(f"{trace_id}: equation_or_claim_anchor is absent from paper_section")
        implementation_rel = row.get("implementation_path", "").replace("\\", "/").strip()
        try:
            implementation = (workspace / implementation_rel).resolve()
            implementation.relative_to(workspace)
        except ValueError:
            errors.append(f"{trace_id}: implementation_path escapes workspace")
        else:
            if not implementation.is_file():
                errors.append(f"{trace_id}: implementation file is missing")
            elif row.get("implementation_symbol", "").strip() not in implementation.read_text(encoding="utf-8", errors="replace"):
                errors.append(f"{trace_id}: implementation_symbol is absent from implementation file")
        errors.extend(artifact_errors(workspace, row, trace_id, path_field="test_artifact_path", sha_field="test_sha256", check_field="test_command"))
        for result_id in split_ids(row.get("result_ids", "")):
            if result_id not in result_ids:
                errors.append(f"{trace_id}: unknown result_id {result_id}")
        if row.get("equation_or_claim_anchor", "").strip() and row.get("equation_or_claim_anchor", "").strip() not in source_text:
            errors.append(f"{trace_id}: anchor is absent from final paper sources")
    return errors


def validate_paper_integrity(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    sources = paper_sources(workspace)
    question_sources = [path for path in sources if re.fullmatch(r"q\d+\.tex", path.name, re.IGNORECASE)]
    for path in sources:
        text = visible_text(path)
        rel = path.relative_to(workspace).as_posix()
        for pattern, label in CHAT_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: {label}")
        for pattern, label in CONTROL_META_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: {label}")
        for phrase in adjacent_cjk_repetitions(text):
            errors.append(f"{rel}: adjacent repeated Chinese phrase '{phrase}{phrase}'")
        clean = prose(text)
        for sentence in re.split(r"[。！？!?]", clean):
            if len(sentence.strip()) < 8:
                continue
            if any(pattern.search(sentence) for pattern in VAGUE_SENTENCES) and not re.search(r"\d|%|误差|区间|相比|边界", sentence):
                warnings.append(f"{rel}: vague evaluation without a local metric or boundary: {sentence.strip()[:100]}")
        for match in DERIVATION_JUMPS.finditer(text):
            window = text[match.end():match.end() + 180]
            if EQUATION_SIGNAL.search(window):
                warnings.append(f"{rel}: possible derivation jump before displayed mathematics near '{match.group(0)}'")

    signatures: dict[tuple[str, ...], list[str]] = {}
    for path in question_sources:
        headings = tuple(re.sub(r"\s+", "", item) for item in HEADING.findall(visible_text(path)))
        if len(headings) >= 3:
            signatures.setdefault(headings, []).append(path.relative_to(workspace).as_posix())
    for headings, paths in signatures.items():
        if len(paths) >= 2:
            warnings.append(f"question sections repeat an identical heading template {headings}: {', '.join(paths)}")

    first_paragraphs: list[tuple[str, str]] = []
    for path in question_sources:
        text = HEADING.sub("\n", visible_text(path))
        paragraphs = [re.sub(r"\s+", "", prose(item)) for item in re.split(r"\n\s*\n", text) if len(prose(item)) >= 30]
        if paragraphs:
            first_paragraphs.append((path.relative_to(workspace).as_posix(), paragraphs[0][:28]))
    stems = Counter(stem for _, stem in first_paragraphs)
    for stem, count in stems.items():
        if count >= 2:
            paths = [path for path, item in first_paragraphs if item == stem]
            warnings.append(f"question openings repeat the same prose stem in {', '.join(paths)}: {stem}")

    errors.extend(validate_traceability(workspace))
    report = {
        "status": "pass" if not errors else "block",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(sources),
        "question_source_count": len(question_sources),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "integrity" / "paper_integrity_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit paper seams and equation-code-result traceability.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_paper_integrity(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
