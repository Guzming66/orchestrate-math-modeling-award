#!/usr/bin/env python3
"""Migrate a v7 workspace to the v8 innovation-claim schema without deleting legacy files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


TARGET_VERSION = 8
CLAIM_FIELDS = [
    "claim_id", "subproblem", "scout_id", "innovation_axis", "problem_structure",
    "baseline", "baseline_failure", "failure_evidence_artifact", "failure_evidence_sha256",
    "failure_check", "failure_checked_at", "proposed_change", "change_targets_failure",
    "mathematical_expression", "why_this_change", "minimality_argument", "extra_complexity",
    "extra_complexity_justified", "nearest_precedent", "difference_from_precedent",
    "expected_effect", "falsification_test", "ablation_required", "complexity_cost",
    "paper_location", "analogy_source", "is_fusion", "component_failure_map",
    "mathematical_interface", "status", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_if_missing(path: Path, fields: list[str], rows: list[dict[str, str]] | None = None) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def replace_legacy_csv(path: Path, fields: list[str], legacy_dir: Path) -> None:
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            current = csv.DictReader(handle).fieldnames or []
        if "claim_id" in current:
            return
        legacy_dir.mkdir(parents=True, exist_ok=True)
        backup = legacy_dir / path.name
        if not backup.exists():
            shutil.copy2(path, backup)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerow(fields)


def extend_csv_fields(path: Path, fields: list[str], backup: Path) -> None:
    """Add schema fields without discarding legacy rows; new evidence fields stay blank."""
    if not path.is_file():
        write_csv_if_missing(path, fields)
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        current = reader.fieldnames or []
        rows = list(reader)
    if current == fields:
        return
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(path, backup)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def migrate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = workspace / "competition_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "block", "errors": ["competition manifest is missing or invalid"], "warnings": []}
    current = manifest.get("workflow_version")
    if current == TARGET_VERSION:
        return {"status": "pass", "from_version": current, "to_version": TARGET_VERSION, "errors": [], "warnings": ["workspace is already current"]}
    if current != 7:
        return {"status": "block", "errors": [f"no migration path from workflow_version {current}"], "warnings": []}

    legacy = read_csv(workspace / "innovation" / "candidate_portfolio.csv")
    migrated: list[dict[str, str]] = []
    axis_map = {
        "mechanism": "assumption_mechanism",
        "uncertainty": "parameter_inference",
        "optimization": "solution_strategy",
        "cross-domain": "problem_formulation",
    }
    for row in legacy:
        status = row.get("status", "").strip().lower()
        migrated.append(
            {
                "claim_id": row.get("candidate_id", ""),
                "subproblem": "all",
                "scout_id": row.get("scout_id", ""),
                "innovation_axis": axis_map.get(row.get("origin_lens", "").strip().lower(), "model_structure"),
                "problem_structure": row.get("problem_structure", ""),
                "baseline": row.get("baseline", ""),
                "baseline_failure": "",
                "proposed_change": row.get("mechanism_change", ""),
                "mathematical_expression": row.get("mathematical_formulation", ""),
                "why_this_change": row.get("innovation_unit", ""),
                "minimality_argument": row.get("complexity_justification", ""),
                "expected_effect": row.get("validation_plan", ""),
                "falsification_test": row.get("cheap_falsifier", ""),
                "analogy_source": row.get("cross_domain_source", ""),
                "status": "rejected" if status == "rejected" else "exploring",
                "notes": "Migrated from v7; baseline failure and artifact evidence require manual reconstruction.",
            }
        )
    write_csv_if_missing(workspace / "innovation" / "claim_portfolio.csv", CLAIM_FIELDS, migrated)
    for relative, content in (
        ("innovation/baseline_failure_map.md", "# Baseline failure map\n\nReconstruct from artifact-backed tests; do not infer failure from v7 route labels.\n"),
        ("innovation/opportunity_map.md", "# Innovation opportunity map\n\nMap verified baseline failures to minimal changes across innovation axes.\n"),
    ):
        path = workspace / relative
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    write_csv_if_missing(
        workspace / "innovation" / "claim_experiments.csv",
        [
            "claim_id", "experiment_id", "test_type", "component", "hypothesis", "baseline",
            "dataset_or_fixture", "command", "seed", "metric", "baseline_value", "changed_value",
            "artifact_path", "sha256", "checked_at", "status", "reviewer", "decision", "notes",
        ],
    )
    legacy_dir = workspace / "innovation" / "legacy_v7"
    replace_legacy_csv(
        workspace / "innovation" / "novelty_audit.csv",
        [
            "claim_id", "search_queries", "primary_sources", "nearest_precedent", "difference",
            "evidence_locator", "novelty_class", "metadata_status", "support_status",
            "correction_retraction_status", "source_artifact", "source_sha256",
            "verification_command", "checked_at", "auditor", "decision", "notes",
        ],
        legacy_dir,
    )
    replace_legacy_csv(
        workspace / "innovation" / "critic_findings.csv",
        [
            "finding_id", "claim_id", "attack_surface", "severity", "finding",
            "repair_or_falsifier", "status", "artifact_path", "sha256", "command_or_check",
            "checked_at", "reviewer", "notes",
        ],
        legacy_dir,
    )
    replace_legacy_csv(
        workspace / "innovation" / "selection.csv",
        [
            "claim_id", "decision", "paper_role", "problem_fit", "evidence_strength", "necessity",
            "novelty", "robustness", "parsimony", "communication", "risks", "artifact_path",
            "sha256", "command_or_check", "checked_at", "reviewer", "notes",
        ],
        legacy_dir,
    )
    write_csv_if_missing(
        workspace / "synthesis" / "innovation_claims.csv",
        [
            "claim_id", "claim_sentence", "problem_structure", "baseline_failure", "method_change",
            "evidence_result_ids", "novelty_source_keys", "paper_section", "paper_anchor",
            "figure_or_table", "claim_strength", "status", "artifact_path", "sha256",
            "command_or_check", "checked_at", "reviewer", "notes",
        ],
    )
    extend_csv_fields(
        workspace / "audits" / "citations" / "citation_ledger.csv",
        [
            "claim_id", "claim_location", "claim_text", "citation_key", "source_class",
            "primary_source", "identifier", "canonical_url", "metadata_sources",
            "metadata_status", "evidence_locator", "support_status",
            "correction_retraction_status", "accessed_at", "auditor", "severity",
            "verification_command", "artifact_path", "artifact_sha256", "checked_at", "notes",
        ],
        workspace / "audits" / "citations" / "citation_ledger_v7.csv",
    )
    extend_csv_fields(
        workspace / "audits" / "data" / "data_provenance.csv",
        [
            "data_id", "relative_path", "source_type", "source_url", "license_or_terms",
            "acquired_at", "original_sha256", "current_sha256", "transform_script",
            "fields_used", "status", "verification_command", "checked_at", "reviewer", "notes",
        ],
        workspace / "audits" / "data" / "data_provenance_v7.csv",
    )
    profile_path = workspace / "compliance" / "competition_profile.json"
    if not profile_path.exists():
        profile = {
            "schema_version": 1,
            "profile_id": f"{manifest.get('competition', '')}-{manifest.get('year', '')}-migrated-unverified",
            "competition": manifest.get("competition"),
            "edition": str(manifest.get("year", "")),
            "status": "unverified",
            "effective_from": "",
            "effective_to": None,
            "verified_at": "",
            "verified_by": "",
            "sources": [],
            "requirements": {
                "paper": {"format": None, "max_front_matter_pages": None, "max_total_pages": None, "max_body_pages": None, "max_pdf_bytes": None, "page_size": None, "table_of_contents_allowed": None, "anonymous": None},
                "submission": {"support_archive_required": None, "support_archive_max_bytes": None},
                "ai": {
                    "policy_checked": False, "usage_statement_required": None,
                    "details_pdf_required": None, "statement_position": None,
                    "inline_disclosure_required": None, "tool_reference_required": None,
                    "human_verification_required": None, "details_filename": None,
                },
            },
            "notes": "Migrated from v7. Reverify current official rules; no year-based rule inference was retained.",
        }
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv_if_missing(
        workspace / "compliance" / "ai_usage_ledger.csv",
        [
            "use_id", "tool", "version", "purpose", "paper_section", "paper_anchor",
            "citation_key", "human_changes", "verification_status", "artifact_path",
            "sha256", "command_or_check", "checked_at", "reviewer", "notes",
        ],
    )
    manifest["schema_version"] = TARGET_VERSION
    manifest["workflow_version"] = TARGET_VERSION
    manifest["competition_profile"] = "compliance/competition_profile.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for relative, fresh in (
        (
            "audits/gate_status.json",
            {
                "status": "not_reviewed",
                "gates": {
                    f"G{index}": {
                        "status": "pending", "reviewer": "", "checked_at": "",
                        "evidence": [], "blocking_findings": [],
                    }
                    for index in range(8)
                },
            },
        ),
        (
            "audits/reproduction/reproduction_status.json",
            {
                "status": "pending", "reviewer": "", "checked_at": "",
                "clean_run_command": "", "core_results_reproduced": False,
                "evidence": [], "blocking_findings": [],
            },
        ),
    ):
        path = workspace / relative
        if path.is_file():
            backup = path.with_name(path.stem + "_v7" + path.suffix)
            if not backup.exists():
                shutil.copy2(path, backup)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_board = workspace / "shared" / "task_board.csv"
    if task_board.is_file():
        backup = workspace / "shared" / "task_board_v7.csv"
        if not backup.exists():
            shutil.copy2(task_board, backup)
        branches = manifest.get("branches") if isinstance(manifest.get("branches"), list) else ["model-a"]
        rows = [
            ["profile-audit", "all", "rules", "", "", "compliance/competition_profile.json", "", "", "verify current official profile", "pending", "true", "profile and snapshots", ""],
            ["problem-route", "all", "routing", "", "", "shared/problem_route.md", "", "", "unverified exploratory structure", "pending", "true", "frozen route", ""],
            ["strong-baseline", "all", "baseline", "problem-route", "", "innovation/baseline_failure_map.md", "", "", "simple baseline", "pending", "true", "baseline tests", ""],
            ["baseline-failure", "all", "diagnostic", "strong-baseline", "", "innovation/baseline_failure_map.md", "", "", "no claim if no failure", "pending", "true", "failure evidence", ""],
            ["innovation-discovery", "all", "innovation", "baseline-failure", "", "innovation/claim_portfolio.csv", "", "", "minimal change", "pending", "true", "claim portfolio", ""],
            ["innovation-evidence", "all", "experiment", "innovation-discovery;profile-audit", "", "innovation/claim_experiments.csv", "", "", "no promotion before profile", "pending", "true", "claim evidence", ""],
            ["innovation-critic", "all", "red-team", "innovation-evidence", "", "innovation/critic_findings.csv", "", "", "reject complexity", "pending", "true", "critic findings", ""],
            ["innovation-selection", "all", "jury", "innovation-critic", "", "innovation/selection.csv", "", "", "primary claim", "pending", "true", "claim decision", ""],
        ]
        for branch in branches:
            rows.append([str(branch), "assigned", "model", "innovation-selection", "", f"branches/{branch}", "", "", "baseline solution", "pending", "true", "model and evidence", ""])
        joined = ";".join(str(item) for item in branches)
        rows.extend(
            [
                ["synthesis", "all", "synthesis", joined, "", "synthesis", "", "", "one selected solution", "pending", "true", "evidence matrix", ""],
                ["reproduction", "all", "reproduction", "synthesis", "", "audits/reproduction", "", "", "clean rerun", "pending", "true", "reproduction report", ""],
                ["paper", "all", "writing", "synthesis", "", "paper", "", "", "minimal complete paper", "pending", "true", "direct LaTeX paper", ""],
                ["citation-audit", "all", "citations", "paper", "", "audits/citations", "", "", "remove unsupported claims", "pending", "true", "citation ledger", ""],
                ["submission", "all", "submission", "paper;citation-audit;reproduction", "", "submission", "", "", "reproducible submission", "pending", "true", "paper and package", ""],
            ]
        )
        with task_board.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["task_id", "subproblem", "task_type", "depends_on", "owner", "assigned_path", "due_at", "freeze_at", "fallback", "status", "blocking", "deliverables", "evidence"])
            writer.writerows(rows)
    warnings.append("legacy innovation files were preserved; promoted v7 routes were not trusted as v8 claims")
    report = {
        "status": "pass" if not errors else "block",
        "from_version": current,
        "to_version": TARGET_VERSION,
        "migrated_legacy_candidates": len(migrated),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "warnings": warnings,
    }
    audit = workspace / "audits" / "migration_v7_to_v8.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a competition workspace to the current schema.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = migrate(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
