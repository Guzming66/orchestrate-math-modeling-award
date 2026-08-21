#!/usr/bin/env python3
"""Migrate v8-v14 workspaces to v15 claim, presentation, and review contracts."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from init_competition_workspace import create_workspace


TARGET_VERSION = 15
EVIDENCE_PROFILES = {
    "analytical", "deterministic_numerical", "optimization", "statistical",
    "simulation", "machine_learning",
}


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def backup(path: Path, version: int) -> None:
    if not path.is_file():
        return
    target = path.with_name(f"{path.stem}_v{version}{path.suffix}")
    if not target.exists():
        shutil.copy2(path, target)


def append_csv_fields(path: Path, fields: list[str]) -> None:
    if not path.is_file():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        current = reader.fieldnames or []
        rows = list(reader)
    missing = [field for field in fields if field not in current]
    if not missing:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=current + missing)
        writer.writeheader()
        writer.writerows(rows)


def v8_profile(manifest: dict[str, object]) -> dict[str, object]:
    engine = str(manifest.get("paper_engine", "")).strip()
    if engine not in {"xelatex", "pdflatex", "lualatex"}:
        engine = "xelatex" if manifest.get("competition") == "CUMCM" else "pdflatex"
    main_document = Path(str(manifest.get("paper_source", "paper/main.tex"))).name
    return {
        "schema_version": 2,
        "profile_id": f"{manifest.get('competition', '')}-{manifest.get('year', '')}-v15-migrated-unverified",
        "competition": manifest.get("competition", ""),
        "edition": str(manifest.get("year", "")),
        "status": "unverified",
        "effective_from": None,
        "effective_to": None,
        "verified_at": "",
        "verified_by": None,
        "sources": [],
        "build": {"latex_engine": engine, "main_document": main_document},
        "requirements": {
            "paper": {
                "format": None, "max_front_matter_pages": None, "max_total_pages": None,
                "max_body_pages": None, "max_pdf_bytes": None, "page_size": None,
                "table_of_contents_allowed": None, "anonymous": None,
            },
            "submission": {"support_archive_required": None, "support_archive_max_bytes": None},
            "ai": {
                "policy_checked": False, "usage_statement_required": None,
                "details_pdf_required": None, "statement_source": None,
                "statement_enable_marker": None, "statement_position": None,
                "inline_disclosure_required": None, "tool_reference_required": None,
                "human_verification_required": None, "details_source": None,
                "details_filename": None,
            },
            "artifacts": [],
        },
        "rule_bindings": [],
        "notes": "Migrated from v8. Reverify current official rules; no v8 rule value was trusted automatically.",
    }


def structurally_current_profile(profile: dict[str, object]) -> bool:
    """Return whether a legacy profile has the v15 profile-v2 container shape.

    Scientific verification is deliberately not inferred here; the normal profile
    validator still has to bind every executable rule to its source artifact.
    """
    return (
        profile.get("schema_version") == 2
        and isinstance(profile.get("sources"), list)
        and isinstance(profile.get("build"), dict)
        and isinstance(profile.get("requirements"), dict)
        and isinstance(profile.get("rule_bindings"), list)
        and str(profile.get("competition", "")).strip() in {"CUMCM", "MCM", "ICM"}
        and str(profile.get("edition", "")).strip() != ""
    )


def prepare_payload_question(
    item: dict[str, object], profile_by_question: dict[str, str]
) -> dict[str, object]:
    """Preserve legacy content while making the reopened v4 draft schema-shaped."""
    question_id = str(item.get("question_id", "")).strip() or "PENDING"
    profile = str(item.get("evidence_profile", "")).strip().lower()
    if profile not in EVIDENCE_PROFILES:
        profile = profile_by_question.get(question_id, "analytical")
    item["question_id"] = question_id
    item["evidence_profile"] = profile
    for field in ("problem_summary", "core_model", "derivation_summary", "paper_section"):
        if not str(item.get(field, "")).strip():
            item[field] = "pending"
    for field in ("validation_summary", "sensitivity_and_limits"):
        if not isinstance(item.get(field), str):
            item[field] = ""
    if not isinstance(item.get("assumptions"), list):
        item["assumptions"] = []
    if not isinstance(item.get("key_results"), list):
        item["key_results"] = []
    if profile != "analytical" and not str(item.get("algorithm_summary", "")).strip():
        item["algorithm_summary"] = "pending"

    precision = item.get("precision_policy")
    if not isinstance(precision, dict):
        precision = {}
    for field in ("display_rule", "justification", "dominant_uncertainty"):
        precision.setdefault(field, "")
    item["precision_policy"] = precision

    complexity = item.get("complexity_value")
    if not isinstance(complexity, dict):
        complexity = {}
    complexity.setdefault("mode", "no_extra_complexity")
    complexity.setdefault("added_complexity", "pending")
    complexity.setdefault("structural_need", "pending")
    complexity.setdefault("incremental_gain", None)
    complexity.setdefault("decision", "pending")
    item["complexity_value"] = complexity

    presentation = item.get("presentation_plan")
    if not isinstance(presentation, dict):
        presentation = {}
    for field, default in (
        ("answer_form", "pending"), ("answer_anchor", ""), ("answer_takeaway", ""),
        ("validation_form", "pending"), ("validation_anchor", ""), ("validation_takeaway", ""),
        ("mechanism_visual", "pending"),
        ("mechanism_visual_reason", "Reassess before paper freeze."),
        ("mechanism_visual_must_show", []),
    ):
        presentation.setdefault(field, default)
    item["presentation_plan"] = presentation
    # Geometry claims gained a new claim-level contract in v15.  Preserve the old
    # payload in its backup and require explicit re-entry instead of inventing data.
    item["geometry_claims"] = []

    figures = item.get("figures")
    if not isinstance(figures, list):
        figures = []
    for figure in figures:
        if not isinstance(figure, dict):
            continue
        figure.setdefault("paper_anchor", "pending")
        figure.setdefault("final_width", "pending")
        figure.setdefault("minimum_label_pt", 6.0)
        figure["final_size_reviewed"] = False
        if str(figure.get("role", "")).strip().lower() in {"data", "diagnostic", "decision"}:
            figure.setdefault("claim_anchor", "pending")
            figure.setdefault("samples_per_pixel", None)
            figure.setdefault("overplot_handling", "pending")
    item["figures"] = figures
    return item


def migrate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    manifest_path = workspace / "competition_manifest.json"
    manifest = load(manifest_path)
    current = manifest.get("workflow_version")
    if current == TARGET_VERSION:
        return {"status": "pass", "from_version": current, "to_version": TARGET_VERSION, "errors": [], "warnings": ["workspace is already current"]}
    if current not in {8, 9, 10, 11, 12, 13, 14}:
        return {
            "status": "block",
            "from_version": current,
            "to_version": TARGET_VERSION,
            "errors": [f"no direct migration path from workflow_version {current}; migrate to a supported v8-v14 workspace first"],
            "warnings": [],
        }

    source_version = int(current)
    warnings: list[str] = []
    backup(manifest_path, source_version)
    profile_path = workspace / "compliance" / "competition_profile.json"
    legacy_profile = load(profile_path)
    if source_version == 8 or not structurally_current_profile(legacy_profile):
        backup(profile_path, source_version)
        write_json(profile_path, v8_profile(manifest))
        warnings.append(
            f"v{source_version} competition profile was reset because it lacked the current source-bound profile-v2 structure"
        )

    model_path = workspace / "synthesis" / "model_selection.json"
    review_path = workspace / "audits" / "review_findings.json"
    payload_path = workspace / "synthesis" / "paper_payload.json"
    if source_version in {8, 9}:
        backup(model_path, source_version)
        write_json(
            model_path,
            {
                "schema_version": 2,
                "status": "draft",
                "questions": [],
                "notes": f"Reconstruct adaptive evidence profiles from the preserved v{source_version} model-selection record.",
            },
        )
        write_json(
            workspace / "synthesis" / "review_route.json",
            {"schema_version": 1, "status": "draft", "questions": []},
        )
        write_json(
            payload_path,
            {"schema_version": 4, "status": "draft", "questions": []},
        )
    else:
        backup(payload_path, source_version)
        payload = load(payload_path)
        questions = payload.get("questions")
        if not isinstance(questions, list):
            questions = []
        selection = load(model_path)
        selection_questions = selection.get("questions")
        if not isinstance(selection_questions, list):
            selection_questions = []
        profile_by_question = {
            str(item.get("question_id", "")).strip(): str(item.get("evidence_profile", "")).strip().lower()
            for item in selection_questions if isinstance(item, dict)
            if str(item.get("question_id", "")).strip()
        }
        questions = [
            prepare_payload_question(item, profile_by_question)
            for item in questions if isinstance(item, dict)
        ]
        payload["schema_version"] = 4
        payload["status"] = "draft"
        payload["questions"] = questions
        write_json(payload_path, payload)
        warnings.append(
            f"v{source_version} paper payload was preserved but reset to draft for geometry-claim and final-size figure review"
        )
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode == "fast":
        mode = "standard"
        warnings.append("legacy fast mode was mapped to standard")
    backup(review_path, source_version)
    review_document = load(review_path)
    old_policy = review_document.get("policy")
    accepted_limit = (
        old_policy.get("max_accepted_major")
        if isinstance(old_policy, dict) and isinstance(old_policy.get("max_accepted_major"), int)
        else (0 if mode == "championship" else 1)
    )
    write_json(
        review_path,
        {
            "schema_version": 3,
            "status": "not_reviewed",
            "policy": {"max_accepted_major": accepted_limit},
            "coverage": [],
            "findings": [],
        },
    )
    warnings.append("independent review was reset because v15 requires anchored checks, adversarial attempts and evidence for every required pass")

    append_csv_fields(
        workspace / "innovation" / "claim_portfolio.csv",
        [
            "reasoning_path", "semantic_requirement", "faithfulness_argument", "simplified_benchmark",
            "faithfulness_evidence_artifact", "faithfulness_evidence_sha256",
            "faithfulness_check", "faithfulness_checked_at",
        ],
    )
    review_document = load(review_path)
    review_policy = review_document.get("policy")
    if isinstance(review_policy, dict):
        legacy_limit = review_policy.pop("max_open_major", None)
        review_policy.setdefault(
            "max_accepted_major",
            legacy_limit if isinstance(legacy_limit, int) else (0 if mode == "championship" else 1),
        )
        write_json(review_path, review_document)
    semantic_map = workspace / "innovation" / "semantic_fidelity_map.md"
    if not semantic_map.exists():
        semantic_map.parent.mkdir(parents=True, exist_ok=True)
        semantic_map.write_text(
            "# Semantic fidelity map\n\n"
            "| subproblem | explicit problem semantics | faithful mathematical object | hidden simplification to avoid | simplified benchmark | verification artifact |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    baseline_path = workspace / "innovation" / "strong_baseline.md"
    if not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            "# Strong baseline\n\n"
            "| subproblem | baseline | why structurally sufficient | assumptions | planned validation | evidence |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    append_csv_fields(
        workspace / "synthesis" / "innovation_claims.csv",
        ["reasoning_path", "semantic_requirement"],
    )
    for relative in ("audits/integrity", "audits/similarity/corpus"):
        (workspace / relative).mkdir(parents=True, exist_ok=True)
    for relative, fields in (
        (
            "compliance/ai_artifact_inventory.csv",
            ["artifact_id", "artifact_type", "relative_path", "ai_used", "use_ids", "human_verification", "sha256", "reviewer", "checked_at", "notes"],
        ),
        (
            "synthesis/implementation_trace.csv",
            ["trace_id", "question_id", "paper_section", "equation_or_claim_anchor", "mathematical_role", "implementation_path", "implementation_symbol", "test_artifact_path", "test_sha256", "test_command", "result_ids", "reviewer", "checked_at", "notes"],
        ),
        (
            "synthesis/entity_lexicon.csv",
            ["entity_id", "display_name_zh", "display_name_en", "symbol", "unit", "notes"],
        ),
        (
            "audits/similarity/reference_corpus.csv",
            ["source_id", "source_type", "text_path", "sha256", "status", "notes"],
        ),
    ):
        path = workspace / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                csv.writer(handle).writerow(fields)
    contract_path = workspace / "shared" / "problem_contract.json"
    if not contract_path.exists():
        write_json(
            contract_path,
            {
                "schema_version": 1,
                "status": "draft",
                "competition": manifest.get("competition", ""),
                "year": manifest.get("year", ""),
                "problem": manifest.get("problem", ""),
                "problem_artifacts": [],
                "questions": [],
                "notes": "Rebuild from hashed source problem files before submission.",
            },
        )
    write_json(
        workspace / "shared" / "question_interfaces.json",
        {"schema_version": 1, "status": "draft", "interfaces": [], "notes": "Re-freeze every cross-question dependency after migration."},
    )
    append_csv_fields(workspace / "synthesis" / "result_manifest.csv", ["question_id"])
    write_json(
        workspace / "synthesis" / "global_claim_certificates.json",
        {
            "schema_version": 1,
            "status": "draft",
            "claims": [],
            "notes": "Reassess every first-event, global optimum/extremum and full-domain safety statement before paper freeze.",
        },
    )
    reproduction_path = workspace / "audits" / "reproduction" / "reproduction_status.json"
    backup(reproduction_path, source_version)
    write_json(
        reproduction_path,
        {
            "schema_version": 2,
            "status": "pending",
            "reviewer": "",
            "checked_at": "",
            "runner": {
                "argv": [], "entrypoint": "", "entrypoint_sha256": "",
                "working_directory": ".", "timeout_seconds": 900, "clean_paths": [],
            },
            "expected_artifacts": [],
            "blocking_findings": [],
        },
    )
    write_json(
        workspace / "audits" / "presentation" / "final_pdf_visual_review.json",
        {
            "schema_version": 2,
            "status": "pending",
            "pdf_path": "",
            "pdf_sha256": "",
            "page_count": 0,
            "render_dpi": 150,
            "page_text_fill": [],
            "page_layout_metrics": [],
            "page_reviews": [],
        },
    )
    competition = str(manifest.get("competition", "")).strip().upper()
    if competition not in {"CUMCM", "MCM", "ICM"}:
        return {
            "status": "block",
            "from_version": source_version,
            "to_version": TARGET_VERSION,
            "errors": ["legacy manifest competition must be CUMCM, MCM, or ICM before migration"],
            "warnings": warnings,
        }
    try:
        year = int(manifest.get("year"))
    except (TypeError, ValueError):
        return {
            "status": "block",
            "from_version": source_version,
            "to_version": TARGET_VERSION,
            "errors": ["legacy manifest year must be an integer before migration"],
            "warnings": warnings,
        }
    problem = str(manifest.get("problem", "")).strip()
    if not problem:
        problem = "UNSET"
        warnings.append("legacy manifest had no problem code; set problem to UNSET and verify it manually")
    raw_branches = manifest.get("branches")
    branches = (
        [str(value).strip() for value in raw_branches if isinstance(value, str) and value.strip()]
        if isinstance(raw_branches, list)
        else []
    )
    if not branches:
        branches = ["model-a"]
        warnings.append("legacy manifest had no usable branch list; one model-a branch was scaffolded")
    if len(branches) > 8 or len(set(branches)) != len(branches):
        return {
            "status": "block",
            "from_version": source_version,
            "to_version": TARGET_VERSION,
            "errors": ["legacy manifest branches must contain one to eight unique non-empty names"],
            "warnings": warnings,
        }
    manifest["schema_version"] = TARGET_VERSION
    manifest["workflow_version"] = TARGET_VERSION
    manifest["workflow_stage"] = "rule_verification"
    manifest["innovation_mode"] = mode
    manifest["competition"] = competition
    manifest["year"] = year
    manifest["problem"] = problem
    manifest["branches"] = branches
    manifest["competition_profile"] = "compliance/competition_profile.json"
    write_json(manifest_path, manifest)
    task_board_path = workspace / "shared" / "task_board.csv"
    backup(task_board_path, source_version)
    if task_board_path.is_file():
        task_board_path.unlink()
    try:
        create_workspace(
            argparse.Namespace(
                workspace=str(workspace),
                competition=competition,
                year=year,
                problem=problem,
                branches=len(branches),
                innovation_mode=mode,
            )
        )
    except (OSError, ValueError, SystemExit) as exc:
        manifest_backup = manifest_path.with_name(f"{manifest_path.stem}_v{source_version}{manifest_path.suffix}")
        if manifest_backup.is_file():
            shutil.copy2(manifest_backup, manifest_path)
        return {
            "status": "block",
            "from_version": source_version,
            "to_version": TARGET_VERSION,
            "errors": [f"v15 scaffold failed: {exc}"],
            "warnings": warnings,
        }
    required_scaffold = (
        "paper/main.tex",
        "shared/task_board.csv",
        "audits/citations/citation_ledger.csv",
        "audits/data/data_provenance.csv",
        "compliance/ai_usage_ledger.csv",
        "synthesis/result_manifest.csv",
        "submission/support_manifest.json",
    )
    missing_scaffold = [relative for relative in required_scaffold if not (workspace / relative).is_file()]
    if missing_scaffold:
        manifest_backup = manifest_path.with_name(f"{manifest_path.stem}_v{source_version}{manifest_path.suffix}")
        if manifest_backup.is_file():
            shutil.copy2(manifest_backup, manifest_path)
        return {
            "status": "block",
            "from_version": source_version,
            "to_version": TARGET_VERSION,
            "errors": ["v15 scaffold is incomplete: " + ", ".join(missing_scaffold)],
            "warnings": warnings,
        }
    if source_version in {8, 9}:
        warnings.append(f"v{source_version} model-selection and review records were preserved but reset for adaptive schemas")
    warnings.append("global-claim certificates, review evidence, geometry claims, cross-question interfaces, reproduction, and final PDF page review must be re-frozen before submission")
    report = {
        "status": "pass",
        "from_version": source_version,
        "to_version": TARGET_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "warnings": warnings,
    }
    write_json(workspace / "audits" / f"migration_v{source_version}_to_v15.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a v8-v14 competition workspace to v15.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = migrate(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
