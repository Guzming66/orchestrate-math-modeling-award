#!/usr/bin/env python3
"""Build a direct-LaTeX contest paper and fail closed on submission defects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ENGINE_BY_COMPETITION = {
    "CUMCM": "xelatex",
    "MCM": "pdflatex",
    "ICM": "pdflatex",
}
PLACEHOLDERS = ("DRAFT TITLE", "DRAFT KEYWORDS", "DRAFT CONTENT", "0000000")
PLACEHOLDER_PATTERNS = (
    *( (re.escape(value), value) for value in PLACEHOLDERS ),
    (r"\b(?:TODO|TBD|PLACEHOLDER)\b", "generic TODO/TBD/PLACEHOLDER marker"),
    (r"(?:待补充|待填写|待完善|待完成|此处填写|示例内容)", "unfinished Chinese placeholder marker"),
    (r"\bLorem\s+ipsum\b", "Lorem ipsum placeholder text"),
)
INTERNAL_PAPER_PATTERNS = (
    (r"\bartifact_path\b", "internal evidence field artifact_path"),
    (r"\bsha256\b", "internal SHA-256 field"),
    (r"\bworkflow_stage\b", "internal workflow stage"),
    (r"\bcommand_or_check\b", "internal verification command field"),
    (r"\bverification_command\b", "internal verification command field"),
    (r"\bchecked_at\b", "internal evidence timestamp field"),
    (r"\breview_type\b", "internal review field"),
    (r"\bfinding_id\b", "internal review finding field"),
    (r"\btask_board\b", "internal task board"),
    (r"\bdecision_log\b", "internal decision log"),
    (r"\bmodel_selection\.json\b", "internal model-selection file"),
    (r"\binnovation_claims\.csv\b", "internal innovation ledger"),
    (r"\bresult_manifest\.csv\b", "internal result manifest"),
    (r"\bfinal_report\.json\b", "internal final report"),
    (r"\baudits[\\/]", "internal audits path"),
    (r"\bbranches[\\/]", "internal branch path"),
    (r"\bsynthesis[\\/]", "internal synthesis path"),
    (r"\b(?:model|paper)[_-]?freeze\b", "internal freeze terminology"),
    (r"\bdownstream interface\b", "internal downstream-interface terminology"),
    (r"\bartifact[- ]backed\b", "internal artifact terminology"),
    (r"\breview findings?\b", "internal review terminology"),
    (r"\bno innovation claim\b", "negative innovation meta-statement"),
    (r"\bstrong baseline\b", "internal strong-baseline terminology"),
    (r"\bbaseline failure\b", "internal baseline-failure terminology"),
    (r"\bmateriality threshold\b", "internal materiality terminology"),
    (r"强基线", "internal strong-baseline terminology"),
    (r"基线失败", "internal baseline-failure terminology"),
    (r"最小(?:必要|充分)改变(?:原则)?", "internal minimal-change workflow terminology"),
    (r"创新主张(?:卡|组合|台账|晋级)?", "internal innovation-claim workflow terminology"),
    (r"(?:Critic|Jury|Scout)\s*(?:Agent)?", "internal agent-role terminology"),
    (r"(?:论文表达|presentation)\s*(?:防火墙|firewall)", "internal presentation-firewall terminology"),
    (r"评委可见验证", "internal judge-visible-validation terminology"),
    (r"材料性(?:阈值|标准)", "internal materiality terminology"),
    (r"(?:问题|Q\s*\d+).{0,8}(?:验收|冻结)", "question acceptance/freeze terminology"),
    (r"冻结的?下游接口", "internal downstream-interface terminology"),
    (r"不(?:虚构|构造).{0,12}(?:置信区间|可信区间)", "negative statistical meta-statement"),
    (r"不提出创新主张", "negative innovation meta-statement"),
    (r"代码.{0,8}(?:哈希|hash)", "internal code-hash terminology"),
    (r"作为(?:一个)?(?:人工智能|AI|语言模型)", "chat-assistant self-reference"),
    (r"根据(?:您|用户)的(?:要求|提示)", "chat-assistant request reference"),
    (r"希望(?:以上|这些)(?:内容|回答).{0,16}(?:帮助|有用)", "chat-assistant closing phrase"),
    (r"(?:turn\d+(?:search|view|fetch)\d+|cite\b|:codex-annotation|::(?:code-comment|created-thread))", "tool or chat transcript residue"),
    (r"\[citation needed\]", "unresolved citation placeholder"),
    (r"```", "Markdown code fence leaked into LaTeX source"),
)
LEAN_PAPER_WARNINGS = (
    (r"\\section\*?\{问题重述\}", "standalone problem restatement is usually redundant"),
    (r"\\section\*?\{符号(?:说明|约定)\}", "standalone notation section should be kept only when symbols are dense and reused"),
    (r"\\section\*?\{模型(?:评价|评估)(?:与推广)?\}", "generic evaluation section should be evidence-specific"),
    (r"\\section\*?\{模型推广\}", "generic extension section should state a concrete transfer condition"),
    (r"\\section\*?\{(?:模型)?优点(?:与|和)缺点\}", "generic strengths/weaknesses list should be replaced with concrete limits"),
    (r"\\section\*?\{创新点\}", "standalone innovation slogan section should be mapped to evidence in context"),
    (r"结果(?:较为)?良好", "replace vague result quality with a metric or boundary"),
    (r"精度较高", "replace vague accuracy with a metric or interval"),
    (r"大大提高", "replace promotional language with a measured comparison"),
    (r"显而易见", "state the derivation or observable evidence"),
    (r"充分证明", "calibrate proof language to the available evidence"),
    (r"具有(?:重要|较大)的(?:现实|实际|应用)意义", "replace generic significance with the decision or use enabled by the result"),
    (r"从图中可以(?:很|明显地?|清楚地?)?(?:看出|发现)", "state the visible comparison, direction and condition"),
    (r"(?:创新性地|创造性地)(?:提出|引入|建立|使用)", "state the problem-specific change and its evidence instead of self-awarding novelty"),
    (r"(?:能够|可以)更好地(?:解决|描述|反映|刻画)", "name the failure resolved or the measured improvement"),
    (r"具有(?:较强|良好)的(?:鲁棒性|稳健性|普适性|适用性)", "replace generic robustness/applicability with a tested boundary"),
    (r"验证了模型的(?:正确性|准确性|有效性)", "name the validation target, metric and observed result"),
    (r"保守裁决", "state the adopted modeling criterion and its consequence directly"),
    (r"语义敏感性基线", "use a contest-native criterion comparison instead of internal terminology"),
    (r"(?:独立复算|区间算术|单调性证书).{0,16}(?:一致|通过|确认)", "show the compared configuration, discrepancy or boundary in the paper"),
)
BLOCKING_LOG_PATTERNS = (
    (r"^! LaTeX Error:", "LaTeX error"),
    (r"Undefined control sequence", "undefined control sequence"),
    (r"Emergency stop", "TeX emergency stop"),
    (r"Fatal error", "fatal TeX error"),
    (r"LaTeX Warning: Citation .+ undefined", "undefined citation"),
    (r"LaTeX Warning: Reference .+ undefined", "undefined reference"),
    (r"There were undefined references", "undefined references remain"),
    (r"Label\(s\) may have changed.*Rerun", "cross-references need another run"),
)
QUESTION_STANDALONE_PATTERN = re.compile(r"^q(?P<number>\d+)_standalone\.tex$", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{(?P<title>[^{}]+)\}")
QUESTION_DUTIES = {
    "task": re.compile(r"任务|问题分析|建模准备|判定|目标"),
    "model": re.compile(r"模型|方法|推导|算法|求解"),
    "result": re.compile(r"结果|结论|方案|回答"),
    "validation": re.compile(r"验证|检验|敏感|误差|稳健|边界|复核"),
}
COMPARATIVE_VALIDATION_PATTERN = re.compile(
    r"加密|步长|收敛|复算|枚举|敏感性|扰动|对照|比较|消融|网格|不同配置"
)
VISIBLE_EVIDENCE_PATTERN = re.compile(
    r"\\begin\{(?:table|figure|tabular)\}|\\input\{[^{}]*(?:table|figure)[^{}]*\}",
    re.IGNORECASE,
)


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def latex_environment(paper_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["TEXINPUTS"] = str(paper_dir) + os.pathsep + environment.get("TEXINPUTS", "")
    environment["BIBINPUTS"] = str(paper_dir) + os.pathsep + environment.get("BIBINPUTS", "")
    environment["SOURCE_DATE_EPOCH"] = "946684800"
    environment["FORCE_SOURCE_DATE"] = "1"
    return environment


def fallback_build(paper_dir: Path, main: Path, engine: str, build_dir: Path) -> subprocess.CompletedProcess[str]:
    environment = latex_environment(paper_dir)
    command = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-output-directory={build_dir}",
        main.name,
    ]
    outputs: list[str] = []
    result = run(command, paper_dir, environment)
    outputs.append(result.stdout)
    if result.returncode != 0:
        result.stdout = "\n".join(outputs)
        return result

    aux_path = build_dir / f"{main.stem}.aux"
    if aux_path.exists() and "\\bibdata" in aux_path.read_text(encoding="utf-8", errors="replace"):
        bibtex = shutil.which("bibtex")
        if not bibtex:
            return subprocess.CompletedProcess(command, 1, "\n".join(outputs) + "\nbibtex is missing")
        bib_result = run([bibtex, str(build_dir / main.stem)], paper_dir, environment)
        outputs.append(bib_result.stdout)
        if bib_result.returncode != 0:
            bib_result.stdout = "\n".join(outputs)
            return bib_result

    for _ in range(2):
        result = run(command, paper_dir, environment)
        outputs.append(result.stdout)
        if result.returncode != 0:
            break
    result.stdout = "\n".join(outputs)
    return result


def compile_paper(paper_dir: Path, main: Path, engine: str, build_dir: Path) -> subprocess.CompletedProcess[str]:
    latexmk = shutil.which("latexmk")
    if latexmk:
        engine_flag = {"xelatex": "-xelatex", "lualatex": "-lualatex", "pdflatex": "-pdf"}[engine]
        return run(
            [
                latexmk,
                engine_flag,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={build_dir}",
                main.name,
            ],
            paper_dir,
            latex_environment(paper_dir),
        )
    return fallback_build(paper_dir, main, engine, build_dir)


def strip_tex_comments(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        index = 0
        while True:
            marker = line.find("%", index)
            if marker < 0:
                cleaned.append(line)
                break
            backslashes = 0
            cursor = marker - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cleaned.append(line[:marker])
                break
            index = marker + 1
    return "\n".join(cleaned)


def find_placeholders(text: str) -> list[str]:
    return sorted(
        {
            label
            for pattern, label in PLACEHOLDER_PATTERNS
            if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        }
    )


def classify_artifact(main_path: Path) -> str:
    if main_path.name == "main.tex":
        return "full_paper"
    if QUESTION_STANDALONE_PATTERN.fullmatch(main_path.name):
        return "question_standalone"
    return "auxiliary"


def audit_question_standalone(
    paper_dir: Path, main_path: Path, mode: str
) -> tuple[dict[str, object], list[str], list[str]]:
    match = QUESTION_STANDALONE_PATTERN.fullmatch(main_path.name)
    if not match:
        return {}, [], []

    number = match.group("number")
    names = [f"q{number}.tex", f"q{int(number):02d}.tex"]
    section_path: Path | None = None
    for name in dict.fromkeys(names):
        candidate = paper_dir / "sections" / "questions" / name
        if candidate.is_file():
            section_path = candidate
            break
    errors: list[str] = []
    warnings: list[str] = []
    target = errors if mode == "submission" else warnings
    duties: dict[str, bool] = {}
    duty_content: dict[str, bool] = {}
    metrics: dict[str, object] = {
        "question_id": f"Q{int(number)}",
        "source": str(section_path) if section_path else None,
        "duties": duties,
        "duty_content": duty_content,
        "subsection_count": 0,
        "display_math_count": 0,
        "table_count": 0,
        "figure_count": 0,
        "label_count": 0,
        "validation_anchor_present": False,
        "comparative_validation_visible": None,
    }
    if section_path is None:
        target.append(f"standalone question source is missing for {main_path.name}")
        return metrics, errors, warnings

    visible = strip_tex_comments(section_path.read_text(encoding="utf-8", errors="replace"))
    headings = list(HEADING_PATTERN.finditer(visible))
    metrics.update(
        {
            "subsection_count": len(re.findall(r"\\subsection\*?\{", visible)),
            "display_math_count": len(re.findall(r"\\\[|\\begin\{(?:equation|align|gather)\*?\}", visible)),
            "table_count": len(re.findall(r"\\begin\{table\}", visible)),
            "figure_count": len(re.findall(r"\\begin\{figure\}", visible)),
            "label_count": len(re.findall(r"\\label\{[^{}]+\}", visible)),
        }
    )
    for duty, pattern in QUESTION_DUTIES.items():
        matching = [
            (index, heading) for index, heading in enumerate(headings)
            if pattern.search(heading.group("title"))
        ]
        present = bool(matching)
        duties[duty] = present
        if not present:
            target.append(f"standalone question lacks a substantive {duty} section: {section_path.relative_to(paper_dir)}")
            duty_content[duty] = False
            continue
        content_present = False
        for index, heading in matching:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(visible)
            body = visible[heading.end():end]
            plain = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", body)
            plain = re.sub(r"[{}$\\\s]", "", plain)
            embedded = re.search(
                r"\\input\{|\\includegraphics|\\begin\{(?:equation|align|gather|table|figure|tabular)",
                body,
            )
            if len(plain) >= 16 or embedded:
                content_present = True
                break
        duty_content[duty] = content_present
        if not content_present:
            target.append(f"standalone {duty} heading has no substantive content: {section_path.relative_to(paper_dir)}")

    validation_segments: list[str] = []
    for index, heading in enumerate(headings):
        if not QUESTION_DUTIES["validation"].search(heading.group("title")):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(visible)
        validation_segments.append(visible[heading.start():end])
    validation_text = "\n".join(validation_segments)
    anchor_present = bool(re.search(r"\\label\{[^{}]+\}", validation_text))
    metrics["validation_anchor_present"] = anchor_present
    if validation_text and not anchor_present:
        target.append("standalone validation must have a paper-visible LaTeX label")

    if validation_text and COMPARATIVE_VALIDATION_PATTERN.search(validation_text):
        visible_evidence = bool(VISIBLE_EVIDENCE_PATTERN.search(validation_text))
        metrics["comparative_validation_visible"] = visible_evidence
        if not visible_evidence:
            target.append("comparative validation is compressed into prose; add a judge-visible table or figure")
    return metrics, errors, warnings


def scan_sources(paper_dir: Path, mode: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in paper_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".tex", ".bib"}:
            continue
        relative = path.relative_to(paper_dir)
        if "build" in relative.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        visible = strip_tex_comments(text) if path.suffix.lower() == ".tex" else text
        placeholder_target = errors if mode == "submission" else warnings
        for placeholder in find_placeholders(visible):
            qualifier = "remains" if mode == "submission" else "marks this build as review-only"
            placeholder_target.append(f"placeholder '{placeholder}' {qualifier} in {relative}")

        if "sections" not in relative.parts:
            continue
        internal_target = errors if mode == "submission" else warnings
        for pattern, message in INTERNAL_PAPER_PATTERNS:
            if re.search(pattern, visible, flags=re.IGNORECASE | re.MULTILINE):
                internal_target.append(f"{message} leaked into paper source: {relative}")
        for pattern, message in LEAN_PAPER_WARNINGS:
            if re.search(pattern, visible, flags=re.MULTILINE):
                warnings.append(f"{message}: {relative}")
        if relative.name != "90_appendix.tex" and re.search(
            r"\\lstinputlisting|\\begin\{(?:lstlisting|verbatim)\}", visible
        ):
            warnings.append(f"full code listing should stay in the profile-designated appendix/support package: {relative}")
        if relative.name in {"00_abstract.tex", "00_summary.tex"}:
            if re.search(r"\\cite[tp]?\s*\{", visible):
                warnings.append(f"abstract/summary contains a citation; keep it only if indispensable: {relative}")
            if re.search(r"\\begin\{(?:equation|align|gather)\*?\}|\\\[", visible):
                warnings.append(f"abstract/summary contains displayed mathematics; prefer a result map: {relative}")
    return errors, warnings


def scan_log(log_text: str, mode: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for pattern, message in BLOCKING_LOG_PATTERNS:
        if re.search(pattern, log_text, flags=re.MULTILINE | re.IGNORECASE):
            errors.append(message)

    missing_chars = re.findall(r"Missing character: There is no .+", log_text)
    if missing_chars:
        target = errors if mode == "submission" else warnings
        target.append(f"{len(missing_chars)} missing-character warning(s)")

    overfull = [float(value) for value in re.findall(r"Overfull \\hbox \(([0-9.]+)pt too wide\)", log_text)]
    if overfull:
        maximum = max(overfull)
        message = f"{len(overfull)} overfull box(es), maximum {maximum:.2f}pt"
        if mode == "submission" and maximum > 5.0:
            errors.append(message)
        else:
            warnings.append(message)

    if re.search(r"multiply defined", log_text, flags=re.IGNORECASE):
        target = errors if mode == "submission" else warnings
        target.append("multiply defined labels")
    return errors, warnings


def resolve_poppler_tool(name: str) -> str | None:
    executable = shutil.which(name)
    if not executable:
        return None
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        bundled = path.parents[2] / "native" / "poppler" / "Library" / "bin" / f"{name}.exe"
        if bundled.is_file():
            return str(bundled)
    return executable


def pdf_metadata(pdf_path: Path) -> tuple[dict[str, object], str | None]:
    pdfinfo = resolve_poppler_tool("pdfinfo")
    if not pdfinfo:
        return {}, "pdfinfo is missing"
    command = [pdfinfo, str(pdf_path)]
    result = run(command, pdf_path.parent)
    if result.returncode != 0:
        return {}, "pdfinfo failed"
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    pages_match = re.search(r"^Pages:\s+(\d+)", result.stdout, flags=re.MULTILINE | re.IGNORECASE)
    size_match = re.search(
        r"^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts",
        result.stdout,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    metadata: dict[str, object] = {
        "pages": int(pages_match.group(1)) if pages_match else None,
        "page_width_points": float(size_match.group(1)) if size_match else None,
        "page_height_points": float(size_match.group(2)) if size_match else None,
        "author": fields.get("author", ""),
        "title": fields.get("title", ""),
        "subject": fields.get("subject", ""),
        "keywords": fields.get("keywords", ""),
    }
    return metadata, None


def pdf_text_page_fill(pdf_path: Path) -> tuple[list[float], str | None]:
    pdftotext = resolve_poppler_tool("pdftotext")
    if not pdftotext:
        return [], "pdftotext is missing; standalone page-density audit was not run"
    result = run([pdftotext, "-bbox-layout", str(pdf_path), "-"], pdf_path.parent)
    if result.returncode != 0:
        return [], "pdftotext bbox extraction failed; standalone page-density audit was not run"
    try:
        ratios = parse_page_fill(result.stdout)
    except (ET.ParseError, KeyError, TypeError, ValueError):
        return [], "pdftotext bbox output is invalid; standalone page-density audit was not run"
    return ratios, None


def parse_page_fill(bbox_xml: str) -> list[float]:
    root = ET.fromstring(bbox_xml)
    ratios: list[float] = []
    for page in root.findall(".//{*}page"):
        height = float(page.attrib["height"])
        bottoms = [float(word.attrib["yMax"]) for word in page.findall(".//{*}word")]
        ratios.append(round(max(bottoms, default=0.0) / height, 4) if height > 0 else 0.0)
    return ratios


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile and audit a direct-LaTeX contest paper.")
    parser.add_argument("paper_dir", help="Directory containing main.tex")
    parser.add_argument("--engine", choices=("xelatex", "pdflatex", "lualatex"))
    parser.add_argument("--competition", choices=tuple(ENGINE_BY_COMPETITION), help="Legacy shortcut; prefer --engine from a verified profile")
    parser.add_argument("--mode", choices=("draft", "submission"), default="draft")
    parser.add_argument("--main", default="main.tex")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paper_dir = Path(args.paper_dir).expanduser().resolve()
    main_path = paper_dir / args.main
    artifact_class = classify_artifact(main_path)
    build_dir = paper_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    if main_path.stem == "main":
        report_path = build_dir / "build_report.json"
        stdout_path = build_dir / "build_stdout.log"
    else:
        report_path = build_dir / f"build_report_{main_path.stem}.json"
        stdout_path = build_dir / f"build_stdout_{main_path.stem}.log"

    errors, warnings = scan_sources(paper_dir, args.mode)
    question_audit, question_errors, question_warnings = audit_question_standalone(
        paper_dir, main_path, args.mode
    )
    errors.extend(question_errors)
    warnings.extend(question_warnings)
    engine = args.engine or ENGINE_BY_COMPETITION.get(args.competition or "", "")
    if not engine:
        errors.append("LaTeX engine is not specified; use --engine or the legacy --competition shortcut")
    if not main_path.is_file():
        errors.append(f"main file is missing: {main_path}")
        result = subprocess.CompletedProcess([], 1, "")
    elif not engine or not shutil.which(engine):
        errors.append(f"LaTeX engine is missing: {engine}")
        result = subprocess.CompletedProcess([], 1, "")
    else:
        result = compile_paper(paper_dir, main_path, engine, build_dir)
        stdout_path.write_text(result.stdout, encoding="utf-8")
        if result.returncode != 0:
            errors.append(f"compiler returned exit code {result.returncode}")

    log_path = build_dir / f"{main_path.stem}.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else result.stdout
    log_errors, log_warnings = scan_log(log_text, args.mode)
    errors.extend(log_errors)
    warnings.extend(log_warnings)

    pdf_path = build_dir / f"{main_path.stem}.pdf"
    pages: int | None = None
    front_matter_pages: int | None = None
    body_pages: int | None = None
    page_width_points: float | None = None
    page_height_points: float | None = None
    pdf_author: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    page_text_fill: list[float] = []
    if pdf_path.is_file():
        metadata, metadata_warning = pdf_metadata(pdf_path)
        if metadata_warning:
            target = errors if args.mode == "submission" else warnings
            target.append(metadata_warning)
        pages_value = metadata.get("pages")
        pages = int(pages_value) if isinstance(pages_value, int) else None
        width_value = metadata.get("page_width_points")
        height_value = metadata.get("page_height_points")
        page_width_points = float(width_value) if isinstance(width_value, (int, float)) else None
        page_height_points = float(height_value) if isinstance(height_value, (int, float)) else None
        author_value = metadata.get("author")
        pdf_author = str(author_value) if author_value is not None else None
        file_size_bytes = pdf_path.stat().st_size
        sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        if artifact_class == "question_standalone":
            page_text_fill, density_warning = pdf_text_page_fill(pdf_path)
            if density_warning:
                target = errors if args.mode == "submission" else warnings
                target.append(density_warning)
            elif len(page_text_fill) >= 2 and page_text_fill[-1] < 0.55:
                target = errors if args.mode == "submission" else warnings
                target.append(
                    f"standalone final page uses only {page_text_fill[-1]:.1%} of page height; repair float placement or consolidate the section"
                )
    else:
        errors.append("compiled PDF is missing")

    front_match = re.search(r"(?:MATHMODEL|MATHAWARD):FRONT_MATTER_PAGES=(\d+)", log_text)
    if front_match:
        front_matter_pages = int(front_match.group(1))
    body_match = re.search(r"(?:MATHMODEL|MATHAWARD):(?:CUMCM_BODY|MCM_MAIN|BODY)_PAGES=(\d+)", log_text)
    if body_match:
        body_pages = int(body_match.group(1))

    if errors or args.mode == "draft":
        release_class = "review_only"
    elif artifact_class == "full_paper":
        release_class = "submission_candidate"
    elif artifact_class == "question_standalone":
        release_class = "question_handoff_candidate"
    else:
        release_class = "auxiliary_candidate"

    report = {
        "status": "pass" if not errors else "block",
        "mode": args.mode,
        "artifact_class": artifact_class,
        "release_class": release_class,
        "submission_eligible": artifact_class == "full_paper" and args.mode == "submission" and not errors,
        "handoff_eligible": args.mode == "submission" and not errors,
        "competition": args.competition,
        "engine": engine,
        "source": str(main_path),
        "pdf": str(pdf_path) if pdf_path.exists() else None,
        "pages": pages,
        "front_matter_pages": front_matter_pages,
        "body_pages": body_pages,
        "page_width_points": page_width_points,
        "page_height_points": page_height_points,
        "file_size_bytes": file_size_bytes,
        "pdf_author": pdf_author,
        "sha256": sha256,
        "page_text_fill": page_text_fill,
        "question_audit": question_audit,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
