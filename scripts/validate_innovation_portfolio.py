#!/usr/bin/env python3
"""Validate an evidence-backed portfolio of paper innovation claims."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evidence_utils import artifact_errors


EXPLORATION_TARGETS = {
    "standard": (6, 4, 3, 1),
    "championship": (8, 5, 4, 1),
}
INNOVATION_AXES = {
    "problem_formulation",
    "state_representation",
    "assumption_mechanism",
    "problem_decomposition",
    "objective_constraint",
    "parameter_inference",
    "solution_strategy",
    "data_use",
    "validation",
    "decision_explanation",
    "model_structure",
    "model_fusion",
}
JURY_FIELDS = (
    "problem_fit",
    "evidence_strength",
    "necessity",
    "novelty",
    "robustness",
    "parsimony",
    "communication",
)
TRUE_VALUES = {"true", "yes", "1", "required"}
NONE_VALUES = {"", "none", "no", "0", "not_applicable", "n/a"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def required(row: dict[str, str], fields: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}: {field} is empty" for field in fields if not row.get(field, "").strip()]


def is_true(value: str) -> bool:
    return value.strip().lower() in TRUE_VALUES


def validate_experiment(workspace: Path, row: dict[str, str], known_claims: set[str]) -> list[str]:
    experiment_id = row.get("experiment_id", "").strip() or "experiment row"
    errors = required(
        row,
        (
            "claim_id", "experiment_id", "test_type", "hypothesis", "baseline",
            "dataset_or_fixture", "command", "seed", "metric", "baseline_value",
            "changed_value", "artifact_path", "sha256", "checked_at", "reviewer", "decision",
        ),
        experiment_id,
    )
    if row.get("claim_id", "").strip() not in known_claims:
        errors.append(f"{experiment_id}: experiment references unknown claim")
    if row.get("test_type", "").strip().lower() not in {"baseline_failure", "semantic_fidelity", "falsification", "ablation", "robustness"}:
        errors.append(f"{experiment_id}: invalid test_type")
    if row.get("decision", "").strip().lower() not in {"pass", "fail", "inconclusive"}:
        errors.append(f"{experiment_id}: invalid decision")
    errors.extend(
        artifact_errors(
            workspace,
            row,
            experiment_id,
            check_field="command",
        )
    )
    return errors


def validate_innovation_portfolio(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = json.loads((workspace / "competition_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
        errors.append("competition manifest is missing or invalid")
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode not in EXPLORATION_TARGETS:
        errors.append(f"unknown innovation mode: {mode}")
    target_claims, target_axes, target_scouts, target_analogies = EXPLORATION_TARGETS.get(
        mode, EXPLORATION_TARGETS["standard"]
    )

    folder = workspace / "innovation"
    claims = read_csv(folder / "claim_portfolio.csv")
    novelty = read_csv(folder / "novelty_audit.csv")
    experiments = read_csv(folder / "claim_experiments.csv")
    findings = read_csv(folder / "critic_findings.csv")
    selection = read_csv(folder / "selection.csv")

    by_claim: dict[str, dict[str, str]] = {}
    axes: set[str] = set()
    scouts: set[str] = set()
    analogies: set[str] = set()
    for index, row in enumerate(claims, start=2):
        claim_id = row.get("claim_id", "").strip()
        label = claim_id or f"claim row {index}"
        errors.extend(required(row, ("claim_id", "subproblem", "innovation_axis", "status"), label))
        if not claim_id:
            continue
        if claim_id in by_claim:
            errors.append(f"duplicate claim_id: {claim_id}")
        by_claim[claim_id] = row
        axis = row.get("innovation_axis", "").strip().lower()
        if axis not in INNOVATION_AXES:
            errors.append(f"{claim_id}: invalid innovation_axis")
        else:
            axes.add(axis)
        scout = row.get("scout_id", "").strip()
        analogy = row.get("analogy_source", "").strip()
        if scout:
            scouts.add(scout)
        if analogy:
            analogies.add(analogy)
        if row.get("status", "").strip().lower() not in {"draft", "exploring", "rejected", "supported"}:
            errors.append(f"{claim_id}: invalid claim status")

    if len(claims) < target_claims:
        warnings.append(f"search breadth: {len(claims)} claims; {mode} target is {target_claims}")
    if len(axes) < target_axes:
        warnings.append(f"search breadth: {len(axes)} innovation axes; {mode} target is {target_axes}")
    if len(scouts) < target_scouts:
        warnings.append(f"search breadth: {len(scouts)} scouts; {mode} target is {target_scouts}")
    if len(analogies) < target_analogies:
        warnings.append(f"search breadth: {len(analogies)} cross-domain analogies; {mode} target is {target_analogies}")

    promoted = [row for row in selection if row.get("decision", "").strip().lower() == "promote"]
    if not promoted:
        warnings.append("no innovation claim was promoted; the paper must not make an innovation claim")
    promoted_ids: set[str] = set()
    primary_ids: set[str] = set()
    for index, row in enumerate(promoted, start=2):
        claim_id = row.get("claim_id", "").strip()
        label = claim_id or f"selection row {index}"
        errors.extend(
            required(
                row,
                (
                    "claim_id", "paper_role", "risks", "artifact_path", "sha256",
                    "command_or_check", "checked_at", "reviewer", *JURY_FIELDS,
                ),
                label,
            )
        )
        if claim_id not in by_claim:
            errors.append(f"selection references unknown claim: {claim_id}")
            continue
        if claim_id in promoted_ids:
            errors.append(f"claim promoted more than once: {claim_id}")
        promoted_ids.add(claim_id)
        role = row.get("paper_role", "").strip().lower()
        if role not in {"primary", "supporting"}:
            errors.append(f"{claim_id}: paper_role must be primary or supporting")
        if role == "primary":
            primary_ids.add(claim_id)
        for field in JURY_FIELDS:
            try:
                score = int(row.get(field, ""))
                if not 1 <= score <= 5:
                    raise ValueError
            except ValueError:
                errors.append(f"{claim_id}: {field} must be an integer from 1 to 5")
        errors.extend(artifact_errors(workspace, row, f"{claim_id} selection"))
    if promoted_ids and not primary_ids:
        errors.append("at least one promoted claim must have paper_role=primary")

    verified_experiments: dict[str, list[dict[str, str]]] = {}
    for row in experiments:
        if row.get("status", "").strip().lower() != "verified":
            continue
        local_errors = validate_experiment(workspace, row, set(by_claim))
        errors.extend(local_errors)
        if not local_errors and row.get("decision", "").strip().lower() == "pass":
            verified_experiments.setdefault(row.get("claim_id", "").strip(), []).append(row)

    novelty_by_claim: dict[str, list[dict[str, str]]] = {}
    for row in novelty:
        novelty_by_claim.setdefault(row.get("claim_id", "").strip(), []).append(row)
    findings_by_claim: dict[str, list[dict[str, str]]] = {}
    for row in findings:
        findings_by_claim.setdefault(row.get("claim_id", "").strip(), []).append(row)

    common_claim_fields = (
        "claim_id", "subproblem", "innovation_axis", "problem_structure", "reasoning_path",
        "proposed_change",
        "mathematical_expression", "why_this_change", "minimality_argument", "extra_complexity",
        "extra_complexity_justified", "nearest_precedent", "difference_from_precedent",
        "expected_effect", "falsification_test", "ablation_required", "complexity_cost",
        "paper_location", "is_fusion", "status",
    )
    for claim_id in sorted(promoted_ids):
        claim = by_claim[claim_id]
        errors.extend(required(claim, common_claim_fields, claim_id))
        if claim.get("status", "").strip().lower() != "supported":
            errors.append(f"{claim_id}: promoted claim is not marked supported")
        reasoning_path = claim.get("reasoning_path", "").strip().lower()
        if reasoning_path not in {"failure_driven", "faithful_formulation"}:
            errors.append(f"{claim_id}: reasoning_path must be failure_driven or faithful_formulation")
        elif reasoning_path == "failure_driven":
            errors.extend(
                required(
                    claim,
                    (
                        "baseline", "baseline_failure", "failure_evidence_artifact",
                        "failure_evidence_sha256", "failure_check", "failure_checked_at",
                        "change_targets_failure",
                    ),
                    claim_id,
                )
            )
            if not is_true(claim.get("change_targets_failure", "")):
                errors.append(f"{claim_id}: proposed change is not explicitly linked to the baseline failure")
            errors.extend(
                artifact_errors(
                    workspace,
                    claim,
                    f"{claim_id} baseline failure",
                    path_field="failure_evidence_artifact",
                    sha_field="failure_evidence_sha256",
                    check_field="failure_check",
                    time_field="failure_checked_at",
                )
            )
        elif reasoning_path == "faithful_formulation":
            errors.extend(
                required(
                    claim,
                    (
                        "semantic_requirement", "faithfulness_argument", "simplified_benchmark",
                        "faithfulness_evidence_artifact", "faithfulness_evidence_sha256",
                        "faithfulness_check", "faithfulness_checked_at",
                    ),
                    claim_id,
                )
            )
            errors.extend(
                artifact_errors(
                    workspace,
                    claim,
                    f"{claim_id} semantic-fidelity evidence",
                    path_field="faithfulness_evidence_artifact",
                    sha_field="faithfulness_evidence_sha256",
                    check_field="faithfulness_check",
                    time_field="faithfulness_checked_at",
                )
            )

        extra_complexity = claim.get("extra_complexity", "").strip().lower()
        needs_ablation = is_true(claim.get("ablation_required", "")) or extra_complexity not in NONE_VALUES
        if extra_complexity not in NONE_VALUES and not is_true(claim.get("extra_complexity_justified", "")):
            errors.append(f"{claim_id}: extra complexity is not justified")
        if is_true(claim.get("is_fusion", "")):
            errors.extend(required(claim, ("component_failure_map", "mathematical_interface"), claim_id))
            needs_ablation = True

        claim_tests = verified_experiments.get(claim_id, [])
        test_types = {row.get("test_type", "").strip().lower() for row in claim_tests}
        if "falsification" not in test_types:
            errors.append(f"{claim_id}: no verified falsification test")
        if reasoning_path == "faithful_formulation" and "semantic_fidelity" not in test_types:
            errors.append(f"{claim_id}: faithful formulation requires a verified semantic_fidelity test")
        if needs_ablation and "ablation" not in test_types:
            errors.append(f"{claim_id}: complexity/fusion requires a verified ablation")

        audits = novelty_by_claim.get(claim_id, [])
        if len(audits) != 1:
            errors.append(f"{claim_id}: exactly one novelty audit is required; found {len(audits)}")
        else:
            audit = audits[0]
            errors.extend(
                required(
                    audit,
                    (
                        "claim_id", "search_queries", "primary_sources", "nearest_precedent",
                        "difference", "evidence_locator", "novelty_class", "metadata_status",
                        "support_status", "correction_retraction_status", "source_artifact",
                        "source_sha256", "verification_command", "checked_at", "auditor", "decision",
                    ),
                    claim_id,
                )
            )
            if audit.get("novelty_class", "").strip().lower() not in {
                "known_baseline", "adaptation", "combination", "problem_specific"
            }:
                errors.append(f"{claim_id}: novelty_class is invalid or unverified")
            if audit.get("metadata_status", "").strip().lower() != "verified":
                errors.append(f"{claim_id}: novelty metadata is not verified")
            if audit.get("support_status", "").strip().lower() != "supported":
                errors.append(f"{claim_id}: novelty difference is not supported")
            if audit.get("correction_retraction_status", "").strip().lower() not in {
                "clear", "checked", "not_applicable", "corrected_version_used"
            }:
                errors.append(f"{claim_id}: correction/retraction status is not cleared")
            if audit.get("decision", "").strip().lower() not in {"pass", "continue", "promote"}:
                errors.append(f"{claim_id}: novelty audit does not permit promotion")
            errors.extend(
                artifact_errors(
                    workspace,
                    audit,
                    f"{claim_id} novelty audit",
                    path_field="source_artifact",
                    sha_field="source_sha256",
                    check_field="verification_command",
                )
            )

        claim_findings = findings_by_claim.get(claim_id, [])
        if not claim_findings:
            errors.append(f"{claim_id}: critic review is missing")
        for finding in claim_findings:
            finding_id = finding.get("finding_id", "").strip() or claim_id
            errors.extend(
                required(
                    finding,
                    (
                        "finding_id", "claim_id", "attack_surface", "severity", "finding",
                        "repair_or_falsifier", "status", "artifact_path", "sha256",
                        "command_or_check", "checked_at", "reviewer",
                    ),
                    finding_id,
                )
            )
            severity = finding.get("severity", "").strip().lower()
            status = finding.get("status", "").strip().lower()
            if severity not in {"blocking", "major", "minor", "clear"}:
                errors.append(f"{finding_id}: invalid critic severity")
            if status not in {"open", "closed", "clear"}:
                errors.append(f"{finding_id}: invalid critic status")
            if severity == "blocking" and status != "closed":
                errors.append(f"{finding_id}: blocking critic finding remains open")
            if severity == "major" and status not in {"closed", "clear"}:
                errors.append(f"{finding_id}: major critic finding remains open")
            errors.extend(artifact_errors(workspace, finding, finding_id))

    report = {
        "status": "pass" if not errors else "block",
        "mode": mode,
        "claim_count": len(claims),
        "innovation_axis_count": len(axes),
        "scout_count": len(scouts),
        "analogy_count": len(analogies),
        "promoted_claims": sorted(promoted_ids),
        "primary_claims": sorted(primary_ids),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "innovation" / "innovation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


validate_innovation_claims = validate_innovation_portfolio


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paper innovation claims and their evidence chains.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_innovation_portfolio(Path(args.workspace).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
