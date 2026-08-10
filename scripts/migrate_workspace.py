#!/usr/bin/env python3
"""Migrate v8/v9 workspaces to v10 adaptive-review and presentation schemas."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


TARGET_VERSION = 10


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
        "profile_id": f"{manifest.get('competition', '')}-{manifest.get('year', '')}-v10-migrated-unverified",
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


def write_v10_task_board(workspace: Path, version: int) -> None:
    path = workspace / "shared" / "task_board.csv"
    backup(path, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ["profile-audit", "rules", "", "compliance/competition_profile.json", "remain in rule verification", "verified current profile", "pending", "true"],
        ["semantic-mapper", "semantics", "profile-audit", "innovation/semantic_fidelity_map.md", "preserve explicit problem semantics", "semantic requirements and simplified benchmark", "pending", "true"],
        ["strong-baseline", "baseline", "semantic-mapper", "innovation/strong_baseline.md", "retain the simplest sufficient solution", "baseline definition and planned validation", "pending", "true"],
        ["model-freeze", "selection", "strong-baseline", "synthesis/model_selection.json", "retain the simplest sufficient solution", "v10 evidence-profile model decisions", "pending", "true"],
        ["review-router", "routing", "model-freeze", "synthesis/review_route.json", "route only applicable review", "adaptive review route and implementation check", "pending", "true"],
        ["paper-payload", "synthesis", "model-freeze", "synthesis/paper_payload.json", "remove control-plane prose", "sanitized scientific payload", "pending", "true"],
        ["paper", "writing", "paper-payload", "paper", "write only verified scientific content", "direct-LaTeX paper", "pending", "true"],
        ["scientific-review", "review", "paper;review-router", "audits/review_findings.json", "repair or weaken unsupported claims", "routed independent review", "pending", "true"],
        ["paper-presentation", "presentation", "scientific-review", "audits/presentation", "keep audit language internal", "presentation firewall and value audit", "pending", "true"],
        ["submission", "submission", "paper-presentation", "submission", "do not submit", "verified profile-required artifacts", "pending", "true"],
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "task_type", "depends_on", "assigned_path", "fallback", "deliverables", "status", "blocking"])
        writer.writerows(rows)


def migrate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    manifest_path = workspace / "competition_manifest.json"
    manifest = load(manifest_path)
    current = manifest.get("workflow_version")
    if current == TARGET_VERSION:
        return {"status": "pass", "from_version": current, "to_version": TARGET_VERSION, "errors": [], "warnings": ["workspace is already current"]}
    if current not in {8, 9}:
        return {
            "status": "block",
            "from_version": current,
            "to_version": TARGET_VERSION,
            "errors": [f"no direct migration path from workflow_version {current}; migrate to v8 or v9 first"],
            "warnings": [],
        }

    source_version = int(current)
    warnings: list[str] = []
    profile_path = workspace / "compliance" / "competition_profile.json"
    if source_version == 8:
        backup(profile_path, 8)
        write_json(profile_path, v8_profile(manifest))
        warnings.append("v8 rule values were reset because they lacked source-bound profile v2 evidence")

    model_path = workspace / "synthesis" / "model_selection.json"
    review_path = workspace / "audits" / "review_findings.json"
    backup(model_path, source_version)
    backup(review_path, source_version)
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
        workspace / "synthesis" / "paper_payload.json",
        {"schema_version": 1, "status": "draft", "questions": []},
    )
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode == "fast":
        mode = "standard"
        warnings.append("legacy fast mode was mapped to standard")
    write_json(
        review_path,
        {
            "schema_version": 2,
            "status": "not_reviewed",
            "policy": {"max_open_major": 0 if mode == "championship" else 1},
            "coverage": [],
            "findings": [],
        },
    )

    append_csv_fields(
        workspace / "innovation" / "claim_portfolio.csv",
        [
            "reasoning_path", "semantic_requirement", "faithfulness_argument", "simplified_benchmark",
            "faithfulness_evidence_artifact", "faithfulness_evidence_sha256",
            "faithfulness_check", "faithfulness_checked_at",
        ],
    )
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
    write_v10_task_board(workspace, source_version)

    manifest["schema_version"] = TARGET_VERSION
    manifest["workflow_version"] = TARGET_VERSION
    manifest["workflow_stage"] = "rule_verification"
    manifest["innovation_mode"] = mode
    manifest["competition_profile"] = "compliance/competition_profile.json"
    write_json(manifest_path, manifest)
    warnings.append(f"v{source_version} model-selection and review records were preserved but reset for v10 adaptive schemas")
    report = {
        "status": "pass",
        "from_version": source_version,
        "to_version": TARGET_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "warnings": warnings,
    }
    write_json(workspace / "audits" / f"migration_v{source_version}_to_v10.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a v8/v9 competition workspace to v10.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = migrate(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
