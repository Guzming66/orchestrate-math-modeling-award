#!/usr/bin/env python3
"""Validate the evidence chain for an innovation portfolio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


THRESHOLDS = {
    "fast": (5, 3, 1, 2, 2),
    "standard": (8, 4, 2, 4, 3),
    "championship": (10, 5, 2, 5, 4),
}
SCORE_FIELDS = (
    "problem_fit",
    "structural_novelty",
    "expected_gain",
    "interpretability",
    "implementation_feasibility",
    "data_sufficiency",
    "validation_strength",
    "judge_readability",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required(row: dict[str, str], fields: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}: {field} is empty" for field in fields if not row.get(field, "").strip()]


def validate_innovation_portfolio(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = workspace / "competition_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
        errors.append("competition manifest is missing or invalid")
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode not in THRESHOLDS:
        errors.append(f"unknown innovation mode: {mode}")
    minimum_candidates, minimum_families, minimum_analogies, minimum_scouts, minimum_experiments = THRESHOLDS.get(mode, THRESHOLDS["standard"])
    branch_count = len(manifest.get("branches", [])) if isinstance(manifest.get("branches"), list) else 3

    folder = workspace / "innovation"
    candidates = read_csv(folder / "candidate_portfolio.csv")
    novelty = read_csv(folder / "novelty_audit.csv")
    experiments = read_csv(folder / "feasibility_experiments.csv")
    findings = read_csv(folder / "critic_findings.csv")
    selection = read_csv(folder / "selection.csv")

    if len(candidates) < minimum_candidates:
        errors.append(f"innovation portfolio has {len(candidates)} candidates; {mode} requires at least {minimum_candidates}")
    candidate_ids: set[str] = set()
    families: set[str] = set()
    analogies: set[str] = set()
    scouts: set[str] = set()
    by_candidate: dict[str, dict[str, str]] = {}
    candidate_fields = (
        "candidate_id", "scout_id", "origin_lens", "problem_structure", "mechanism_change",
        "innovation_unit", "mechanism_family", "mathematical_formulation", "baseline",
        "data_needs", "validation_plan", "cheap_falsifier", "failure_condition",
        "complexity_justification", "risk_role", "status",
    )
    for index, row in enumerate(candidates, start=2):
        label = f"candidate row {index}"
        errors.extend(required(row, candidate_fields, label))
        candidate_id = row.get("candidate_id", "").strip()
        if not candidate_id:
            continue
        if candidate_id in candidate_ids:
            errors.append(f"duplicate candidate_id: {candidate_id}")
        candidate_ids.add(candidate_id)
        by_candidate[candidate_id] = row
        scouts.add(row.get("scout_id", "").strip())
        families.add(row.get("mechanism_family", "").strip())
        analogy = row.get("cross_domain_source", "").strip()
        if analogy:
            analogies.add(analogy)
        if row.get("risk_role", "").strip().lower() not in {"safe", "balanced", "stretch"}:
            errors.append(f"{candidate_id}: invalid risk_role")
        if row.get("status", "").strip().lower() not in {"candidate", "rejected", "survivor"}:
            errors.append(f"{candidate_id}: invalid candidate status")
    families.discard("")
    scouts.discard("")
    if len(scouts) < minimum_scouts:
        errors.append(f"innovation portfolio has {len(scouts)} independent scouts; {mode} requires at least {minimum_scouts}")
    if len(families) < minimum_families:
        errors.append(f"innovation portfolio has {len(families)} mechanism families; {mode} requires at least {minimum_families}")
    if len(analogies) < minimum_analogies:
        errors.append(f"innovation portfolio has {len(analogies)} cross-domain sources; {mode} requires at least {minimum_analogies}")

    promoted = [row for row in selection if row.get("decision", "").strip().lower() == "promote"]
    maximum_promoted = min(3, max(2, branch_count))
    if not 2 <= len(promoted) <= maximum_promoted:
        errors.append(f"selection must promote 2-{maximum_promoted} candidates; found {len(promoted)}")
    promoted_ids: set[str] = set()
    ranks: set[int] = set()
    for index, row in enumerate(promoted, start=2):
        candidate_id = row.get("candidate_id", "").strip()
        label = candidate_id or f"selection row {index}"
        errors.extend(required(row, ("candidate_id", "rank", "risks", "decision_evidence", "reviewer", *SCORE_FIELDS), label))
        if candidate_id not in by_candidate:
            errors.append(f"selection references unknown candidate: {candidate_id}")
            continue
        if candidate_id in promoted_ids:
            errors.append(f"candidate promoted more than once: {candidate_id}")
        promoted_ids.add(candidate_id)
        if by_candidate[candidate_id].get("status", "").strip().lower() != "survivor":
            errors.append(f"{candidate_id}: promoted candidate is not marked survivor")
        try:
            rank = int(row.get("rank", ""))
            if rank in ranks:
                errors.append(f"duplicate promoted rank: {rank}")
            ranks.add(rank)
        except ValueError:
            errors.append(f"{candidate_id}: rank is not an integer")
        for field in SCORE_FIELDS:
            try:
                score = int(row.get(field, ""))
                if not 1 <= score <= 5:
                    raise ValueError
            except ValueError:
                errors.append(f"{candidate_id}: {field} must be an integer from 1 to 5")
    if mode != "fast" and promoted_ids:
        roles = {by_candidate[item].get("risk_role", "").strip().lower() for item in promoted_ids if item in by_candidate}
        if "safe" not in roles or "stretch" not in roles:
            errors.append(f"{mode} selection must include both safe and stretch candidates")

    novelty_by_id = {row.get("candidate_id", "").strip(): row for row in novelty}
    verified_experiment_candidates: set[str] = set()
    for experiment in experiments:
        if experiment.get("status", "").strip().lower() != "verified":
            continue
        experiment_id = experiment.get("experiment_id", "").strip() or "experiment row"
        local_errors = required(
            experiment,
            (
                "candidate_id", "experiment_id", "hypothesis", "baseline", "dataset_or_fixture",
                "command", "seed", "metric", "baseline_value", "candidate_value", "result_artifact",
                "result_sha256", "reviewer", "decision",
            ),
            experiment_id,
        )
        candidate_id = experiment.get("candidate_id", "").strip()
        if candidate_id not in by_candidate:
            local_errors.append(f"{experiment_id}: experiment references unknown candidate")
        if experiment.get("decision", "").strip().lower() not in {"pass", "continue", "promote"}:
            local_errors.append(f"{experiment_id}: experiment decision does not permit promotion")
        relative = experiment.get("result_artifact", "").replace("\\", "/").strip()
        path = (workspace / relative).resolve()
        try:
            path.relative_to(workspace)
        except ValueError:
            local_errors.append(f"{experiment_id}: result artifact escapes workspace")
        else:
            if not path.is_file():
                local_errors.append(f"{experiment_id}: result artifact is missing")
            elif experiment.get("result_sha256", "").strip().lower() != sha256_file(path):
                local_errors.append(f"{experiment_id}: result sha256 does not match")
        errors.extend(local_errors)
        if not local_errors and candidate_id:
            verified_experiment_candidates.add(candidate_id)
    findings_by_id: dict[str, list[dict[str, str]]] = {}
    for row in findings:
        findings_by_id.setdefault(row.get("candidate_id", "").strip(), []).append(row)

    for candidate_id in sorted(promoted_ids):
        audit = novelty_by_id.get(candidate_id)
        if audit is None:
            errors.append(f"{candidate_id}: novelty audit is missing")
        else:
            errors.extend(required(audit, ("claim", "primary_sources", "nearest_precedent", "difference", "evidence_locator", "novelty_class", "metadata_status", "support_status", "accessed_at", "auditor", "decision"), candidate_id))
            novelty_class = audit.get("novelty_class", "").strip().lower()
            if novelty_class not in {"known_baseline", "adaptation", "combination", "problem_specific"}:
                errors.append(f"{candidate_id}: novelty_class is unverified or invalid")
            if audit.get("metadata_status", "").strip().lower() != "verified":
                errors.append(f"{candidate_id}: novelty metadata is not verified")
            if audit.get("support_status", "").strip().lower() != "supported":
                errors.append(f"{candidate_id}: novelty difference is not supported")
            if audit.get("decision", "").strip().lower() not in {"continue", "pass", "promote"}:
                errors.append(f"{candidate_id}: novelty audit decision does not permit promotion")

        if candidate_id not in verified_experiment_candidates:
            errors.append(f"{candidate_id}: no verified feasibility experiment")

        candidate_findings = findings_by_id.get(candidate_id, [])
        if not candidate_findings:
            errors.append(f"{candidate_id}: critic review is missing")
        for finding in candidate_findings:
            finding_id = finding.get("finding_id", "").strip() or candidate_id
            errors.extend(required(finding, ("finding_id", "attack_surface", "severity", "finding", "evidence", "repair_or_falsifier", "status", "reviewer"), finding_id))
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

    if len(verified_experiment_candidates) < minimum_experiments:
        errors.append(
            f"innovation portfolio has verified experiments for {len(verified_experiment_candidates)} candidates; "
            f"{mode} requires at least {minimum_experiments}"
        )
    if ranks and ranks != set(range(1, len(promoted) + 1)):
        errors.append("promoted ranks must be contiguous starting at 1")

    report = {
        "status": "pass" if not errors else "block",
        "mode": mode,
        "candidate_count": len(candidates),
        "mechanism_family_count": len(families),
        "cross_domain_source_count": len(analogies),
        "independent_scout_count": len(scouts),
        "verified_experiment_candidate_count": len(verified_experiment_candidates),
        "promoted_candidates": sorted(promoted_ids),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "innovation" / "innovation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate innovation candidates, evidence, experiments, and jury selection.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_innovation_portfolio(Path(args.workspace).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
