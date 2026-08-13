#!/usr/bin/env python3
"""Check that every frozen CUMCM question has one loaded LaTeX section."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_latex import find_placeholders, strip_tex_comments


INPUT_PATTERN = re.compile(r"\\input\{(sections/questions/[^}]+)\}")
QUESTION_ID_PATTERN = re.compile(r"^Q(?P<number>\d+)$", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{[^{}]*\}")
NONCONTENT_PATTERN = re.compile(
    r"\\(?:label|index|addcontentsline)\{[^{}]*\}"
    r"|\\(?:clearpage|newpage|pagebreak|medskip|smallskip|bigskip)\b"
)


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def has_substantive_tex_content(visible: str) -> bool:
    without_headings = HEADING_PATTERN.sub("", visible)
    without_bookkeeping = NONCONTENT_PATTERN.sub("", without_headings)
    return bool(re.sub(r"[\s{}~]+", "", without_bookkeeping))


def validate_paper_question_coverage(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    contract = load_json(workspace / "shared" / "problem_contract.json")
    questions = contract.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = []
        errors.append("problem_contract.json has no source-verified questions to map into the paper")
    question_ids = [
        str(item.get("question_id", "")).strip() if isinstance(item, dict) else ""
        for item in questions
    ]

    loader_path = workspace / "paper" / "generated" / "question_sections.tex"
    try:
        loader_text = strip_tex_comments(loader_path.read_text(encoding="utf-8"))
    except OSError:
        loader_text = ""
        errors.append("paper/generated/question_sections.tex is missing")
    inputs = INPUT_PATTERN.findall(loader_text)
    normalized_inputs = [value if value.endswith(".tex") else f"{value}.tex" for value in inputs]
    if len(normalized_inputs) != len(set(normalized_inputs)):
        errors.append("question_sections.tex loads a question section more than once")
    if len(normalized_inputs) != len(question_ids):
        errors.append(
            f"paper loads {len(normalized_inputs)} question section(s), but problem contract freezes {len(question_ids)} question(s)"
        )

    mappings = []
    for index, question_id in enumerate(question_ids):
        relative = normalized_inputs[index] if index < len(normalized_inputs) else ""
        mappings.append({"question_id": question_id, "paper_section": relative})
        if not relative:
            continue
        question_match = QUESTION_ID_PATTERN.fullmatch(question_id)
        if question_match:
            expected_name = f"q{int(question_match.group('number')):02d}.tex"
            actual_name = Path(relative).name.lower()
            if actual_name != expected_name:
                errors.append(
                    f"{question_id} must load sections/questions/{expected_name}, not {relative}"
                )
        else:
            warnings.append(f"question id is not canonical Q<number>; verify semantic mapping manually: {question_id}")
        section_path = workspace / "paper" / relative
        try:
            visible = strip_tex_comments(section_path.read_text(encoding="utf-8"))
        except OSError:
            errors.append(f"question section is missing: {relative}")
            continue
        placeholders = find_placeholders(visible)
        if placeholders:
            errors.append(f"question section still contains placeholder(s) {', '.join(placeholders)}: {relative}")
        if not has_substantive_tex_content(visible):
            errors.append(f"question section is empty or still a draft: {relative}")
        if not re.search(r"\\(?:section|subsection)\*?\{", visible):
            warnings.append(f"question section has no visible heading: {relative}")

    report = {
        "status": "pass" if not errors else "block",
        "question_count": len(question_ids),
        "loaded_section_count": len(normalized_inputs),
        "mappings": mappings,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "paper_question_coverage_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CUMCM question-to-LaTeX coverage.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_paper_question_coverage(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
