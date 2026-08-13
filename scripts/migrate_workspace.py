#!/usr/bin/env python3
"""Migrate v8-v13 workspaces to v14 source, interface, and execution contracts."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


TARGET_VERSION = 14


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
        "profile_id": f"{manifest.get('competition', '')}-{manifest.get('year', '')}-v14-migrated-unverified",
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


def write_v14_task_board(workspace: Path, version: int) -> None:
    path = workspace / "shared" / "task_board.csv"
    backup(path, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    def row(task_id: str, task_type: str, depends_on: str, assigned_path: str, fallback: str, deliverables: str, blocking: str = "true") -> list[str]:
        return [task_id, "all", task_type, depends_on, "", assigned_path, "", "", fallback, "pending", blocking, deliverables, ""]

    rows = [
        row("profile-audit", "rules", "", "compliance/competition_profile.json", "remain in rule verification", "verified current profile"),
        row("problem-route", "routing", "profile-audit", "shared/problem_contract.json", "recheck every prompt locator", "source-bound question contract"),
        row("semantic-mapper", "semantics", "problem-route", "innovation/semantic_fidelity_map.md", "preserve explicit problem semantics", "semantic requirements and simplified benchmark"),
        row("strong-baseline", "baseline", "semantic-mapper", "innovation/strong_baseline.md", "retain the simplest sufficient solution", "baseline definition and planned validation"),
        row("model-freeze", "selection", "strong-baseline", "synthesis/model_selection.json", "retain the simplest sufficient solution", "adaptive evidence-profile model decisions"),
        row("question-interfaces", "integration", "model-freeze", "shared/question_interfaces.json", "refresh downstream work after upstream changes", "frozen result fingerprints"),
        row("reproduction", "reproduction", "question-interfaces", "audits/reproduction/reproduction_status.json", "repair the executable clean-run contract", "isolated reproduction report"),
        row("review-router", "routing", "model-freeze", "synthesis/review_route.json", "route only applicable review", "adaptive review route and implementation check"),
        row("paper-payload", "synthesis", "model-freeze", "synthesis/paper_payload.json", "remove control-plane prose", "sanitized scientific payload"),
        row("paper", "writing", "paper-payload", "paper", "write only verified scientific content", "direct-LaTeX paper"),
        row("scientific-review", "review", "paper;review-router;reproduction", "audits/review_findings.json", "repair or weaken unsupported claims", "routed independent review"),
        row("paper-presentation", "presentation", "scientific-review", "audits/presentation", "keep audit language internal", "presentation firewall, visible validation and mechanism-visual audit"),
        row("paper-integrity", "integrity", "paper-presentation", "audits/integrity", "repair prose and implementation seams", "chat-residue, repeated-template and equation-code-result audit"),
        row("similarity-precheck", "similarity", "paper-integrity", "audits/similarity", "rewrite copied or template-derived prose", "local overlap report with human-review locations"),
        row("final-pdf-visual-review", "presentation", "similarity-precheck", "audits/presentation/final_pdf_visual_review.json", "re-review changed pages", "page-hash-bound visual review", "false"),
        row("submission", "submission", "similarity-precheck", "submission", "do not submit", "verified profile-required artifacts"),
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "subproblem", "task_type", "depends_on", "owner", "assigned_path", "due_at", "freeze_at", "fallback", "status", "blocking", "deliverables", "evidence"])
        writer.writerows(rows)


def migrate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    manifest_path = workspace / "competition_manifest.json"
    manifest = load(manifest_path)
    current = manifest.get("workflow_version")
    if current == TARGET_VERSION:
        return {"status": "pass", "from_version": current, "to_version": TARGET_VERSION, "errors": [], "warnings": ["workspace is already current"]}
    if current not in {8, 9, 10, 11, 12, 13}:
        return {
            "status": "block",
            "from_version": current,
            "to_version": TARGET_VERSION,
            "errors": [f"no direct migration path from workflow_version {current}; migrate to v8 first"],
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
    payload_path = workspace / "synthesis" / "paper_payload.json"
    if source_version in {8, 9}:
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
            payload_path,
            {"schema_version": 3, "status": "draft", "questions": []},
        )
    elif source_version in {10, 11}:
        backup(payload_path, source_version)
        payload = load(payload_path)
        questions = payload.get("questions")
        if not isinstance(questions, list):
            questions = []
        for item in questions:
            if not isinstance(item, dict):
                continue
            item["presentation_plan"] = {
                "answer_form": "pending",
                "answer_anchor": "",
                "answer_takeaway": "",
                "validation_form": "pending",
                "validation_anchor": "",
                "validation_takeaway": "",
                "mechanism_visual": "pending",
                "mechanism_visual_reason": "Reassess before paper freeze.",
                "mechanism_visual_must_show": [],
            }
            figures = item.get("figures")
            if isinstance(figures, list):
                for figure in figures:
                    if isinstance(figure, dict):
                        figure.setdefault("paper_anchor", "pending")
        payload["schema_version"] = 3
        payload["status"] = "draft"
        payload["questions"] = questions
        write_json(payload_path, payload)
        warnings.append(f"v{source_version} paper payload was preserved but reset to draft for question-local answer, validation and mechanism-visual planning")
    else:
        warnings.append(f"v{source_version} scientific and paper-payload state was preserved; v14 execution contracts were added")
    mode = str(manifest.get("innovation_mode", "standard"))
    if mode == "fast":
        mode = "standard"
        warnings.append("legacy fast mode was mapped to standard")
    if source_version in {8, 9}:
        write_json(
            review_path,
            {
                "schema_version": 2,
                "status": "not_reviewed",
                "policy": {"max_accepted_major": 0 if mode == "championship" else 1},
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
    reproduction_path = workspace / "audits" / "reproduction" / "reproduction_status.json"
    backup(reproduction_path, source_version)
    write_json(
        reproduction_path,
        {
            "schema_version": 2,
            "status": "pending",
            "reviewer": "",
            "checked_at": "",
            "runner": {"argv": [], "working_directory": ".", "timeout_seconds": 900, "clean_paths": []},
            "expected_artifacts": [],
            "blocking_findings": [],
        },
    )
    write_json(
        workspace / "audits" / "presentation" / "final_pdf_visual_review.json",
        {"schema_version": 1, "status": "pending", "pdf_path": "", "pdf_sha256": "", "page_count": 0, "render_dpi": 150, "page_reviews": []},
    )
    write_v14_task_board(workspace, source_version)

    manifest["schema_version"] = TARGET_VERSION
    manifest["workflow_version"] = TARGET_VERSION
    manifest["workflow_stage"] = "rule_verification"
    manifest["innovation_mode"] = mode
    manifest["competition_profile"] = "compliance/competition_profile.json"
    write_json(manifest_path, manifest)
    if source_version in {8, 9}:
        warnings.append(f"v{source_version} model-selection and review records were preserved but reset for adaptive schemas")
    warnings.append("problem contract, cross-question interfaces, executable reproduction, and final PDF page review must be re-frozen before submission")
    report = {
        "status": "pass",
        "from_version": source_version,
        "to_version": TARGET_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "warnings": warnings,
    }
    write_json(workspace / "audits" / f"migration_v{source_version}_to_v14.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a v8-v13 competition workspace to v14.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = migrate(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
