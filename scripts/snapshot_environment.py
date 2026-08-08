#!/usr/bin/env python3
"""Capture a secret-free, reproducible Python and LaTeX environment snapshot."""

from __future__ import annotations

import argparse
import json
import platform
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


TOOLS = ("latexmk", "xelatex", "pdflatex", "bibtex", "pdfinfo", "pdftoppm", "pdftotext")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def first_line(output: str) -> str:
    return next((line.strip() for line in output.splitlines() if line.strip()), "")


def resolve_tool(name: str) -> str | None:
    executable = shutil.which(name)
    if not executable:
        return None
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"} and name.startswith("pdf"):
        bundled = path.parents[2] / "native" / "poppler" / "Library" / "bin" / f"{name}.exe"
        if bundled.is_file():
            return str(bundled)
    return executable


def snapshot(workspace: Path) -> dict[str, object]:
    environment_dir = workspace / "environment"
    environment_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    freeze = run([sys.executable, "-m", "pip", "freeze", "--all"])
    lock_path = environment_dir / "requirements-lock.txt"
    if freeze.returncode == 0:
        lock_path.write_text(freeze.stdout, encoding="utf-8")
    else:
        errors.append("pip freeze failed")
        lock_path.write_text("", encoding="utf-8")

    tools: dict[str, object] = {}
    for name in TOOLS:
        executable = resolve_tool(name)
        if not executable:
            tools[name] = {"status": "missing", "path": None, "version": None}
            errors.append(f"required tool is missing: {name}")
            continue
        version_flag = "-v" if name.startswith("pdf") else "--version"
        version = run([executable, version_flag])
        tools[name] = {
            "status": "ok" if version.returncode == 0 else "version_failed",
            "path": executable,
            "version": first_line(version.stdout),
        }
        if version.returncode != 0:
            errors.append(f"unable to read version: {name}")

    result = {
        "status": "pass" if not errors else "block",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "platform": platform.platform(),
        "requirements_lock": str(lock_path.relative_to(workspace)),
        "tools": tools,
        "errors": errors,
    }
    (environment_dir / "environment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot the modeling environment.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    result = snapshot(Path(args.workspace).expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
