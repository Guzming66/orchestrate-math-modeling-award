#!/usr/bin/env python3
"""Shared artifact-backed evidence checks."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_errors(
    workspace: Path,
    record: dict[str, object] | dict[str, str],
    label: str,
    *,
    path_field: str = "artifact_path",
    sha_field: str = "sha256",
    check_field: str = "command_or_check",
    time_field: str = "checked_at",
) -> list[str]:
    errors: list[str] = []
    relative = str(record.get(path_field, "")).replace("\\", "/").strip()
    digest = str(record.get(sha_field, "")).strip().lower()
    check = str(record.get(check_field, "")).strip()
    checked_at = str(record.get(time_field, "")).strip()
    for field, value in ((path_field, relative), (sha_field, digest), (check_field, check), (time_field, checked_at)):
        if not value:
            errors.append(f"{label}: {field} is empty")
    if checked_at:
        try:
            datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label}: {time_field} is not an ISO timestamp")
    if not relative:
        return errors
    workspace = workspace.resolve()
    path = (workspace / relative).resolve()
    try:
        path.relative_to(workspace)
    except ValueError:
        errors.append(f"{label}: {path_field} escapes workspace")
        return errors
    if not path.is_file():
        errors.append(f"{label}: artifact is missing: {relative}")
    elif digest and digest != sha256_file(path):
        errors.append(f"{label}: {sha_field} does not match")
    return errors


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]
