#!/usr/bin/env python3
"""Validate a source-bound competition profile without inferring rules from its name or year."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from evidence_utils import artifact_errors


PAPER_FIELDS = {
    "format", "max_front_matter_pages", "max_total_pages", "max_body_pages",
    "max_pdf_bytes", "page_size", "table_of_contents_allowed", "anonymous",
}
SUBMISSION_FIELDS = {"support_archive_required", "support_archive_max_bytes"}
AI_FIELDS = {
    "policy_checked", "usage_statement_required", "details_pdf_required", "statement_source", "statement_enable_marker", "statement_position",
    "inline_disclosure_required", "tool_reference_required", "human_verification_required",
    "details_source", "details_filename",
}


def load_profile(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def timestamp_error(value: object, label: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{label} is empty"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{label} is not an ISO timestamp"
    return None


def bound_pointers(requirements: dict[str, object]) -> set[str]:
    """Return rule leaves that the finalizer can execute and therefore need an official binding."""
    pointers: set[str] = set()
    for group, allowed in (("paper", PAPER_FIELDS), ("submission", SUBMISSION_FIELDS), ("ai", AI_FIELDS)):
        values = requirements.get(group)
        if not isinstance(values, dict):
            continue
        for field in allowed:
            value = values.get(field)
            if value is not None:
                pointers.add(f"/requirements/{group}/{field}")
    artifacts = requirements.get("artifacts")
    if isinstance(artifacts, list):
        for index, item in enumerate(artifacts):
            if isinstance(item, dict) and item.get("required") is True:
                pointers.add(f"/requirements/artifacts/{index}")
    return pointers


def validate_competition_profile(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    profile_path = workspace / "compliance" / "competition_profile.json"
    profile = load_profile(profile_path)
    manifest = load_profile(workspace / "competition_manifest.json")
    errors: list[str] = []
    warnings: list[str] = []
    if not profile:
        errors.append("competition profile is missing or invalid JSON")
    if profile.get("schema_version") != 2:
        errors.append("competition profile schema_version must be 2")
    for field in ("profile_id", "competition", "edition"):
        if not str(profile.get(field, "")).strip():
            errors.append(f"competition profile {field} is empty")
    if str(profile.get("competition", "")) != str(manifest.get("competition", "")):
        errors.append("competition profile does not match the workspace competition")
    if str(profile.get("edition", "")) != str(manifest.get("year", "")):
        errors.append("competition profile does not match the workspace edition")
    if profile.get("status") != "verified":
        errors.append("competition profile is not verified")
    timestamp_issue = timestamp_error(profile.get("verified_at"), "competition profile verified_at")
    if timestamp_issue:
        errors.append(timestamp_issue)
    if not str(profile.get("verified_by", "") or "").strip():
        errors.append("competition profile verified_by is empty")

    build = profile.get("build")
    if not isinstance(build, dict):
        errors.append("competition profile build configuration is missing")
    else:
        if build.get("latex_engine") not in {"xelatex", "pdflatex", "lualatex"}:
            errors.append("competition profile latex_engine is invalid")
        main = str(build.get("main_document", "")).replace("\\", "/").strip()
        if not main or main.startswith("/") or ".." in Path(main).parts:
            errors.append("competition profile main_document is unsafe or empty")

    sources = profile.get("sources")
    source_map: dict[str, dict[str, object]] = {}
    if not isinstance(sources, list) or not sources:
        errors.append("competition profile has no official source artifacts")
        sources = []
    for index, source in enumerate(sources, start=1):
        label = f"competition source[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label} is not an object")
            continue
        source_id = str(source.get("source_id", "")).strip()
        if not source_id or source_id in source_map:
            errors.append(f"{label}: source_id is empty or duplicated")
        source_map[source_id] = source
        for field in ("kind", "url"):
            if not str(source.get(field, "")).strip():
                errors.append(f"{label}: {field} is empty")
        errors.extend(artifact_errors(workspace, source, label))

    requirements = profile.get("requirements")
    if not isinstance(requirements, dict):
        errors.append("competition profile requirements is missing")
        requirements = {}
    for group, fields in (("paper", PAPER_FIELDS), ("submission", SUBMISSION_FIELDS), ("ai", AI_FIELDS)):
        value = requirements.get(group)
        if not isinstance(value, dict):
            errors.append(f"competition profile requirements.{group} is missing")
            continue
        missing = fields - set(value)
        if missing:
            errors.append(f"competition profile requirements.{group} lacks fields: {', '.join(sorted(missing))}")
    ai = requirements.get("ai") if isinstance(requirements.get("ai"), dict) else {}
    if ai.get("policy_checked") is not True:
        errors.append("competition profile AI policy has not been checked")
    if ai.get("usage_statement_required") is True and not str(ai.get("statement_source", "") or "").strip():
        errors.append("AI usage statement is required but statement_source is empty")
    if ai.get("usage_statement_required") is True and not str(ai.get("statement_enable_marker", "") or "").strip():
        errors.append("AI usage statement is required but statement_enable_marker is empty")
    if ai.get("details_pdf_required") is True:
        if not str(ai.get("details_source", "") or "").strip():
            errors.append("AI details source is required but empty")
        if not str(ai.get("details_filename", "") or "").strip():
            errors.append("AI details filename is required but empty")
    for field in ("statement_source", "details_source"):
        value = str(ai.get(field, "") or "").replace("\\", "/").strip()
        if value and (not value.startswith("paper/") or ".." in Path(value).parts or Path(value).is_absolute()):
            errors.append(f"competition profile AI {field} must be a safe path inside paper/")
    details_filename = str(ai.get("details_filename", "") or "").replace("\\", "/").strip()
    if details_filename and Path(details_filename).name != details_filename:
        errors.append("competition profile AI details_filename must be a filename, not a path")

    artifacts = requirements.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("competition profile requirements.artifacts is not an array")
        artifacts = []
    artifact_ids: set[str] = set()
    for index, item in enumerate(artifacts):
        label = f"required artifact[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} is invalid")
            continue
        artifact_id = str(item.get("artifact_id", "")).strip()
        if not artifact_id or artifact_id in artifact_ids:
            errors.append(f"{label}: artifact_id is empty or duplicated")
        artifact_ids.add(artifact_id)
        if not isinstance(item.get("required"), bool):
            errors.append(f"{label}: required is not boolean")
        for field in ("source_path", "archive_path"):
            value = str(item.get(field, "")).replace("\\", "/").strip()
            if not value or value.startswith("/") or ".." in Path(value).parts:
                errors.append(f"{label}: {field} is unsafe or empty")

    bindings = profile.get("rule_bindings")
    binding_map: dict[str, dict[str, object]] = {}
    if not isinstance(bindings, list):
        errors.append("competition profile rule_bindings is not an array")
        bindings = []
    for index, binding in enumerate(bindings, start=1):
        label = f"rule binding[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{label} is invalid")
            continue
        pointer = str(binding.get("requirement_pointer", "")).strip()
        source_id = str(binding.get("source_id", "")).strip()
        if not pointer.startswith("/requirements/"):
            errors.append(f"{label}: requirement_pointer is invalid")
        if pointer in binding_map:
            errors.append(f"{label}: duplicate binding for {pointer}")
        binding_map[pointer] = binding
        if not str(binding.get("locator", "")).strip():
            errors.append(f"{label}: locator is empty")
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"{label}: unknown source_id {source_id or '<empty>'}")
        elif str(binding.get("evidence_sha256", "")).lower() != str(source.get("sha256", "")).lower():
            errors.append(f"{label}: evidence_sha256 does not match bound source artifact")

    required_bindings = bound_pointers(requirements)
    missing_bindings = required_bindings - set(binding_map)
    if missing_bindings:
        errors.append("executable requirements lack official source bindings: " + ", ".join(sorted(missing_bindings)))
    unused_bindings = set(binding_map) - required_bindings
    if unused_bindings:
        warnings.append("rule bindings do not affect an active requirement: " + ", ".join(sorted(unused_bindings)))

    report = {
        "status": "pass" if not errors else "block",
        "profile_id": profile.get("profile_id"),
        "bound_requirement_count": len(required_bindings),
        "source_count": len(source_map),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    audit_path = workspace / "audits" / "rules" / "competition_profile_report.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a versioned competition profile and its rule bindings.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_competition_profile(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
