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


PROTECTED_CLEAN_PARTS = {"input", "inputs", "code", "src", "scripts", "support", "environment"}
OUTPUT_CLEAN_PARTS = {"result", "results", "figure", "figures", "build", "output", "outputs"}
SCRIPT_SUFFIXES = {".py", ".r", ".jl", ".m", ".sh", ".ps1", ".bat", ".cmd", ".exe", ".ipynb"}
INLINE_EXECUTION_FLAGS = {"-c", "/c", "-command", "--command", "-e", "--eval", "-encodedcommand"}


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
        paths: set[str] = set()
        for row in csv.DictReader(handle):
            raw = row.get("relative_path", "").strip()
            normalized = normalized_path(workspace, raw) if raw else None
            if normalized:
                paths.add(normalized[1])
        return paths


def normalized_path(root: Path, value: str, base: Path | None = None) -> tuple[Path, str] | None:
    raw = value.replace("\\", "/").strip()
    if not raw:
        return None
    supplied = Path(raw)
    path = (supplied if supplied.is_absolute() else (base or root) / supplied).resolve()
    try:
        relative = path.relative_to(root.resolve())
    except ValueError:
        return None
    return path, relative.as_posix() or "."


def within(root: Path, relative: str) -> Path | None:
    normalized = normalized_path(root, relative)
    return normalized[0] if normalized else None


def is_ancestor_or_same(candidate: Path, target: Path) -> bool:
    return candidate == target or candidate in target.parents


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
        argv = []
    cwd = str(runner.get("working_directory", ".")).strip() or "."
    normalized_cwd = normalized_path(workspace, cwd)
    if normalized_cwd is None:
        errors.append("reproduction working_directory escapes workspace")
        cwd_path = workspace
        cwd_relative = "."
    else:
        cwd_path, cwd_relative = normalized_cwd
    timeout = runner.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 7200:
        errors.append("reproduction timeout_seconds must be an integer from 1 to 7200")
    clean_paths = runner.get("clean_paths")
    if not isinstance(clean_paths, list) or not clean_paths or any(not str(item).strip() for item in clean_paths):
        errors.append("reproduction clean_paths must be a non-empty array")
        clean_paths = []
    normalized_clean_paths: list[tuple[Path, str]] = []
    for relative in clean_paths:
        normalized = normalized_path(workspace, str(relative))
        if normalized is None:
            errors.append(f"reproduction clean path escapes workspace: {relative}")
            continue
        path, canonical = normalized
        if canonical == ".":
            errors.append("reproduction clean path cannot be the workspace root")
        elif any(part.lower() in PROTECTED_CLEAN_PARTS for part in Path(canonical).parts):
            errors.append(f"reproduction clean path targets protected inputs, code, or environment: {canonical}")
        elif not any(part.lower() in OUTPUT_CLEAN_PARTS for part in Path(canonical).parts):
            errors.append(f"reproduction clean path must be confined to a named output/results/figures/build location: {canonical}")
        elif is_ancestor_or_same(path, cwd_path):
            errors.append(f"reproduction clean path cannot be the runner working directory or its ancestor: {canonical}")
        if canonical in {item[1] for item in normalized_clean_paths}:
            errors.append(f"duplicate reproduction clean path after normalization: {canonical}")
        else:
            normalized_clean_paths.append((path, canonical))

    entrypoint_value = str(runner.get("entrypoint", "")).strip()
    entrypoint = normalized_path(workspace, entrypoint_value)
    entrypoint_path: Path | None = None
    entrypoint_relative = ""
    if entrypoint is None:
        errors.append("reproduction runner entrypoint is empty or escapes workspace")
    else:
        entrypoint_path, entrypoint_relative = entrypoint
        if not entrypoint_path.is_file():
            errors.append("reproduction runner entrypoint is missing from the workspace")
        elif entrypoint_path.suffix.lower() not in SCRIPT_SUFFIXES and entrypoint_path.name.lower() not in {"makefile", "snakefile"}:
            errors.append("reproduction runner entrypoint must be a script or executable file")
        entrypoint_sha256 = str(runner.get("entrypoint_sha256", "")).strip().lower()
        if len(entrypoint_sha256) != 64 or any(character not in "0123456789abcdef" for character in entrypoint_sha256):
            errors.append("reproduction runner entrypoint_sha256 must be a 64-character hexadecimal digest")
        elif entrypoint_path.is_file() and sha256_file(entrypoint_path) != entrypoint_sha256:
            errors.append("reproduction runner entrypoint is hash-mismatched")
        for clean_path, canonical in normalized_clean_paths:
            if is_ancestor_or_same(clean_path, entrypoint_path):
                errors.append(f"reproduction clean path would delete the runner entrypoint: {canonical}")

    entrypoint_index: int | None = None
    if entrypoint_path is not None:
        for index, item in enumerate(argv):
            candidate = normalized_path(workspace, item, cwd_path)
            if candidate and candidate[0] == entrypoint_path:
                entrypoint_index = index
                break
    if entrypoint_index is None:
        errors.append("reproduction argv must invoke the declared workspace entrypoint")
    elif any(item.strip().lower() in INLINE_EXECUTION_FLAGS for item in argv[1:entrypoint_index]):
        errors.append("reproduction argv cannot use inline command or eval flags before the entrypoint")

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
        supplied_relative = str(artifact.get("relative_path", ""))
        normalized = normalized_path(workspace, supplied_relative)
        digest = str(artifact.get("sha256", "")).strip().lower()
        if normalized is None:
            errors.append(f"{label}: relative_path is empty or escapes workspace")
            continue
        original, relative = normalized
        expected_paths.add(relative)
        if not original.is_file() or sha256_file(original) != digest:
            errors.append(f"{label}: registered source artifact is missing or hash-mismatched")
        if any(part.lower() in PROTECTED_CLEAN_PARTS for part in Path(relative).parts):
            errors.append(f"{label}: output targets protected inputs, code, or environment")
        if not any(is_ancestor_or_same(clean_path, original) for clean_path, _ in normalized_clean_paths):
            errors.append(f"{label}: artifact is outside the declared output clean_paths")
    for clean_path, canonical in normalized_clean_paths:
        if not any(is_ancestor_or_same(clean_path, workspace / relative) for relative in expected_paths):
            errors.append(f"reproduction clean path does not contain an expected output: {canonical}")
    missing = result_paths(workspace) - expected_paths
    if missing:
        errors.append("reproduction expected_artifacts do not cover result manifest paths: " + ", ".join(sorted(missing)))
    normalized_runner = dict(runner)
    normalized_runner["working_directory"] = cwd_relative
    normalized_runner["clean_paths"] = [canonical for _, canonical in normalized_clean_paths]
    normalized_runner["entrypoint"] = entrypoint_relative
    return errors, normalized_runner


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
                normalized = normalized_path(workspace, str(artifact["relative_path"]))
                if normalized is None:
                    continue
                relative = normalized[1]
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
