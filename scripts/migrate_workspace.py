#!/usr/bin/env python3
"""Migrate a v8 workspace to v9 while resetting rule and review trust."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


TARGET_VERSION = 9


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def migrate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    manifest_path = workspace / "competition_manifest.json"
    manifest = load(manifest_path)
    current = manifest.get("workflow_version")
    if current == TARGET_VERSION:
        return {"status": "pass", "from_version": current, "to_version": TARGET_VERSION, "errors": [], "warnings": ["workspace is already current"]}
    if current != 8:
        return {
            "status": "block",
            "from_version": current,
            "to_version": TARGET_VERSION,
            "errors": [f"no direct migration path from workflow_version {current}; migrate to v8 first"],
            "warnings": [],
        }

    warnings: list[str] = []
    profile_path = workspace / "compliance" / "competition_profile.json"
    if profile_path.is_file():
        backup = profile_path.with_name("competition_profile_v8.json")
        if not backup.exists():
            shutil.copy2(profile_path, backup)
    old_build_engine = str(manifest.get("paper_engine", "")).strip()
    if old_build_engine not in {"xelatex", "pdflatex", "lualatex"}:
        old_build_engine = "xelatex" if manifest.get("competition") == "CUMCM" else "pdflatex"
    main_document = Path(str(manifest.get("paper_source", "paper/main.tex"))).name
    v9_profile = {
        "schema_version": 2,
        "profile_id": f"{manifest.get('competition', '')}-{manifest.get('year', '')}-v9-migrated-unverified",
        "competition": manifest.get("competition", ""),
        "edition": str(manifest.get("year", "")),
        "status": "unverified",
        "effective_from": None,
        "effective_to": None,
        "verified_at": "",
        "verified_by": None,
        "sources": [],
        "build": {"latex_engine": old_build_engine, "main_document": main_document},
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
                "statement_enable_marker": None,
                "statement_position": None, "inline_disclosure_required": None,
                "tool_reference_required": None, "human_verification_required": None,
                "details_source": None, "details_filename": None,
            },
            "artifacts": [],
        },
        "rule_bindings": [],
        "notes": "Migrated from v8. Reverify official rules and bind every active requirement to a source locator. No v8 rule value was trusted automatically.",
    }
    write_json(profile_path, v9_profile)

    write_json(
        workspace / "synthesis" / "model_selection.json",
        {
            "schema_version": 1,
            "status": "draft",
            "questions": [],
            "notes": "Reconstruct question-level model decisions from branch evidence; the legacy evidence_matrix.csv remains historical only.",
        },
    )
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode == "fast":
        mode = "standard"
        warnings.append("legacy fast mode was mapped to standard")
    write_json(
        workspace / "audits" / "review_findings.json",
        {
            "schema_version": 1,
            "status": "not_reviewed",
            "policy": {"max_open_major": 0 if mode == "championship" else 1},
            "coverage": [
                {"review_type": item, "status": "pending", "rationale": ""}
                for item in ("scientific", "statistical", "claims")
            ],
            "findings": [],
        },
    )

    task_board = workspace / "shared" / "task_board.csv"
    if task_board.is_file():
        backup = task_board.with_name("task_board_v8.csv")
        if not backup.exists():
            shutil.copy2(task_board, backup)
        branches = manifest.get("branches") if isinstance(manifest.get("branches"), list) else ["model-a"]
        rows = [
            ["profile-audit", "rules", "", "compliance/competition_profile.json", "remain in rule verification", "verify current official sources and bindings", "pending", "true"],
            ["exploration", "modeling", "profile-audit", "branches", "retain the strong baseline", "strong baseline plus only necessary alternatives", "pending", "true"],
            ["model-freeze", "selection", "exploration", "synthesis/model_selection.json", "select the validated baseline", "evidence-backed decision per core question", "pending", "true"],
            ["paper-freeze", "writing", "model-freeze", "paper", "write only verified results", "direct-LaTeX paper", "pending", "true"],
            ["scientific-review", "review", "paper-freeze", "audits/review_findings.json", "weaken or remove unsupported claims", "independent scientific/statistical/claim review", "pending", "true"],
            ["submission", "submission", "scientific-review", "submission", "do not submit", "verified profile-required artifacts", "pending", "true"],
        ]
        with task_board.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["task_id", "task_type", "depends_on", "assigned_path", "fallback", "deliverables", "status", "blocking"])
            writer.writerows(rows)
        warnings.append(f"legacy task board was preserved; {len(branches)} branch directories were left intact")

    manifest["schema_version"] = TARGET_VERSION
    manifest["workflow_version"] = TARGET_VERSION
    manifest["workflow_stage"] = "rule_verification"
    manifest["innovation_mode"] = mode
    manifest["competition_profile"] = "compliance/competition_profile.json"
    write_json(manifest_path, manifest)
    warnings.append("v8 rule values and review decisions were reset because they lacked v9 source bindings")
    report = {
        "status": "pass",
        "from_version": current,
        "to_version": TARGET_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "warnings": warnings,
    }
    write_json(workspace / "audits" / "migration_v8_to_v9.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a v8 competition workspace to v9.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = migrate(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
