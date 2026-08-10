#!/usr/bin/env python3
"""Validate question-level model decisions against an adaptive evidence profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_utils import artifact_errors


PROFILE_CHECKS = {
    "analytical": {"derivation", "boundary", "special_case"},
    "deterministic_numerical": {"convergence", "discretization", "cross_method"},
    "optimization": {"feasibility", "boundary", "optimality_or_search", "sensitivity"},
    "statistical": {"assumptions", "residual_or_fit", "uncertainty", "out_of_sample"},
    "simulation": {"calibration", "convergence", "stochastic_uncertainty", "scenario_validation"},
    "machine_learning": {"leakage", "out_of_sample", "calibration_or_error", "robustness"},
}

# These checks define whether the evidence profile has actually been exercised. Other
# profile checks may be marked not_applicable with an internal rationale.
MANDATORY_PASS = {
    "analytical": {"derivation"},
    "deterministic_numerical": {"convergence", "discretization"},
    "optimization": {"feasibility", "optimality_or_search"},
    "statistical": {"assumptions", "uncertainty", "out_of_sample"},
    "simulation": {"convergence", "stochastic_uncertainty", "scenario_validation"},
    "machine_learning": {"leakage", "out_of_sample", "calibration_or_error"},
}


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_checks(
    checks: object,
    profile: str,
    label: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(checks, list):
        errors.append(f"{label}: verification_checks is not an array")
        return
    by_type: dict[str, dict[str, object]] = {}
    for item in checks:
        if not isinstance(item, dict):
            errors.append(f"{label}: invalid verification check")
            continue
        check_type = str(item.get("check_type", "")).strip().lower()
        if not check_type or check_type in by_type:
            errors.append(f"{label}: verification check type is empty or duplicated")
            continue
        by_type[check_type] = item
        status = str(item.get("status", "")).strip().lower()
        if status not in {"pass", "not_applicable"}:
            errors.append(f"{label}/{check_type}: status must be pass or not_applicable")
        if not nonempty(item.get("summary")):
            errors.append(f"{label}/{check_type}: summary is empty")

    expected = PROFILE_CHECKS.get(profile, set())
    missing = expected - set(by_type)
    if missing:
        errors.append(f"{label}: evidence profile checks are missing: {', '.join(sorted(missing))}")
    unexpected = set(by_type) - expected
    if unexpected:
        warnings.append(f"{label}: extra checks outside {profile} profile: {', '.join(sorted(unexpected))}")
    for check_type in sorted(expected & set(by_type)):
        status = str(by_type[check_type].get("status", "")).strip().lower()
        if check_type in MANDATORY_PASS.get(profile, set()) and status != "pass":
            errors.append(f"{label}/{check_type}: mandatory profile check did not pass")
        elif status == "not_applicable":
            warnings.append(f"{label}/{check_type}: marked not_applicable internally")


def validate_model_selection(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load(workspace / "synthesis" / "model_selection.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 2:
        errors.append("model_selection.json schema_version must be 2")
    frozen = document.get("status") == "frozen"
    if not frozen:
        errors.append("model selection is not frozen")
    questions = document.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("model selection has no core questions")
        questions = []

    seen: set[str] = set()
    profile_counts: dict[str, int] = {}
    for index, question in enumerate(questions, start=1):
        label = f"question[{index}]"
        if not isinstance(question, dict):
            errors.append(f"{label} is not an object")
            continue
        question_id = str(question.get("question_id", "")).strip()
        if not question_id:
            errors.append(f"{label}: question_id is empty")
        elif question_id in seen:
            errors.append(f"{label}: duplicate question_id {question_id}")
        seen.add(question_id)
        label = question_id or label

        profile = str(question.get("evidence_profile", "")).strip().lower()
        if profile not in PROFILE_CHECKS:
            errors.append(f"{label}: invalid evidence_profile")
        else:
            profile_counts[profile] = profile_counts.get(profile, 0) + 1

        structure = question.get("problem_structure")
        if not isinstance(structure, dict):
            errors.append(f"{label}: problem_structure is missing")
        else:
            for field in ("target", "data", "constraints", "validation_anchor"):
                if not nonempty(structure.get(field)):
                    errors.append(f"{label}: problem_structure.{field} is empty")

        candidates = question.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            errors.append(f"{label}: no candidate model is recorded")
            candidates = []
        candidate_ids: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                errors.append(f"{label}: invalid candidate record")
                continue
            model_id = str(candidate.get("model_id", "")).strip()
            if not model_id or model_id in candidate_ids:
                errors.append(f"{label}: candidate model_id is empty or duplicated")
            candidate_ids.add(model_id)
            if not nonempty(candidate.get("pre_fit_rationale")):
                errors.append(f"{label}/{model_id}: pre_fit_rationale is empty")

        baseline_id = str(question.get("strong_baseline_id", "")).strip()
        if baseline_id not in candidate_ids:
            errors.append(f"{label}: strong_baseline_id is not a candidate")
        if not frozen:
            warnings.append(f"{label}: draft model decision; final evidence, selection and rejection checks are deferred")
            continue

        selected_id = str(question.get("selected_model_id", "")).strip()
        if selected_id not in candidate_ids:
            errors.append(f"{label}: selected_model_id is not a candidate")
        if not nonempty(question.get("selection_rationale")):
            errors.append(f"{label}: selection_rationale is empty")
        if not nonempty(question.get("complexity_tradeoff")):
            errors.append(f"{label}: complexity_tradeoff is empty")

        evidence = question.get("post_fit_evidence")
        evidence_by_model: set[str] = set()
        if not isinstance(evidence, list):
            evidence = []
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"{label}: invalid post_fit_evidence record")
                continue
            model_id = str(item.get("model_id", "")).strip()
            evidence_label = f"{label}/{model_id or '<empty>'}"
            if model_id not in candidate_ids:
                errors.append(f"{label}: evidence references unknown model {model_id or '<empty>'}")
            if model_id in evidence_by_model:
                errors.append(f"{label}: duplicate post-fit evidence for {model_id}")
            evidence_by_model.add(model_id)
            if not nonempty(item.get("result_summary")):
                errors.append(f"{evidence_label}: result_summary is empty")
            if profile in PROFILE_CHECKS:
                validate_checks(item.get("verification_checks"), profile, evidence_label, errors, warnings)
            errors.extend(artifact_errors(workspace, item, f"{evidence_label} model evidence"))
        for required_id in {baseline_id, selected_id} - {""}:
            if required_id not in evidence_by_model:
                errors.append(f"{label}: no post-fit evidence for {required_id}")

        rejected = question.get("rejected_models")
        rejected_ids: set[str] = set()
        if isinstance(rejected, list):
            for item in rejected:
                if not isinstance(item, dict):
                    errors.append(f"{label}: invalid rejected model record")
                    continue
                model_id = str(item.get("model_id", "")).strip()
                if model_id not in candidate_ids:
                    errors.append(f"{label}: rejection references unknown model {model_id or '<empty>'}")
                if model_id == selected_id:
                    errors.append(f"{label}: selected model is also rejected")
                rejected_ids.add(model_id)
                if not nonempty(item.get("reason")):
                    errors.append(f"{label}/{model_id}: rejection reason is empty")
        missing_rejections = candidate_ids - {selected_id} - rejected_ids
        if missing_rejections:
            errors.append(f"{label}: rejected candidates lack reasons: {', '.join(sorted(missing_rejections))}")
        if len(candidate_ids) == 1:
            warnings.append(f"{label}: only the strong baseline was evaluated; acceptable if alternatives were unnecessary")

    report = {
        "status": "pass" if not errors else "block",
        "question_count": len(questions),
        "evidence_profiles": profile_counts,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "model_selection_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate adaptive evidence-backed model selection.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_model_selection(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
