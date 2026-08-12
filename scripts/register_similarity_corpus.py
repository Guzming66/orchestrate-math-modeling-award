#!/usr/bin/env python3
"""Register local reference texts for the similarity precheck."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from evidence_utils import sha256_file


def register(workspace: Path, inputs: list[Path], source_type: str) -> int:
    workspace = workspace.resolve()
    corpus = workspace / "audits" / "similarity" / "corpus"
    registry = workspace / "audits" / "similarity" / "reference_corpus.csv"
    corpus.mkdir(parents=True, exist_ok=True)
    default_fields = ["source_id", "source_type", "text_path", "sha256", "status", "notes"]
    if registry.is_file():
        with registry.open(encoding="utf-8-sig", newline="") as handle:
            fieldnames = csv.DictReader(handle).fieldnames or default_fields
    else:
        registry.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = default_fields
    rows: list[dict[str, str]] = []
    if registry.is_file():
        with registry.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    by_id = {row.get("source_id", ""): row for row in rows}
    count = 0
    for source in inputs:
        if source.suffix.lower() not in {".txt", ".tex", ".md"} or not source.is_file():
            continue
        digest = sha256_file(source)
        source_id = f"{source_type}-{digest[:12]}"
        target = corpus / f"{source_id}{source.suffix.lower()}"
        if not target.exists():
            shutil.copy2(source, target)
        by_id[source_id] = {
            "source_id": source_id,
            "source_type": source_type,
            "text_path": target.relative_to(workspace).as_posix(),
            "sha256": sha256_file(target),
            "status": "verified",
            "notes": source.name,
        }
        count += 1
    with registry.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(by_id[key] for key in sorted(by_id))
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy and register local texts for similarity precheck.")
    parser.add_argument("workspace")
    parser.add_argument("source", nargs="+")
    parser.add_argument("--type", choices=("excellent_paper", "template"), required=True)
    args = parser.parse_args()
    sources: list[Path] = []
    for raw in args.source:
        path = Path(raw).expanduser()
        if not path.is_dir():
            sources.append(path)
            continue
        combined = sorted(path.rglob("combined.txt")) if args.type == "excellent_paper" else []
        sources.extend(combined or sorted(path.rglob("*")))
    count = register(Path(args.workspace).expanduser(), sources, args.type)
    print(f"Registered {count} reference text(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
