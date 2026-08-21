#!/usr/bin/env python3
"""Explainable local overlap precheck for reference papers and reusable templates."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from build_latex import strip_tex_comments
from evidence_utils import sha256_file
from latex_sources import loaded_tex_sources


IGNORE_HEADINGS = {
    "摘要", "关键词", "参考文献", "附录", "问题一", "问题二", "问题三", "问题四", "问题五",
    "模型假设", "符号说明", "问题分析", "模型建立", "模型求解", "结果分析", "灵敏度分析", "模型评价",
    "abstract", "keywords", "references", "appendix", "problem restatement", "problem analysis",
    "assumptions", "notation", "model", "results", "sensitivity analysis", "conclusion",
}
LATEX_NOISE = re.compile(
    r"\\begin\{(?:equation|align|gather|multline|table|figure|lstlisting)\*?\}.*?"
    r"\\end\{(?:equation|align|gather|multline|table|figure|lstlisting)\*?\}",
    re.DOTALL,
)


def normalize(text: str) -> str:
    text = strip_tex_comments(text)
    text = LATEX_NOISE.sub(" ", text)
    text = re.sub(r"\\(?:cite|ref|eqref|autoref|cref|Cref|label|includegraphics|input)(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\[[0-9,;\- ]+\]", " ", text)
    text = re.sub(r"[\s{}$&_^~#%\\|`]+", "", text)
    text = re.sub(r"[，。；：！？、,.!?;:'\"“”‘’（）()\[\]<>《》=+\-*/0-9]", "", text)
    for heading in IGNORE_HEADINGS:
        text = text.replace(heading, "")
    return text.lower()


def ngrams(text: str, size: int) -> list[tuple[str, int]]:
    return [(text[index:index + size], index) for index in range(max(0, len(text) - size + 1))]


def read_registry(workspace: Path) -> tuple[list[dict[str, str]], list[str]]:
    path = workspace / "audits" / "similarity" / "reference_corpus.csv"
    errors: list[str] = []
    if not path.is_file():
        return [], ["similarity reference_corpus.csv is missing"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return [], ["similarity reference_corpus.csv has no registered reference texts"]
    for index, row in enumerate(rows, start=2):
        label = row.get("source_id", "").strip() or f"reference row {index}"
        for field in ("source_id", "source_type", "text_path", "sha256"):
            if not row.get(field, "").strip():
                errors.append(f"{label}: {field} is empty")
        if row.get("source_type", "").strip() not in {"excellent_paper", "template"}:
            errors.append(f"{label}: source_type must be excellent_paper or template")
        rel = row.get("text_path", "").replace("\\", "/").strip()
        try:
            source = (workspace / rel).resolve()
            source.relative_to(workspace)
        except ValueError:
            errors.append(f"{label}: text_path escapes workspace")
            continue
        if not source.is_file():
            errors.append(f"{label}: reference text is missing")
        elif row.get("sha256", "").strip().lower() != sha256_file(source):
            errors.append(f"{label}: reference text sha256 does not match")
        if row.get("status", "").strip().lower() != "verified":
            errors.append(f"{label}: status is not verified")
    return rows, errors


def collect_paper(workspace: Path) -> list[tuple[str, str]]:
    paper = workspace / "paper"
    items: list[tuple[str, str]] = []
    for path in loaded_tex_sources(paper):
        if path.name == "ai_usage_details.tex":
            continue
        text = normalize(path.read_text(encoding="utf-8", errors="replace"))
        if text:
            items.append((path.relative_to(workspace).as_posix(), text))
    return items


def validate_similarity_precheck(workspace: Path, *, ngram_size: int = 24, block_count: int = 3) -> dict[str, object]:
    workspace = workspace.resolve()
    rows, errors = read_registry(workspace)
    warnings: list[str] = []
    matches: list[dict[str, object]] = []
    paper_items = collect_paper(workspace)
    reference_index: dict[str, list[tuple[str, int]]] = defaultdict(list)
    reference_counts: dict[str, int] = {}
    for row in rows:
        rel = row.get("text_path", "").replace("\\", "/").strip()
        source = workspace / rel
        if not source.is_file():
            continue
        source_id = row.get("source_id", "").strip()
        normalized = normalize(source.read_text(encoding="utf-8", errors="replace"))
        grams = ngrams(normalized, ngram_size)
        reference_counts[source_id] = len(grams)
        for gram, position in grams:
            reference_index[gram].append((source_id, position))

    by_pair: dict[tuple[str, str], list[tuple[int, str, int]]] = defaultdict(list)
    paper_gram_count = 0
    for paper_path, text in paper_items:
        grams = ngrams(text, ngram_size)
        paper_gram_count += len(grams)
        for gram, position in grams:
            for source_id, source_position in reference_index.get(gram, []):
                by_pair[(paper_path, source_id)].append((position, gram, source_position))

    source_totals: dict[str, int] = defaultdict(int)
    for (paper_path, source_id), values in by_pair.items():
        values.sort()
        nonoverlap: list[tuple[int, str, int]] = []
        previous = -ngram_size
        for item in values:
            if item[0] - previous >= ngram_size:
                nonoverlap.append(item)
                previous = item[0]
        source_totals[source_id] += len(nonoverlap)
        for position, gram, source_position in nonoverlap[:10]:
            matches.append(
                {
                    "paper_path": paper_path,
                    "source_id": source_id,
                    "paper_char_offset": position,
                    "source_char_offset": source_position,
                    "normalized_overlap": gram,
                    "length": len(gram),
                }
            )

    for source_id, count in sorted(source_totals.items()):
        source_type = next((row.get("source_type", "") for row in rows if row.get("source_id", "").strip() == source_id), "")
        if source_type == "template" and count >= 1:
            errors.append(f"template overlap requires revision: {source_id} has {count} non-overlapping {ngram_size}-character matches")
        elif source_type == "excellent_paper" and count >= block_count:
            errors.append(f"excellent-paper overlap requires manual review: {source_id} has {count} non-overlapping {ngram_size}-character matches")
        elif count:
            warnings.append(f"reference overlap found: {source_id} has {count} non-overlapping matches")

    report = {
        "status": "pass" if not errors else "block",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "method": "exact normalized character n-gram precheck; formulas, citations, URLs, generic headings and LaTeX structure excluded",
        "limitations": "This is not an official similarity score and does not replace institutional systems or human review.",
        "ngram_size": ngram_size,
        "block_count": block_count,
        "paper_source_count": len(paper_items),
        "paper_ngram_count": paper_gram_count,
        "reference_count": len(rows),
        "reference_ngram_counts": reference_counts,
        "matches": matches,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "similarity" / "similarity_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local overlap precheck against registered papers and templates.")
    parser.add_argument("workspace")
    parser.add_argument("--ngram-size", type=int, default=24)
    parser.add_argument("--block-count", type=int, default=3)
    args = parser.parse_args()
    report = validate_similarity_precheck(Path(args.workspace).expanduser(), ngram_size=args.ngram_size, block_count=args.block_count)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
