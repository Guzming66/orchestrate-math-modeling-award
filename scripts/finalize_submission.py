#!/usr/bin/env python3
"""Run every hard gate and produce a fail-closed submission manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
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
from snapshot_environment import snapshot
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_task_board import validate_task_board


PASS = {"pass", "verified", "done"}
CORRECTION_CLEAR = {"clear", "checked", "not_applicable", "corrected_version_used"}


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace).as_posix()


def check_gate_status(workspace: Path) -> list[str]:
    errors: list[str] = []
    document = load_json(workspace / "audits" / "gate_status.json")
    gates = document.get("gates")
    if not isinstance(gates, dict):
        return ["audits/gate_status.json is missing or invalid"]
    for gate_id in (f"G{index}" for index in range(8)):
        gate = gates.get(gate_id)
        if not isinstance(gate, dict):
            errors.append(f"{gate_id}: gate record is missing")
            continue
        if str(gate.get("status", "")).lower() not in PASS:
            errors.append(f"{gate_id}: status is not pass")
        for field in ("reviewer", "checked_at"):
            if not str(gate.get(field, "")).strip():
                errors.append(f"{gate_id}: {field} is empty")
        evidence = gate.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{gate_id}: evidence is empty")
        blocking = gate.get("blocking_findings")
        if isinstance(blocking, list) and blocking:
            errors.append(f"{gate_id}: blocking findings remain")
    return errors


def check_official_sources(workspace: Path) -> list[str]:
    errors: list[str] = []
    document = load_json(workspace / "compliance" / "official_sources.json")
    if str(document.get("status", "")).lower() != "verified":
        errors.append("official sources are not marked verified")
    for field in ("last_checked_at", "verified_by"):
        if not str(document.get(field, "")).strip():
            errors.append(f"official sources: {field} is empty")
    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("official sources list is empty")
        return errors
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"official source {index} is invalid")
            continue
        for field in ("kind", "url", "version", "sha256"):
            if not str(source.get(field, "")).strip():
                errors.append(f"official source {index}: {field} is empty")
    return errors


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
        for field in ("data_id", "source_type", "acquired_at", "reviewer"):
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
    if isinstance(document.get("blocking_findings"), list) and document["blocking_findings"]:
        errors.append("reproduction blocking findings remain")
    return errors


def check_evidence_matrix(workspace: Path) -> list[str]:
    rows = read_csv(workspace / "synthesis" / "evidence_matrix.csv")
    selected = [row for row in rows if row.get("decision", "").strip().lower() in {"selected", "primary", "accepted"}]
    if len(selected) != 1:
        return [f"evidence matrix must contain exactly one selected branch; found {len(selected)}"]
    row = selected[0]
    errors: list[str] = []
    if row.get("blocking_findings", "").strip():
        errors.append("selected branch still has blocking findings")
    if not row.get("decision_evidence", "").strip():
        errors.append("selected branch has no decision evidence")
    return errors


def cumcm_ai_rule_applies(manifest: dict[str, object]) -> bool:
    if str(manifest.get("competition", "")) != "CUMCM":
        return False
    try:
        return int(str(manifest.get("year", "0"))) >= 2026
    except ValueError:
        return False


def check_cumcm_ai_compliance(workspace: Path, manifest: dict[str, object]) -> list[str]:
    if not cumcm_ai_rule_applies(manifest):
        return []
    errors: list[str] = []
    paper = workspace / "paper"
    metadata_path = paper / "generated" / "metadata.tex"
    metadata = strip_tex_comments(metadata_path.read_text(encoding="utf-8", errors="replace")) if metadata_path.is_file() else ""
    switches = re.findall(r"\\IncludeAIUsageStatement(true|false)\b", metadata)
    if not switches or switches[-1] != "true":
        errors.append("CUMCM 2026+: AI usage statement is not enabled")

    statement_path = paper / "sections" / "09_ai_statement.tex"
    statement = strip_tex_comments(statement_path.read_text(encoding="utf-8", errors="replace")) if statement_path.is_file() else ""
    normalized = re.sub(r"\s+", "", statement)
    if "本参赛队在竞赛过程中使用了AI工具" not in normalized:
        errors.append("CUMCM 2026+: AI statement must truthfully declare use of this Skill/Codex")

    main_path = paper / "main.tex"
    main = strip_tex_comments(main_path.read_text(encoding="utf-8", errors="replace")) if main_path.is_file() else ""
    statement_position = main.find(r"\ifIncludeAIUsageStatement\input")
    bibliography_position = main.find("generated/bibliography.tex")
    if statement_position < 0 or bibliography_position < 0 or statement_position > bibliography_position:
        errors.append("CUMCM 2026+: AI usage statement must appear before references")

    support_manifest = load_json(workspace / "submission" / "support_manifest.json")
    files = support_manifest.get("files")
    normalized_files = {str(item).replace("\\", "/") for item in files} if isinstance(files, list) else set()
    if "paper/build/AI工具使用详情.pdf" not in normalized_files:
        errors.append("CUMCM 2026+: paper/build/AI工具使用详情.pdf is missing from support_manifest.json")
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


def run_build(workspace: Path, competition: str, main_name: str = "main.tex") -> tuple[int, dict[str, object]]:
    script = Path(__file__).with_name("build_latex.py")
    command = [
        sys.executable,
        str(script),
        str(workspace / "paper"),
        "--competition",
        competition,
        "--main",
        main_name,
        "--mode",
        "submission",
    ]
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    report_name = "build_report.json" if main_name == "main.tex" else f"build_report_{Path(main_name).stem}.json"
    return result.returncode, load_json(workspace / "paper" / "build" / report_name)


def finalize(workspace: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_json(workspace / "competition_manifest.json")
    competition = str(manifest.get("competition", ""))
    if competition not in {"CUMCM", "MCM", "ICM"}:
        errors.append("competition manifest is missing or invalid")

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

    citation_exit, citation_output = run_citation_validator(workspace)
    if citation_exit != 0:
        errors.append("citation validator failed")

    checks = {
        "gates": check_gate_status(workspace),
        "official_sources": check_official_sources(workspace),
        "citations": check_citations(workspace),
        "data_provenance": check_data_provenance(workspace),
        "results": check_results(workspace),
        "reproduction": check_reproduction(workspace),
        "evidence_matrix": check_evidence_matrix(workspace),
        "cumcm_ai": check_cumcm_ai_compliance(workspace, manifest),
    }
    for findings in checks.values():
        errors.extend(findings)

    build_exit, build_report = run_build(workspace, competition) if competition else (1, {})
    if build_exit != 0 or build_report.get("status") != "pass":
        errors.append("submission LaTeX build failed")
        errors.extend(str(item) for item in build_report.get("errors", []))

    ai_details_report: dict[str, object] = {"status": "not_applicable"}
    if cumcm_ai_rule_applies(manifest):
        ai_exit, ai_details_report = run_build(workspace, competition, "ai_usage_details.tex")
        if ai_exit != 0 or ai_details_report.get("status") != "pass":
            errors.append("CUMCM AI usage details LaTeX build failed")
            errors.extend(str(item) for item in ai_details_report.get("errors", []))
        else:
            source = Path(str(ai_details_report.get("pdf", "")))
            target = workspace / "paper" / "build" / "AI工具使用详情.pdf"
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                errors.append(f"cannot create AI工具使用详情.pdf: {exc}")
            else:
                ai_details_report["pdf"] = str(target)
                ai_details_report["sha256"] = sha256_file(target)

    package_report: dict[str, object] = {"status": "not_applicable"}
    if competition == "CUMCM":
        package_report = package_workspace(workspace, require_paper=True)
        if package_report.get("status") != "pass":
            errors.append("support package failed")
            errors.extend(str(item) for item in package_report.get("errors", []))

    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    status = "pass" if not errors else "block"
    report = {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "competition": competition,
        "workflow_version": manifest.get("workflow_version"),
        "checks": checks,
        "environment_status": environment_report.get("status"),
        "task_status": task_report.get("status"),
        "innovation_status": innovation_report.get("status"),
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
