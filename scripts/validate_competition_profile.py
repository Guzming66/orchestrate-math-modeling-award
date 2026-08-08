#!/usr/bin/env python3
"""Validate a versioned, source-backed competition profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_utils import artifact_errors


COMPETITIONS = {"CUMCM", "MCM", "ICM"}


def load_profile(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_competition_profile(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    profile = load_profile(workspace / "compliance" / "competition_profile.json")
    manifest = load_profile(workspace / "competition_manifest.json")
    if not profile:
        errors.append("competition profile is missing or invalid")
    for field in ("profile_id", "competition", "edition", "status", "effective_from", "verified_at", "verified_by"):
        if not str(profile.get(field, "")).strip():
            errors.append(f"competition profile: {field} is empty")
    if profile.get("schema_version") != 1:
        errors.append("competition profile schema_version must be 1")
    competition = str(profile.get("competition", ""))
    if competition not in COMPETITIONS:
        errors.append("competition profile has an invalid competition")
    if str(profile.get("status", "")).lower() != "verified":
        errors.append("competition profile is not verified")
    if manifest:
        if competition != str(manifest.get("competition", "")):
            errors.append("competition profile does not match manifest competition")
        if str(profile.get("edition", "")) != str(manifest.get("year", "")):
            errors.append("competition profile does not match manifest edition")

    sources = profile.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("competition profile has no official source snapshots")
    else:
        for index, source in enumerate(sources, start=1):
            label = f"competition profile source {index}"
            if not isinstance(source, dict):
                errors.append(f"{label} is invalid")
                continue
            for field in ("kind", "url"):
                if not str(source.get(field, "")).strip():
                    errors.append(f"{label}: {field} is empty")
            errors.extend(artifact_errors(workspace, source, label))

    requirements = profile.get("requirements")
    if not isinstance(requirements, dict):
        errors.append("competition profile requirements are missing")
        requirements = {}
    paper = requirements.get("paper") if isinstance(requirements.get("paper"), dict) else {}
    submission = requirements.get("submission") if isinstance(requirements.get("submission"), dict) else {}
    ai = requirements.get("ai") if isinstance(requirements.get("ai"), dict) else {}
    required_keys = {
        "paper": ("format", "max_front_matter_pages", "max_total_pages", "max_body_pages", "max_pdf_bytes", "page_size", "table_of_contents_allowed", "anonymous"),
        "submission": ("support_archive_required", "support_archive_max_bytes"),
        "ai": (
            "policy_checked", "usage_statement_required", "details_pdf_required",
            "statement_position", "inline_disclosure_required", "tool_reference_required",
            "human_verification_required", "details_filename",
        ),
    }
    for group_name, group, keys in (
        ("paper", paper, required_keys["paper"]),
        ("submission", submission, required_keys["submission"]),
        ("ai", ai, required_keys["ai"]),
    ):
        for key in keys:
            if key not in group:
                errors.append(f"competition profile requirements.{group_name}.{key} is missing")
    for group_name, group, keys in (
        ("paper", paper, ("table_of_contents_allowed", "anonymous")),
        ("submission", submission, ("support_archive_required",)),
        (
            "ai",
            ai,
            (
                "policy_checked", "usage_statement_required", "details_pdf_required",
                "inline_disclosure_required", "tool_reference_required", "human_verification_required",
            ),
        ),
    ):
        for key in keys:
            if key in group and not isinstance(group[key], bool):
                errors.append(f"competition profile requirements.{group_name}.{key} must be boolean")
    for key in ("max_front_matter_pages", "max_total_pages", "max_body_pages", "max_pdf_bytes"):
        value = paper.get(key)
        if value is not None and (not isinstance(value, int) or value <= 0):
            errors.append(f"competition profile requirements.paper.{key} must be null or a positive integer")
    archive_limit = submission.get("support_archive_max_bytes")
    if archive_limit is not None and (not isinstance(archive_limit, int) or archive_limit <= 0):
        errors.append("competition profile requirements.submission.support_archive_max_bytes must be null or a positive integer")
    if str(paper.get("format", "")).strip().lower() != "pdf":
        errors.append("competition profile requirements.paper.format must be pdf")
    if paper.get("page_size") is not None and not str(paper.get("page_size", "")).strip():
        errors.append("competition profile requirements.paper.page_size must be null or nonempty")
    position = ai.get("statement_position")
    if position not in {None, "before_references", "after_references"}:
        errors.append("competition profile requirements.ai.statement_position is invalid")
    if ai.get("usage_statement_required") is True and position is None:
        errors.append("competition profile requires an AI statement position")
    details_filename = ai.get("details_filename")
    if ai.get("details_pdf_required") is True and not str(details_filename or "").strip():
        errors.append("competition profile requires an AI details filename")
    if ai.get("details_pdf_required") is False and details_filename is not None:
        errors.append("competition profile AI details filename must be null when no details PDF is required")

    report = {
        "status": "pass" if not errors else "block",
        "profile_id": profile.get("profile_id"),
        "competition": competition,
        "edition": profile.get("edition"),
        "errors": sorted(set(errors)),
        "warnings": [],
    }
    path = workspace / "audits" / "rules" / "competition_profile_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a source-backed competition profile.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_competition_profile(Path(args.workspace).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
