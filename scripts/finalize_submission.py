#!/usr/bin/env python3
"""Run every hard gate and produce a fail-closed submission manifest."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from package_submission import package_workspace
from build_latex import strip_tex_comments
from evidence_utils import artifact_errors, sha256_file
from preflight import preflight
from snapshot_environment import snapshot
from validate_competition_profile import load_profile, validate_competition_profile
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_model_selection import validate_model_selection
from validate_paper_innovation import validate_paper_innovation
from validate_review_findings import validate_review_findings
from validate_task_board import validate_task_board


PASS = {"pass", "verified", "done"}
CORRECTION_CLEAR = {"clear", "checked", "not_applicable", "corrected_version_used"}
PAGE_SIZES_POINTS = {
    "A4": (595.276, 841.89),
    "LETTER": (612.0, 792.0),
}


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace).as_posix()


def bib_keys(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {match.strip() for match in re.findall(r"@\w+\s*\{\s*([^,\s]+)", text)}


def check_citations(workspace: Path) -> list[str]:
    errors: list[str] = []
    keys = bib_keys(workspace / "paper" / "references.bib")
    rows = read_csv(workspace / "audits" / "citations" / "citation_ledger.csv")
    if not keys:
        if rows:
            errors.append("citation ledger has rows but references.bib has no entries")
        return errors
    report = load_json(workspace / "audits" / "citations" / "metadata_report.json")
    if not report:
        errors.append("citation metadata report is missing")
    elif report.get("errors"):
        errors.append("citation metadata report contains errors")
    covered: set[str] = set()
    for index, row in enumerate(rows, start=2):
        key = row.get("citation_key", "").strip()
        if not key:
            errors.append(f"citation ledger row {index}: citation_key is empty")
            continue
        covered.add(key)
        if row.get("metadata_status", "").strip().lower() != "verified":
            errors.append(f"{key}: metadata_status is not verified")
        if row.get("support_status", "").strip().lower() != "supported":
            errors.append(f"{key}: support_status is not supported")
        if row.get("correction_retraction_status", "").strip().lower() not in CORRECTION_CLEAR:
            errors.append(f"{key}: correction/retraction status is not cleared")
        for field in ("claim_id", "claim_location", "evidence_locator", "accessed_at", "auditor"):
            if not row.get(field, "").strip():
                errors.append(f"{key}: {field} is empty")
        errors.extend(
            artifact_errors(
                workspace,
                row,
                f"citation {key}",
                path_field="artifact_path",
                sha_field="artifact_sha256",
                check_field="verification_command",
            )
        )
    for key in sorted(keys - covered):
        errors.append(f"citation is not covered by the claim ledger: {key}")
    for key in sorted(covered - keys):
        errors.append(f"citation ledger references an unknown BibTeX key: {key}")
    return errors


def check_data_provenance(workspace: Path) -> list[str]:
    errors: list[str] = []
    rows = read_csv(workspace / "audits" / "data" / "data_provenance.csv")
    by_path = {row.get("relative_path", "").replace("\\", "/").strip(): row for row in rows}
    input_files = [
        path
        for folder in (workspace / "inputs" / "original", workspace / "inputs" / "external")
        if folder.is_dir()
        for path in folder.rglob("*")
        if path.is_file()
    ]
    if not input_files:
        errors.append("no original or external input files are present")
    for path in input_files:
        rel = relative(workspace, path)
        row = by_path.get(rel)
        if row is None:
            errors.append(f"input file is missing from data_provenance.csv: {rel}")
            continue
        digest = sha256_file(path)
        if row.get("status", "").strip().lower() != "verified":
            errors.append(f"{rel}: provenance status is not verified")
        if row.get("original_sha256", "").strip().lower() != digest:
            errors.append(f"{rel}: original_sha256 does not match")
        if row.get("current_sha256", "").strip().lower() != digest:
            errors.append(f"{rel}: current_sha256 does not match")
        for field in (
            "data_id",
            "source_type",
            "acquired_at",
            "verification_command",
            "checked_at",
            "reviewer",
        ):
            if not row.get(field, "").strip():
                errors.append(f"{rel}: {field} is empty")
        if rel.startswith("inputs/external/"):
            for field in ("source_url", "license_or_terms"):
                if not row.get(field, "").strip():
                    errors.append(f"{rel}: external data requires {field}")
    for rel in sorted(set(by_path) - {relative(workspace, path) for path in input_files}):
        if rel:
            errors.append(f"data provenance row points to a missing input file: {rel}")
    return errors


def check_results(workspace: Path) -> list[str]:
    errors: list[str] = []
    rows = read_csv(workspace / "synthesis" / "result_manifest.csv")
    if not rows:
        return ["result_manifest.csv has no core results"]
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        result_id = row.get("result_id", "").strip()
        if not result_id:
            errors.append(f"result row {index}: result_id is empty")
        elif result_id in seen:
            errors.append(f"duplicate result_id: {result_id}")
        seen.add(result_id)
        rel = row.get("relative_path", "").replace("\\", "/").strip()
        try:
            path = (workspace / rel).resolve()
            path.relative_to(workspace)
        except ValueError:
            errors.append(f"{result_id}: result path escapes workspace")
            continue
        if not path.is_file():
            errors.append(f"{result_id}: result file is missing: {rel}")
        elif row.get("sha256", "").strip().lower() != sha256_file(path):
            errors.append(f"{result_id}: result sha256 does not match")
        for field in ("claim_location", "value", "unit", "generator", "command", "input_ids", "seed", "environment_file", "reviewer"):
            if not row.get(field, "").strip():
                errors.append(f"{result_id}: {field} is empty")
        if row.get("status", "").strip().lower() != "verified":
            errors.append(f"{result_id}: status is not verified")
        environment_file = row.get("environment_file", "").strip()
        if environment_file and not (workspace / environment_file).is_file():
            errors.append(f"{result_id}: environment_file is missing")
    return errors


def check_reproduction(workspace: Path) -> list[str]:
    document = load_json(workspace / "audits" / "reproduction" / "reproduction_status.json")
    errors: list[str] = []
    if str(document.get("status", "")).lower() not in PASS:
        errors.append("reproduction status is not pass")
    if document.get("core_results_reproduced") is not True:
        errors.append("core_results_reproduced is not true")
    for field in ("reviewer", "checked_at", "clean_run_command"):
        if not str(document.get(field, "")).strip():
            errors.append(f"reproduction: {field} is empty")
    evidence = document.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("reproduction evidence is empty")
    else:
        for index, record in enumerate(evidence, start=1):
            if not isinstance(record, dict):
                errors.append(f"reproduction evidence {index} is not an artifact record")
                continue
            errors.extend(artifact_errors(workspace, record, f"reproduction evidence {index}"))
    if isinstance(document.get("blocking_findings"), list) and document["blocking_findings"]:
        errors.append("reproduction blocking findings remain")
    return errors


def profile_requirements(profile: dict[str, object], group: str) -> dict[str, object]:
    requirements = profile.get("requirements")
    if not isinstance(requirements, dict):
        return {}
    value = requirements.get(group)
    return value if isinstance(value, dict) else {}


def check_ai_compliance(workspace: Path, profile: dict[str, object]) -> list[str]:
    ai = profile_requirements(profile, "ai")
    errors: list[str] = []
    paper = workspace / "paper"
    if ai.get("usage_statement_required") is True:
        statement_source = str(ai.get("statement_source", "") or "").replace("\\", "/").strip()
        if not statement_source:
            errors.append("competition profile requires statement_source for the AI usage statement")
        statement_path = (workspace / statement_source).resolve()
        try:
            statement_path.relative_to(workspace)
        except ValueError:
            errors.append("competition profile AI statement_source escapes workspace")
            statement_path = workspace / "__invalid__"
        statement = strip_tex_comments(statement_path.read_text(encoding="utf-8", errors="replace")) if statement_path.is_file() else ""
        if not statement.strip() or "DRAFT CONTENT" in statement:
            errors.append("competition profile requires a completed AI usage statement artifact")

        enable_marker = str(ai.get("statement_enable_marker", "") or "").strip()
        source_text = "\n".join(
            strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))
            for path in paper.rglob("*.tex")
            if "build" not in path.relative_to(paper).parts
        )
        if not enable_marker or enable_marker not in source_text:
            errors.append("competition profile AI usage statement is not enabled in the LaTeX source")

        build = profile.get("build") if isinstance(profile.get("build"), dict) else {}
        main_path = paper / str(build.get("main_document", "main.tex"))
        main = strip_tex_comments(main_path.read_text(encoding="utf-8", errors="replace")) if main_path.is_file() else ""
        statement_token = Path(statement_source).with_suffix("").as_posix() if statement_source else ""
        if statement_token.startswith("paper/"):
            statement_token = statement_token[len("paper/"):]
        statement_position = main.find(statement_token) if statement_token else -1
        bibliography_position = main.find("generated/bibliography.tex")
        position = str(ai.get("statement_position", "")).lower()
        if position == "before_references" and (
            statement_position < 0 or bibliography_position < 0 or statement_position > bibliography_position
        ):
            errors.append("competition profile requires the AI usage statement before references")
        if position == "after_references" and (
            statement_position < 0 or bibliography_position < 0 or statement_position < bibliography_position
        ):
            errors.append("competition profile requires the AI usage statement after references")

    ledger_required = any(
        ai.get(field) is True
        for field in ("inline_disclosure_required", "tool_reference_required", "human_verification_required")
    )
    ledger = read_csv(workspace / "compliance" / "ai_usage_ledger.csv")
    if ledger_required and not ledger:
        errors.append("competition profile requires an AI usage ledger")
    known_bib_keys = bib_keys(paper / "references.bib")
    for index, row in enumerate(ledger, start=2):
        label = row.get("use_id", "").strip() or f"AI usage row {index}"
        for field in ("use_id", "tool", "version", "purpose", "paper_section", "paper_anchor"):
            if not row.get(field, "").strip():
                errors.append(f"{label}: {field} is empty")
        section_rel = row.get("paper_section", "").replace("\\", "/").strip()
        try:
            section = (workspace / section_rel).resolve()
            section.relative_to(workspace)
        except ValueError:
            errors.append(f"{label}: paper_section escapes workspace")
        else:
            if not section.is_file():
                errors.append(f"{label}: paper_section is missing")
            elif ai.get("inline_disclosure_required") is True:
                marker = row.get("paper_anchor", "").strip()
                if marker not in section.read_text(encoding="utf-8", errors="replace"):
                    errors.append(f"{label}: inline AI disclosure anchor is absent")
        if ai.get("tool_reference_required") is True:
            key = row.get("citation_key", "").strip()
            if not key or key not in known_bib_keys:
                errors.append(f"{label}: AI tool citation_key is missing from references.bib")
        if ai.get("human_verification_required") is True:
            if row.get("verification_status", "").strip().lower() != "verified":
                errors.append(f"{label}: AI output is not marked human-verified")
            if not row.get("human_changes", "").strip():
                errors.append(f"{label}: human_changes is empty")
        errors.extend(artifact_errors(workspace, row, f"{label} AI evidence"))

    return errors


# One-version compatibility alias for v8 callers.
check_cumcm_ai_compliance = check_ai_compliance


def check_required_artifacts(workspace: Path, profile: dict[str, object]) -> list[str]:
    requirements = profile.get("requirements")
    artifacts = requirements.get("artifacts") if isinstance(requirements, dict) else []
    errors: list[str] = []
    support_manifest = load_json(workspace / "submission" / "support_manifest.json")
    manifest_files = support_manifest.get("files")
    archive_map: dict[str, str] = {}
    if isinstance(manifest_files, list):
        for item in manifest_files:
            if isinstance(item, dict):
                source = str(item.get("source", "")).replace("\\", "/")
                archive_map[source] = str(item.get("archive_path", source)).replace("\\", "/")
            else:
                source = str(item).replace("\\", "/")
                archive_map[source] = source
    if not isinstance(artifacts, list):
        return ["competition profile required artifacts are invalid"]
    for item in artifacts:
        if not isinstance(item, dict) or item.get("required") is not True:
            continue
        artifact_id = str(item.get("artifact_id", "required artifact"))
        source = str(item.get("source_path", "")).replace("\\", "/")
        archive_path = str(item.get("archive_path", "")).replace("\\", "/")
        try:
            path = (workspace / source).resolve()
            path.relative_to(workspace)
        except ValueError:
            errors.append(f"{artifact_id}: source_path escapes workspace")
            continue
        if not path.is_file():
            errors.append(f"{artifact_id}: required artifact is missing: {source}")
        if profile_requirements(profile, "submission").get("support_archive_required") is True:
            if archive_map.get(source) != archive_path:
                errors.append(f"{artifact_id}: support manifest does not map {source} to {archive_path}")
    return errors


def check_paper_against_profile(
    workspace: Path,
    profile: dict[str, object],
    build_report: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    paper = profile_requirements(profile, "paper")
    if str(paper.get("format", "")).lower() != "pdf":
        errors.append("competition profile paper format is not executable by this PDF pipeline")
    limits = (
        ("max_front_matter_pages", "front_matter_pages"),
        ("max_total_pages", "pages"),
        ("max_body_pages", "body_pages"),
        ("max_pdf_bytes", "file_size_bytes"),
    )
    for profile_key, report_key in limits:
        limit = paper.get(profile_key)
        if limit is None:
            continue
        value = build_report.get(report_key)
        if not isinstance(value, int):
            errors.append(f"unable to verify profile limit: {profile_key}")
        elif value > limit:
            errors.append(f"paper exceeds profile {profile_key}: {value} > {limit}")
    page_size = str(paper.get("page_size", "") or "").upper()
    if page_size in PAGE_SIZES_POINTS:
        width = build_report.get("page_width_points")
        height = build_report.get("page_height_points")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            errors.append(f"unable to verify profile {page_size} page size")
        else:
            expected_width, expected_height = PAGE_SIZES_POINTS[page_size]
            if abs(float(width) - expected_width) > 2.0 or abs(float(height) - expected_height) > 2.0:
                errors.append(f"paper is not portrait {page_size}: {width} x {height} pt")
    elif page_size:
        errors.append(f"paper page size cannot be executed by this finalizer: {page_size}")
    if paper.get("anonymous") is True and str(build_report.get("pdf_author", "") or "").strip():
        errors.append("competition profile requires anonymous PDF metadata")
    if paper.get("table_of_contents_allowed") is False:
        for path in (workspace / "paper").rglob("*.tex"):
            if "build" in path.relative_to(workspace / "paper").parts:
                continue
            if re.search(r"\\tableofcontents\b", strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))):
                errors.append("competition profile prohibits a table of contents")
                break
    return errors


def find_citation_validator() -> Path | None:
    """Locate the companion citation-management validator without a machine-specific path."""
    skill_root = Path(__file__).resolve().parents[1]
    candidates: list[Path] = []
    override = os.environ.get("CITATION_VALIDATOR")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(skill_root.parent / "citation-management" / "scripts" / "validate_citations.py")
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "skills" / "citation-management" / "scripts" / "validate_citations.py")
    candidates.extend(
        [
            Path.home() / ".codex" / "skills" / "citation-management" / "scripts" / "validate_citations.py",
            Path.home() / ".agents" / "skills" / "citation-management" / "scripts" / "validate_citations.py",
        ]
    )
    return next((path.resolve() for path in candidates if path.is_file()), None)


def run_citation_validator(workspace: Path) -> tuple[int, str]:
    if not bib_keys(workspace / "paper" / "references.bib"):
        return 0, "no bibliography entries"
    script = find_citation_validator()
    if script is None:
        return 1, "citation validator is missing; install citation-management or set CITATION_VALIDATOR"
    report = workspace / "audits" / "citations" / "metadata_report.json"
    command = [sys.executable, str(script), str(workspace / "paper" / "references.bib"), "--check-dois", "--report", str(report)]
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return result.returncode, result.stdout


def run_build(workspace: Path, engine: str, main_name: str = "main.tex") -> tuple[int, dict[str, object]]:
    script = Path(__file__).with_name("build_latex.py")
    command = [
        sys.executable,
        str(script),
        str(workspace / "paper"),
        "--engine",
        engine,
        "--main",
        main_name,
        "--mode",
        "submission",
    ]
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    report_name = "build_report.json" if main_name == "main.tex" else f"build_report_{Path(main_name).stem}.json"
    return result.returncode, load_json(workspace / "paper" / "build" / report_name)


def finalize(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_json(workspace / "competition_manifest.json")
    competition = str(manifest.get("competition", ""))
    if not competition:
        errors.append("competition manifest is missing or invalid")
    if manifest.get("workflow_stage") != "submission":
        errors.append("workflow_stage must be submission before finalization")
    profile = load_profile(workspace / "compliance" / "competition_profile.json")
    build_configuration = profile.get("build") if isinstance(profile.get("build"), dict) else {}
    engine = str(build_configuration.get("latex_engine", ""))
    main_document = str(build_configuration.get("main_document", "main.tex"))

    preflight_report = preflight(workspace, competition)
    errors.extend(str(item) for item in preflight_report.get("errors", []))
    warnings.extend(str(item) for item in preflight_report.get("warnings", []))

    profile_report = validate_competition_profile(workspace)
    errors.extend(str(item) for item in profile_report.get("errors", []))
    warnings.extend(str(item) for item in profile_report.get("warnings", []))

    environment_report = snapshot(workspace)
    if environment_report.get("status") != "pass":
        errors.extend(str(item) for item in environment_report.get("errors", []))

    task_report = validate_task_board(workspace / "shared" / "task_board.csv", final=True)
    (workspace / "audits" / "task_board_report.json").write_text(
        json.dumps(task_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    errors.extend(str(item) for item in task_report.get("errors", []))
    warnings.extend(str(item) for item in task_report.get("warnings", []))

    innovation_report = validate_innovation_portfolio(workspace)
    errors.extend(str(item) for item in innovation_report.get("errors", []))
    warnings.extend(str(item) for item in innovation_report.get("warnings", []))

    paper_innovation_report = validate_paper_innovation(workspace)
    errors.extend(str(item) for item in paper_innovation_report.get("errors", []))
    warnings.extend(str(item) for item in paper_innovation_report.get("warnings", []))

    model_selection_report = validate_model_selection(workspace)
    errors.extend(str(item) for item in model_selection_report.get("errors", []))
    warnings.extend(str(item) for item in model_selection_report.get("warnings", []))

    review_report = validate_review_findings(workspace)
    errors.extend(str(item) for item in review_report.get("errors", []))
    warnings.extend(str(item) for item in review_report.get("warnings", []))

    citation_exit, citation_output = run_citation_validator(workspace)
    if citation_exit != 0:
        errors.append("citation validator failed")

    checks = {
        "citations": check_citations(workspace),
        "data_provenance": check_data_provenance(workspace),
        "results": check_results(workspace),
        "reproduction": check_reproduction(workspace),
        "ai": check_ai_compliance(workspace, profile),
    }
    for findings in checks.values():
        errors.extend(findings)

    if errors:
        build_exit, build_report = 1, {"status": "skipped_upstream_block"}
        warnings.append("submission LaTeX build skipped because upstream hard gates failed")
    else:
        build_exit, build_report = run_build(workspace, engine, main_document) if engine else (1, {})
    if build_report.get("status") != "skipped_upstream_block" and (
        build_exit != 0 or build_report.get("status") != "pass"
    ):
        errors.append("submission LaTeX build failed")
        errors.extend(str(item) for item in build_report.get("errors", []))
    if profile_report.get("status") == "pass" and build_report.get("status") == "pass":
        profile_paper_errors = check_paper_against_profile(workspace, profile, build_report)
        checks["paper_profile"] = profile_paper_errors
        errors.extend(profile_paper_errors)

    ai_details_report: dict[str, object] = {"status": "not_applicable"}
    ai_requirements = profile_requirements(profile, "ai")
    if not errors and ai_requirements.get("details_pdf_required") is True:
        details_filename = str(ai_requirements.get("details_filename", "") or "").strip()
        details_source = str(ai_requirements.get("details_source", "") or "").strip()
        if not details_filename:
            ai_details_report = {"status": "block", "errors": ["AI details filename is empty"]}
            errors.append("competition profile AI details filename is empty")
        elif not details_source:
            ai_details_report = {"status": "block", "errors": ["AI details source is empty"]}
            errors.append("competition profile AI details source is empty")
        else:
            details_path = Path(details_source.replace("\\", "/"))
            try:
                ai_main = details_path.relative_to("paper").as_posix()
            except ValueError:
                ai_main = details_path.as_posix()
            ai_exit, ai_details_report = run_build(workspace, engine, ai_main)
            if ai_exit != 0 or ai_details_report.get("status") != "pass":
                errors.append("AI usage details LaTeX build failed")
                errors.extend(str(item) for item in ai_details_report.get("errors", []))
            else:
                source = Path(str(ai_details_report.get("pdf", "")))
                target = workspace / "paper" / "build" / details_filename
                try:
                    shutil.copy2(source, target)
                except OSError as exc:
                    errors.append(f"cannot create {details_filename}: {exc}")
                else:
                    ai_details_report["pdf"] = str(target)
                    ai_details_report["sha256"] = sha256_file(target)

    package_report: dict[str, object] = {"status": "not_applicable"}
    submission_requirements = profile_requirements(profile, "submission")
    if not errors and submission_requirements.get("support_archive_required") is True:
        max_bytes = submission_requirements.get("support_archive_max_bytes")
        package_report = package_workspace(
            workspace,
            require_paper=True,
            max_bytes=max_bytes if isinstance(max_bytes, int) else None,
        )
        if package_report.get("status") != "pass":
            errors.append("support package failed")
            errors.extend(str(item) for item in package_report.get("errors", []))

    artifact_errors_after_build = check_required_artifacts(workspace, profile)
    checks["required_artifacts"] = artifact_errors_after_build
    errors.extend(artifact_errors_after_build)

    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    status = "pass" if not errors else "block"
    report = {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "competition": competition,
        "workflow_version": manifest.get("workflow_version"),
        "checks": checks,
        "preflight_status": preflight_report.get("status"),
        "competition_profile_status": profile_report.get("status"),
        "environment_status": environment_report.get("status"),
        "task_status": task_report.get("status"),
        "innovation_status": innovation_report.get("status"),
        "paper_innovation_status": paper_innovation_report.get("status"),
        "model_selection_status": model_selection_report.get("status"),
        "review_status": review_report.get("status"),
        "citation_validator_output": citation_output[-4000:],
        "build_status": build_report.get("status"),
        "ai_details_build_status": ai_details_report.get("status"),
        "package_status": package_report.get("status"),
        "paper_sha256": build_report.get("sha256"),
        "support_sha256": package_report.get("archive_sha256"),
        "errors": errors,
        "warnings": warnings,
    }
    report_path = workspace / "audits" / "submission" / "final_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status == "pass":
        submission_manifest = {
            "created_at": report["checked_at"],
            "competition": competition,
            "paper": build_report.get("pdf"),
            "paper_sha256": build_report.get("sha256"),
            "ai_usage_details": ai_details_report.get("pdf"),
            "ai_usage_details_sha256": ai_details_report.get("sha256"),
            "support_archive": package_report.get("archive"),
            "support_sha256": package_report.get("archive_sha256"),
        }
        (workspace / "submission" / "submission_manifest.json").write_text(
            json.dumps(submission_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all final submission gates.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = finalize(Path(args.workspace).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
