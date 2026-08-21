#!/usr/bin/env python3
"""Validate a source-bound competition profile without inferring rules from its name or year."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from build_latex import resolve_poppler_tool
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
PROFILE_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "competition-profile.schema.json"
SCHEMA_KEYS = {
    "$schema", "$id", "title", "description", "type", "const", "enum", "required",
    "properties", "additionalProperties", "items", "minLength", "minimum", "pattern",
}


def load_profile(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def json_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def matches_json_type(value: object, expected: str) -> bool:
    return {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }.get(expected, lambda: False)()


def validate_schema_value(value: object, schema: dict[str, object], location: str = "$") -> list[str]:
    """Validate the JSON-Schema keywords used by competition-profile.schema.json."""
    errors: list[str] = []
    unsupported = sorted(set(schema) - SCHEMA_KEYS)
    if unsupported:
        return [f"competition profile schema uses unsupported keyword(s) at {location}: {', '.join(unsupported)}"]
    if "const" in schema and not json_equal(value, schema["const"]):
        errors.append(f"competition profile schema violation at {location}: must equal {schema['const']!r}")
    choices = schema.get("enum")
    if isinstance(choices, list) and not any(json_equal(value, choice) for choice in choices):
        errors.append(f"competition profile schema violation at {location}: value is not in the allowed enum")

    expected = schema.get("type")
    expected_types = [expected] if isinstance(expected, str) else expected if isinstance(expected, list) else []
    if expected is not None and (
        not expected_types
        or not all(isinstance(item, str) for item in expected_types)
        or not any(matches_json_type(value, item) for item in expected_types)
    ):
        label = " or ".join(str(item) for item in expected_types) or "a valid JSON type"
        errors.append(f"competition profile schema violation at {location}: expected {label}")
        return errors

    if isinstance(value, dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for key in required:
            if key not in value:
                errors.append(f"competition profile schema violation at {location}: missing required property {key}")
        if schema.get("additionalProperties") is False:
            extras = sorted(str(key) for key in value if key not in properties)
            if extras:
                errors.append(
                    f"competition profile schema violation at {location}: additional properties are not allowed: "
                    + ", ".join(extras)
                )
        for key, child in properties.items():
            if key in value and isinstance(child, dict):
                errors.extend(validate_schema_value(value[key], child, f"{location}.{key}"))
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(validate_schema_value(item, schema["items"], f"{location}[{index}]"))
    elif isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"competition profile schema violation at {location}: string is too short")
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                matched = re.search(pattern, value)
            except re.error:
                errors.append(f"competition profile schema pattern is invalid at {location}")
            else:
                if not matched:
                    errors.append(f"competition profile schema violation at {location}: string does not match {pattern}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"competition profile schema violation at {location}: value is below minimum {minimum}")
    return errors


def competition_schema_errors(profile: dict[str, object]) -> list[str]:
    try:
        schema = json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
        if not isinstance(schema, dict):
            raise ValueError("schema root is not an object")
        return validate_schema_value(profile, schema)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return [f"competition profile schema validation could not run: {type(exc).__name__}"]


def checked_artifact_errors(workspace: Path, record: dict[str, object], label: str) -> list[str]:
    try:
        return artifact_errors(workspace, record, label)
    except (OSError, RuntimeError, ValueError) as exc:
        return [f"{label}: artifact evidence could not be checked: {type(exc).__name__}"]


def rule_source_text(workspace: Path, source: dict[str, object], label: str) -> tuple[str | None, str | None]:
    relative = str(source.get("artifact_path", "")).replace("\\", "/").strip()
    try:
        path = (workspace / relative).resolve()
        path.relative_to(workspace)
    except (OSError, RuntimeError, ValueError):
        return None, f"{label}: source artifact path is invalid or escapes workspace"
    if not path.is_file():
        return None, f"{label}: source artifact is missing"
    if path.suffix.lower() == ".pdf":
        pdftotext = resolve_poppler_tool("pdftotext")
        if not pdftotext:
            return None, f"{label}: pdftotext is required to verify a PDF locator"
        try:
            result = subprocess.run(
                [pdftotext, "-layout", str(path), "-"],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except OSError:
            return None, f"{label}: PDF source text extraction failed"
        if result.returncode != 0:
            return None, f"{label}: PDF source text extraction failed"
        return result.stdout, None
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except (OSError, ValueError):
        return None, f"{label}: source artifact could not be read as UTF-8 text"


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def timestamp_error(value: object, label: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"{label} is empty"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{label} is not an ISO timestamp"
    return None


def effective_window_errors(profile: dict[str, object]) -> list[str]:
    parsed: dict[str, datetime | None] = {}
    errors: list[str] = []
    for field in ("effective_from", "effective_to"):
        value = profile.get(field)
        text = value.strip() if isinstance(value, str) else ""
        required = field == "effective_from" and profile.get("status") == "verified"
        if not text:
            parsed[field] = None
            if required:
                errors.append("verified competition profile effective_from is empty")
            continue
        try:
            instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"competition profile {field} is not a valid ISO date or timestamp")
            parsed[field] = None
            continue
        parsed[field] = (
            instant.replace(tzinfo=timezone.utc)
            if instant.tzinfo is None
            else instant.astimezone(timezone.utc)
        )
    start = parsed.get("effective_from")
    end = parsed.get("effective_to")
    if end is not None and start is None:
        errors.append("competition profile effective_to requires a valid effective_from")
    elif start is not None and end is not None and end < start:
        errors.append("competition profile effective_to precedes effective_from")
    return errors


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
    errors.extend(competition_schema_errors(profile))
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
    errors.extend(effective_window_errors(profile))
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
        main = build.get("main_document")
        if not isinstance(main, str) or main != "main.tex":
            errors.append("competition profile main_document must be exactly main.tex inside paper/")

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
        errors.extend(checked_artifact_errors(workspace, source, label))

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
    source_text_cache: dict[str, tuple[str | None, str | None]] = {}
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
        locator = str(binding.get("locator", "")).strip()
        if not locator:
            errors.append(f"{label}: locator is empty")
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"{label}: unknown source_id {source_id or '<empty>'}")
        elif str(binding.get("evidence_sha256", "")).lower() != str(source.get("sha256", "")).lower():
            errors.append(f"{label}: evidence_sha256 does not match bound source artifact")
        if source is not None and locator:
            if source_id not in source_text_cache:
                source_text_cache[source_id] = rule_source_text(workspace, source, label)
            source_text, source_issue = source_text_cache[source_id]
            if source_issue:
                errors.append(source_issue)
            elif source_text is not None and normalized_text(locator) not in normalized_text(source_text):
                errors.append(f"{label}: locator is not present in the bound source artifact")

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
