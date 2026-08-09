#!/usr/bin/env python3
"""Check companion skill contracts and the document toolchain."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def skill_candidates(name: str, skill_root: Path) -> list[Path]:
    candidates = [skill_root.parent / name]
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "skills" / name)
    candidates.extend(
        [
            Path.home() / ".codex" / "skills" / name,
            Path.home() / ".agents" / "skills" / name,
        ]
    )
    return candidates


def preflight(workspace: Path | None = None, competition: str = "") -> dict[str, object]:
    skill_root = Path(__file__).resolve().parents[1]
    config = load_json(skill_root / "compatibility.json")
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {}
    minimum = str(config.get("python_minimum", "3.10"))
    match = re.fullmatch(r"(\d+)\.(\d+)", minimum)
    required_python = (int(match.group(1)), int(match.group(2))) if match else (3, 10)
    if sys.version_info[:2] < required_python:
        errors.append(f"Python {minimum}+ is required")
    checks["python"] = sys.version.split()[0]

    companions = config.get("companion_skills")
    if not isinstance(companions, list):
        errors.append("compatibility.json companion_skills is invalid")
        companions = []
    for entry in companions:
        if not isinstance(entry, dict):
            errors.append("invalid companion skill entry")
            continue
        name = str(entry.get("name", ""))
        root = next((path.resolve() for path in skill_candidates(name, skill_root) if path.is_dir()), None)
        checks[name] = str(root) if root else None
        if root is None:
            target = errors if entry.get("required") is True else warnings
            target.append(f"companion skill is missing: {name}")
            continue
        required_files = entry.get("required_files")
        for relative in required_files if isinstance(required_files, list) else []:
            if not (root / str(relative)).is_file():
                errors.append(f"{name}: required file is missing: {relative}")
        marker = str(entry.get("version_marker", "")).strip()
        if marker:
            skill_text = (root / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            if marker not in skill_text:
                errors.append(f"{name}: expected compatibility marker is absent: {marker}")
        flags = entry.get("cli_flags")
        validator = root / "scripts" / "validate_citations.py"
        if isinstance(flags, list) and validator.is_file():
            result = subprocess.run(
                [sys.executable, str(validator), "--help"],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode != 0:
                errors.append(f"{name}: validator --help failed")
            for flag in flags:
                if str(flag) not in result.stdout:
                    errors.append(f"{name}: validator CLI is missing {flag}")

    commands = config.get("commands")
    command_names: list[str] = []
    if isinstance(commands, dict):
        values = commands.get("all")
        if isinstance(values, list):
            command_names.extend(str(item) for item in values)
    if workspace is not None:
        profile = load_json(workspace.resolve() / "compliance" / "competition_profile.json")
        build = profile.get("build")
        if isinstance(build, dict) and str(build.get("latex_engine", "")).strip():
            command_names.append(str(build["latex_engine"]))
    for name in sorted(set(command_names)):
        found = shutil.which(name)
        checks[f"command:{name}"] = found
        if not found:
            errors.append(f"required command is missing: {name}")

    if workspace is not None:
        workspace = workspace.resolve()
        manifest = load_json(workspace / "competition_manifest.json")
        if manifest.get("workflow_version") != config.get("workflow_version"):
            errors.append("workspace workflow_version is incompatible; run migrate_workspace.py")
    report = {
        "status": "pass" if not errors else "block",
        "checks": checks,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    if workspace is not None:
        path = workspace / "audits" / "preflight.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check skill dependencies and the contest toolchain.")
    parser.add_argument("workspace", nargs="?")
    parser.add_argument("--competition", choices=("CUMCM", "MCM", "ICM"), default="")
    args = parser.parse_args()
    report = preflight(Path(args.workspace).expanduser() if args.workspace else None, args.competition)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
