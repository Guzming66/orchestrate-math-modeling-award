#!/usr/bin/env python3
"""Validate per-question routing for scientific, statistical, and implementation review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_utils import artifact_errors
from validate_model_selection import PROFILE_CHECKS


STATISTICS_REQUIRED = {"statistical", "simulation", "machine_learning"}
REVIEW_KINDS = {"scientific", "implementation", "statistical", "uncertainty", "claims"}
UNCERTAINTY_FOCI = {
    "numerical_solver",
    "parameter_sensitivity",
    "model_form",
    "measurement",
    "stochastic",
}


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_review_route(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    selection = load(workspace / "synthesis" / "model_selection.json")
    route = load(workspace / "synthesis" / "review_route.json")
    errors: list[str] = []
    warnings: list[str] = []

    if route.get("schema_version") != 1:
        errors.append("review_route.json schema_version must be 1")
    routed = route.get("status") == "routed"
    if not routed:
        errors.append("review routing is not complete")
    if selection.get("schema_version") != 2 or selection.get("status") != "frozen":
        errors.append("review routing requires frozen model_selection.json schema v2")

    selection_questions = selection.get("questions")
    expected_profiles: dict[str, str] = {}
    if isinstance(selection_questions, list):
        for item in selection_questions:
            if isinstance(item, dict):
                question_id = str(item.get("question_id", "")).strip()
                profile = str(item.get("evidence_profile", "")).strip().lower()
                if question_id:
                    expected_profiles[question_id] = profile
    if not expected_profiles:
        errors.append("review route cannot be checked without model-selection questions")

    questions = route.get("questions")
    if not isinstance(questions, list):
        errors.append("review_route.json questions is not an array")
        questions = []
    seen: set[str] = set()
    routed_statistics: dict[str, str] = {}
    for index, item in enumerate(questions, start=1):
        label = f"route[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} is invalid")
            continue
        question_id = str(item.get("question_id", "")).strip()
        if not question_id or question_id in seen:
            errors.append(f"{label}: question_id is empty or duplicated")
            continue
        seen.add(question_id)
        label = question_id
        profile = str(item.get("evidence_profile", "")).strip().lower()
        if profile not in PROFILE_CHECKS:
            errors.append(f"{label}: invalid evidence_profile")
        if expected_profiles.get(question_id) != profile:
            errors.append(f"{label}: evidence_profile does not match model_selection.json")

        reviews = item.get("reviews")
        if not isinstance(reviews, dict):
            errors.append(f"{label}: reviews is missing")
            reviews = {}
        missing_reviews = REVIEW_KINDS - set(reviews)
        if missing_reviews:
            errors.append(f"{label}: review routes are missing: {', '.join(sorted(missing_reviews))}")
        for kind in sorted(REVIEW_KINDS & set(reviews)):
            decision = reviews.get(kind)
            if not isinstance(decision, dict):
                errors.append(f"{label}/{kind}: route is invalid")
                continue
            status = str(decision.get("status", "")).strip().lower()
            if status not in {"required", "not_applicable"}:
                errors.append(f"{label}/{kind}: status must be required or not_applicable")
            if kind in {"scientific", "implementation", "uncertainty", "claims"} and status != "required":
                errors.append(f"{label}/{kind}: review is always required")
            if kind == "statistical":
                routed_statistics[question_id] = status
                if profile in STATISTICS_REQUIRED and status != "required":
                    errors.append(f"{label}: statistical review is required for {profile}")
                if status == "not_applicable" and not nonempty(decision.get("rationale")):
                    errors.append(f"{label}: statistical not_applicable route needs an internal rationale")

        focus = item.get("uncertainty_focus")
        if not isinstance(focus, list) or not focus:
            errors.append(f"{label}: uncertainty_focus is empty")
        else:
            invalid = {str(value).strip() for value in focus} - UNCERTAINTY_FOCI
            if invalid:
                errors.append(f"{label}: invalid uncertainty focus: {', '.join(sorted(invalid))}")

        implementation = item.get("implementation_assumption_check")
        if not isinstance(implementation, dict):
            errors.append(f"{label}: implementation_assumption_check is missing")
        else:
            implementation_status = str(implementation.get("status", "")).strip().lower()
            if routed and implementation_status != "pass":
                errors.append(f"{label}: implementation-assumption check did not pass")
            elif not routed and implementation_status not in {"pending", "pass"}:
                errors.append(f"{label}: draft implementation-assumption status must be pending or pass")
            if not nonempty(implementation.get("summary")):
                errors.append(f"{label}: implementation-assumption summary is empty")
            if routed or implementation_status == "pass":
                errors.extend(artifact_errors(workspace, implementation, f"{label} implementation-assumption check"))

    missing = set(expected_profiles) - seen
    extra = seen - set(expected_profiles)
    if missing:
        errors.append(f"review route is missing questions: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"review route contains unknown questions: {', '.join(sorted(extra))}")

    report = {
        "status": "pass" if not errors else "block",
        "question_count": len(questions),
        "statistical_routes": routed_statistics,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "review_route_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate adaptive scientific-review routing.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_review_route(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
