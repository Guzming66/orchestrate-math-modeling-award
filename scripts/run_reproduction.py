#!/usr/bin/env python3
"""Run the declared clean reproduction in an isolated workspace copy."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from evidence_utils import sha256_file


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def result_paths(workspace: Path) -> set[str]:
    path = workspace / "synthesis" / "result_manifest.csv"
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row.get("relative_path", "").replace("\\", "/").strip()
            for row in csv.DictReader(handle)
            if row.get("relative_path", "").strip()
        }


def within(root: Path, relative: str) -> Path | None:
    path = (root / relative.replace("\\", "/")).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def validate_contract(workspace: Path, document: dict[str, object]) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    if document.get("schema_version") != 2:
        errors.append("reproduction schema_version must be 2")
    if document.get("status") != "ready":
        errors.append("reproduction status must be ready for execution")
    for field in ("reviewer", "checked_at"):
        if not str(document.get(field, "")).strip():
            errors.append(f"reproduction: {field} is empty")
    checked_at = str(document.get("checked_at", "")).strip()
    if checked_at:
        try:
            datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append("reproduction checked_at is not an ISO timestamp")
    if document.get("blocking_findings"):
        errors.append("reproduction blocking findings remain")
    runner = document.get("runner")
    if not isinstance(runner, dict):
        errors.append("reproduction runner is invalid")
        runner = {}
    argv = runner.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        errors.append("reproduction runner argv must be a non-empty string array")
    cwd = str(runner.get("working_directory", ".")).strip() or "."
    if within(workspace, cwd) is None:
        errors.append("reproduction working_directory escapes workspace")
    timeout = runner.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 7200:
        errors.append("reproduction timeout_seconds must be an integer from 1 to 7200")
    clean_paths = runner.get("clean_paths")
    if not isinstance(clean_paths, list) or not clean_paths or any(not str(item).strip() for item in clean_paths):
        errors.append("reproduction clean_paths must be a non-empty array")
        clean_paths = []
    for relative in clean_paths:
        if within(workspace, str(relative)) is None:
            errors.append(f"reproduction clean path escapes workspace: {relative}")

    expected = document.get("expected_artifacts")
    if not isinstance(expected, list) or not expected:
        errors.append("reproduction expected_artifacts is empty")
        expected = []
    expected_paths: set[str] = set()
    for index, artifact in enumerate(expected, start=1):
        label = f"expected reproduction artifact {index}"
        if not isinstance(artifact, dict):
            errors.append(f"{label} is invalid")
            continue
        relative = str(artifact.get("relative_path", "")).replace("\\", "/").strip()
        digest = str(artifact.get("sha256", "")).strip().lower()
        if not relative or within(workspace, relative) is None:
            errors.append(f"{label}: relative_path is empty or escapes workspace")
            continue
        expected_paths.add(relative)
        original = workspace / relative
        if not original.is_file() or sha256_file(original) != digest:
            errors.append(f"{label}: registered source artifact is missing or hash-mismatched")
        if not any(relative == str(clean).replace("\\", "/").rstrip("/") or relative.startswith(str(clean).replace("\\", "/").rstrip("/") + "/") for clean in clean_paths):
            errors.append(f"{label}: artifact is not covered by a clean_path")
    missing = result_paths(workspace) - expected_paths
    if missing:
        errors.append("reproduction expected_artifacts do not cover result manifest paths: " + ", ".join(sorted(missing)))
    return errors, runner


def run_reproduction(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load_json(workspace / "audits" / "reproduction" / "reproduction_status.json")
    errors, runner = validate_contract(workspace, document)
    report: dict[str, object] = {
        "status": "block",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "executed": False,
        "errors": errors,
        "warnings": [],
    }
    if not errors:
        with tempfile.TemporaryDirectory(prefix="mathmodel-repro-") as temporary:
            clone = Path(temporary) / "workspace"

            def ignore(source: str, names: list[str]) -> set[str]:
                relative = Path(source).resolve().relative_to(workspace)
                ignored = {name for name in names if name == "__pycache__" or name.endswith(".pyc")}
                if relative == Path("paper"):
                    ignored.update(name for name in names if name == "build")
                if relative == Path("audits/similarity"):
                    ignored.update(name for name in names if name == "corpus")
                if relative == Path("."):
                    ignored.update(name for name in names if name == "submission")
                return ignored

            shutil.copytree(
                workspace,
                clone,
                ignore=ignore,
            )
            for relative in runner["clean_paths"]:
                target = within(clone, str(relative))
                if target is None:
                    errors.append(f"clean path escapes isolated copy: {relative}")
                    continue
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
            cwd = within(clone, str(runner.get("working_directory", ".")))
            if cwd is None:
                errors.append("working directory escapes isolated copy")
            else:
                cwd.mkdir(parents=True, exist_ok=True)
                started = time.monotonic()
                try:
                    command: list[str] = []
                    source_path_leak = False
                    source_token = str(workspace)
                    for item in runner["argv"]:
                        candidate = Path(item)
                        if candidate.is_absolute():
                            try:
                                relative = candidate.resolve().relative_to(workspace)
                            except ValueError:
                                command.append(item)
                            else:
                                command.append(str(clone / relative))
                        elif source_token.lower() in item.lower():
                            errors.append("reproduction argv embeds the source workspace path")
                            source_path_leak = True
                            command.append(item)
                        else:
                            command.append(item)
                    environment = {
                        key: value
                        for key, value in os.environ.items()
                        if source_token.lower() not in value.lower()
                    }
                    environment.pop("PYTHONPATH", None)
                    environment.pop("PYTHONHOME", None)
                    environment["PYTHONDONTWRITEBYTECODE"] = "1"
                    if not source_path_leak:
                        process = subprocess.run(
                            command,
                            cwd=cwd,
                            env=environment,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            timeout=runner["timeout_seconds"],
                            check=False,
                        )
                        report["executed"] = True
                        report["exit_code"] = process.returncode
                        report["duration_seconds"] = round(time.monotonic() - started, 3)
                        report["output_tail"] = process.stdout[-6000:]
                        if process.returncode != 0:
                            errors.append(f"reproduction command failed with exit code {process.returncode}")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"reproduction command could not complete: {exc}")
            artifact_reports: list[dict[str, object]] = []
            for artifact in document.get("expected_artifacts", []):
                relative = str(artifact["relative_path"]).replace("\\", "/")
                path = clone / relative
                actual = sha256_file(path) if path.is_file() else ""
                expected = str(artifact["sha256"]).lower()
                matched = actual == expected
                artifact_reports.append({"relative_path": relative, "expected_sha256": expected, "actual_sha256": actual, "matched": matched})
                if not matched:
                    errors.append(f"reproduced artifact is missing or hash-mismatched: {relative}")
            report["artifacts"] = artifact_reports
    report["errors"] = sorted(set(errors))
    report["status"] = "pass" if not errors else "block"
    path = workspace / "audits" / "reproduction" / "execution_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute the clean reproduction contract.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = run_reproduction(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
