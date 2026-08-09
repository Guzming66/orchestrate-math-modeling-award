#!/usr/bin/env python3
"""Check that every frozen CUMCM question has one loaded LaTeX section."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_latex import strip_tex_comments


INPUT_PATTERN = re.compile(r"\\input\{(sections/questions/[^}]+)\}")


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_paper_question_coverage(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    selection = load_json(workspace / "synthesis" / "model_selection.json")
    questions = selection.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = []
        errors.append("model_selection.json has no core questions to map into the paper")
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
            f"paper loads {len(normalized_inputs)} question section(s), but model selection freezes {len(question_ids)} core question(s)"
        )

    mappings = []
    for index, question_id in enumerate(question_ids):
        relative = normalized_inputs[index] if index < len(normalized_inputs) else ""
        mappings.append({"question_id": question_id, "paper_section": relative})
        if not relative:
            continue
        section_path = workspace / "paper" / relative
        try:
            visible = strip_tex_comments(section_path.read_text(encoding="utf-8"))
        except OSError:
            errors.append(f"question section is missing: {relative}")
            continue
        if "DRAFT CONTENT" in visible or not visible.strip():
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
