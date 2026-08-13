#!/usr/bin/env python3
"""Validate the source-bound question contract used as the paper's scope authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_utils import artifact_errors


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_problem_contract(workspace: Path, *, final: bool = False) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load_json(workspace / "shared" / "problem_contract.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("problem_contract.json schema_version must be 1")
    if final and document.get("status") != "frozen":
        errors.append("problem contract must be frozen before finalization")

    sources = document.get("problem_artifacts")
    source_ids: set[str] = set()
    if not isinstance(sources, list) or not sources:
        errors.append("problem contract has no source problem artifacts")
        sources = []
    for index, source in enumerate(sources, start=1):
        label = f"problem artifact {index}"
        if not isinstance(source, dict):
            errors.append(f"{label} is invalid")
            continue
        source_id = str(source.get("source_id", "")).strip()
        if not source_id or source_id in source_ids:
            errors.append(f"{label}: source_id is empty or duplicated")
        source_ids.add(source_id)
        relative = str(source.get("relative_path", "")).replace("\\", "/").strip()
        if relative and not relative.startswith("inputs/original/"):
            errors.append(f"{label}: relative_path must be under inputs/original")
        if not str(source.get("reviewer", "")).strip():
            errors.append(f"{label}: reviewer is empty")
        errors.extend(
            artifact_errors(
                workspace,
                source,
                label,
                path_field="relative_path",
                check_field="verification_command",
                time_field="verified_at",
            )
        )

    questions = document.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("problem contract has no questions")
        questions = []
    question_ids: list[str] = []
    upstream_map: dict[str, list[str]] = {}
    for index, question in enumerate(questions, start=1):
        label = f"question contract {index}"
        if not isinstance(question, dict):
            errors.append(f"{label} is invalid")
            continue
        question_id = str(question.get("question_id", "")).strip()
        if not question_id or question_id in question_ids:
            errors.append(f"{label}: question_id is empty or duplicated")
        question_ids.append(question_id)
        source_id = str(question.get("source_id", "")).strip()
        if source_id not in source_ids:
            errors.append(f"{question_id or label}: source_id is unknown")
        for field in (
            "source_locator",
            "required_answer",
            "inputs",
            "constraints_precision",
            "verification_notes",
        ):
            if not str(question.get(field, "")).strip():
                errors.append(f"{question_id or label}: {field} is empty")
        verbs = question.get("task_verbs")
        if not isinstance(verbs, list) or not verbs or any(not isinstance(item, str) or not item.strip() for item in verbs):
            errors.append(f"{question_id or label}: task_verbs must be a non-empty string array")
        artifacts = question.get("required_artifacts")
        if not isinstance(artifacts, list) or any(not isinstance(item, str) or not item.strip() for item in artifacts):
            errors.append(f"{question_id or label}: required_artifacts must be a string array")
            artifacts = []
        if final:
            for relative in artifacts:
                path = (workspace / str(relative)).resolve()
                try:
                    path.relative_to(workspace)
                except ValueError:
                    errors.append(f"{question_id}: required artifact escapes workspace: {relative}")
                else:
                    if not path.is_file():
                        errors.append(f"{question_id}: required artifact is missing: {relative}")
        upstream = question.get("upstream_question_ids")
        if not isinstance(upstream, list) or any(not isinstance(item, str) or not item.strip() for item in upstream):
            errors.append(f"{question_id or label}: upstream_question_ids must be a string array")
            upstream = []
        upstream_map[question_id] = [str(item).strip() for item in upstream]
        if question.get("verified_against_prompt") is not True:
            errors.append(f"{question_id or label}: verified_against_prompt is not true")

    known = set(question_ids)
    for question_id, upstream in upstream_map.items():
        for producer in upstream:
            if producer == question_id:
                errors.append(f"{question_id}: cannot depend on itself")
            elif producer not in known:
                errors.append(f"{question_id}: unknown upstream question {producer}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(question_id: str) -> None:
        if question_id in visiting:
            errors.append("question dependency graph contains a cycle")
            return
        if question_id in visited:
            return
        visiting.add(question_id)
        for producer in upstream_map.get(question_id, []):
            if producer in known:
                visit(producer)
        visiting.remove(question_id)
        visited.add(question_id)

    for question_id in question_ids:
        visit(question_id)

    if final:
        selection = load_json(workspace / "synthesis" / "model_selection.json")
        selection_questions = selection.get("questions")
        selection_ids = [
            str(item.get("question_id", "")).strip()
            for item in selection_questions
            if isinstance(item, dict)
        ] if isinstance(selection_questions, list) else []
        if selection_ids != question_ids:
            errors.append("model_selection question order does not match the frozen problem contract")

    report = {
        "status": "pass" if not errors else "block",
        "question_ids": question_ids,
        "dependency_edges": sorted(
            f"{producer}->{consumer}"
            for consumer, producers in upstream_map.items()
            for producer in producers
        ),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "problem_contract_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the source-bound problem contract.")
    parser.add_argument("workspace")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    report = validate_problem_contract(Path(args.workspace).expanduser(), final=args.final)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
