#!/usr/bin/env python3
"""Validate the sanitized scientific payload and contest-paper presentation firewall."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_latex import INTERNAL_PAPER_PATTERNS, strip_tex_comments


FORBIDDEN_KEYS = {
    "artifact_path",
    "sha256",
    "workflow_stage",
    "review_status",
    "claim_status",
    "acceptance_status",
    "audit_path",
    "reproduction_command",
    "task_board",
    "decision_log",
    "freeze_status",
    "command_or_check",
    "verification_command",
    "checked_at",
    "reviewer",
    "finding_id",
    "review_type",
    "severity",
    "task_id",
    "internal_rationale",
}
META_LANGUAGE = tuple(
    (re.compile(pattern, re.IGNORECASE), message)
    for pattern, message in INTERNAL_PAPER_PATTERNS
)
FIGURE_ROLES = {"mechanism", "data", "diagnostic", "decision"}
ROOT_KEYS = {"schema_version", "status", "questions", "notes"}
QUESTION_KEYS = {
    "question_id", "evidence_profile", "problem_summary", "assumptions", "core_model",
    "derivation_summary", "algorithm_summary", "key_results", "comparison_summary",
    "validation_summary", "sensitivity_and_limits", "precision_policy", "complexity_value",
    "paper_section", "figures", "citations",
}
PRECISION_KEYS = {"display_rule", "justification", "dominant_uncertainty"}
COMPLEXITY_KEYS = {"mode", "added_complexity", "structural_need", "incremental_gain", "decision"}
FIGURE_KEYS = {"path", "role", "supported_claim", "source_data", "generator"}
COMPLEXITY_MODES = {"no_extra_complexity", "semantics_required", "incremental_change"}


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def reject_unknown(mapping: dict[str, object], allowed: set[str], location: str, errors: list[str]) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        errors.append(f"{location}: unknown paper-payload keys: {', '.join(sorted(unknown))}")


def walk_payload(value: object, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in FORBIDDEN_KEYS or (normalized_key == "status" and location != "paper_payload"):
                errors.append(f"{location}: forbidden control-plane key in paper payload: {key}")
            walk_payload(nested, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            walk_payload(nested, f"{location}[{index}]", errors)
    elif isinstance(value, str):
        for pattern, message in META_LANGUAGE:
            if pattern.search(value):
                errors.append(f"{location}: {message} leaked into paper payload")


def validate_paper_presentation(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    payload = load(workspace / "synthesis" / "paper_payload.json")
    selection = load(workspace / "synthesis" / "model_selection.json")
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema_version") != 1:
        errors.append("paper_payload.json schema_version must be 1")
    if payload.get("status") != "ready":
        errors.append("paper payload is not ready")
    ready = payload.get("status") == "ready"
    if selection.get("schema_version") != 2 or selection.get("status") != "frozen":
        errors.append("paper payload requires frozen model_selection.json schema v2")
    reject_unknown(payload, ROOT_KEYS, "paper_payload", errors)
    walk_payload(payload, "paper_payload", errors)

    expected_profiles: dict[str, str] = {}
    selection_questions = selection.get("questions")
    if isinstance(selection_questions, list):
        for item in selection_questions:
            if isinstance(item, dict):
                question_id = str(item.get("question_id", "")).strip()
                if question_id:
                    expected_profiles[question_id] = str(item.get("evidence_profile", "")).strip().lower()

    questions = payload.get("questions")
    if not isinstance(questions, list):
        errors.append("paper_payload.json questions is not an array")
        questions = []
    seen: set[str] = set()
    figure_count = 0
    for index, item in enumerate(questions, start=1):
        label = f"payload[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} is invalid")
            continue
        question_id = str(item.get("question_id", "")).strip()
        if not question_id or question_id in seen:
            errors.append(f"{label}: question_id is empty or duplicated")
            continue
        seen.add(question_id)
        label = question_id
        reject_unknown(item, QUESTION_KEYS, label, errors)
        profile = str(item.get("evidence_profile", "")).strip().lower()
        if expected_profiles.get(question_id) != profile or not profile:
            errors.append(f"{label}: evidence_profile does not match model_selection.json")

        precision = item.get("precision_policy")
        if isinstance(precision, dict):
            reject_unknown(precision, PRECISION_KEYS, f"{label}.precision_policy", errors)
        complexity = item.get("complexity_value")
        if isinstance(complexity, dict):
            reject_unknown(complexity, COMPLEXITY_KEYS, f"{label}.complexity_value", errors)
        figures = item.get("figures", [])
        if isinstance(figures, list):
            for figure_index, figure in enumerate(figures, start=1):
                if isinstance(figure, dict):
                    reject_unknown(figure, FIGURE_KEYS, f"{label}/figure[{figure_index}]", errors)
        if not ready:
            continue

        for field in (
            "problem_summary",
            "core_model",
            "derivation_summary",
            "validation_summary",
            "sensitivity_and_limits",
            "paper_section",
        ):
            if not nonempty(item.get(field)):
                errors.append(f"{label}: {field} is empty")
        if profile != "analytical" and not nonempty(item.get("algorithm_summary")):
            errors.append(f"{label}: algorithm_summary is empty for {profile or 'unknown'} profile")
        if not nonempty(item.get("comparison_summary")):
            warnings.append(f"{label}: comparison_summary is empty; acceptable only when no comparison changes the argument")
        key_results = item.get("key_results")
        if not isinstance(key_results, list) or not key_results or not all(nonempty(value) for value in key_results):
            errors.append(f"{label}: key_results must contain at least one result sentence")
        assumptions = item.get("assumptions")
        if not isinstance(assumptions, list):
            errors.append(f"{label}: assumptions is not an array")

        if not isinstance(precision, dict):
            errors.append(f"{label}: precision_policy is missing")
        else:
            for field in ("display_rule", "justification", "dominant_uncertainty"):
                if not nonempty(precision.get(field)):
                    errors.append(f"{label}: precision_policy.{field} is empty")

        if not isinstance(complexity, dict):
            errors.append(f"{label}: complexity_value is missing")
        else:
            mode = str(complexity.get("mode", "")).strip().lower()
            if mode not in COMPLEXITY_MODES:
                errors.append(f"{label}: complexity_value.mode is invalid")
            for field in ("added_complexity", "structural_need", "decision"):
                if not nonempty(complexity.get(field)):
                    errors.append(f"{label}: complexity_value.{field} is empty")
            gain = complexity.get("incremental_gain")
            if mode == "incremental_change" and not nonempty(gain):
                errors.append(f"{label}: complexity_value.incremental_gain is required for incremental_change")
            elif mode in {"no_extra_complexity", "semantics_required"} and gain is not None and not isinstance(gain, str):
                errors.append(f"{label}: complexity_value.incremental_gain must be text or null")

        section_rel = str(item.get("paper_section", "")).replace("\\", "/").strip()
        section = (workspace / section_rel).resolve()
        try:
            section.relative_to(workspace / "paper" / "sections")
        except ValueError:
            errors.append(f"{label}: paper_section must stay under paper/sections")
        else:
            if not section.is_file():
                errors.append(f"{label}: paper_section is missing")

        if not isinstance(figures, list):
            errors.append(f"{label}: figures is not an array")
            figures = []
        for figure_index, figure in enumerate(figures, start=1):
            figure_label = f"{label}/figure[{figure_index}]"
            if not isinstance(figure, dict):
                errors.append(f"{figure_label} is invalid")
                continue
            for field in ("path", "role", "supported_claim", "source_data", "generator"):
                if not nonempty(figure.get(field)):
                    errors.append(f"{figure_label}: {field} is empty")
            role = str(figure.get("role", "")).strip().lower()
            if role not in FIGURE_ROLES:
                errors.append(f"{figure_label}: invalid evidence role")
            figure_rel = str(figure.get("path", "")).replace("\\", "/").strip()
            figure_path = (workspace / figure_rel).resolve()
            try:
                figure_path.relative_to(workspace / "paper" / "figures")
            except ValueError:
                errors.append(f"{figure_label}: path must stay under paper/figures")
            else:
                if not figure_path.is_file():
                    errors.append(f"{figure_label}: figure file is missing")
            figure_count += 1

    if set(expected_profiles) != seen:
        missing = set(expected_profiles) - seen
        extra = seen - set(expected_profiles)
        if missing:
            errors.append(f"paper payload is missing questions: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"paper payload contains unknown questions: {', '.join(sorted(extra))}")

    paper_sections = workspace / "paper" / "sections"
    for path in paper_sections.rglob("*.tex") if paper_sections.is_dir() else []:
        visible = strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))
        for pattern, message in META_LANGUAGE:
            if pattern.search(visible):
                errors.append(f"{message} leaked into final paper: {path.relative_to(workspace)}")

    report = {
        "status": "pass" if not errors else "block",
        "question_count": len(questions),
        "figure_count": figure_count,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "presentation" / "paper_presentation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the contest-paper presentation firewall.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_paper_presentation(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
