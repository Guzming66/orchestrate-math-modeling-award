#!/usr/bin/env python3
"""Validate task ownership, dependencies, deadlines and final completion."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


DONE = {"done", "waived"}
ALLOWED_STATUS = {"pending", "in_progress", "done", "blocked", "waived"}
V15_REQUIRED_TASK_IDS = {
    "profile-audit",
    "problem-route",
    "semantic-mapper",
    "strong-baseline",
    "baseline-failure",
    "innovation-discovery",
    "innovation-evidence",
    "innovation-critic",
    "innovation-selection",
    "model-freeze",
    "global-claim-draft",
    "global-claim-certification",
    "question-interfaces",
    "review-router",
    "reproduction",
    "paper-payload",
    "paper",
    "citation-audit",
    "scientific-review",
    "paper-presentation",
    "paper-integrity",
    "similarity-precheck",
    "final-pdf-visual-review",
    "submission",
}


def parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def workflow_version(board_path: Path) -> int | None:
    manifest_path = board_path.parent.parent / "competition_manifest.json"
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = document.get("workflow_version") if isinstance(document, dict) else None
    return value if isinstance(value, int) else None


def parse_time(value: str) -> datetime | None:
    if not value.strip():
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_task_board(board_path: Path, final: bool = False) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if not board_path.is_file():
        return {"status": "block", "errors": [f"task board is missing: {board_path}"], "warnings": []}

    with board_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"status": "block", "errors": ["task board has no tasks"], "warnings": []}

    tasks: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        task_id = (row.get("task_id") or "").strip()
        if not task_id:
            errors.append(f"row {row_number}: task_id is empty")
            continue
        if task_id in tasks:
            errors.append(f"duplicate task_id: {task_id}")
            continue
        tasks[task_id] = row

        status = (row.get("status") or "").strip().lower()
        if status not in ALLOWED_STATUS:
            errors.append(f"{task_id}: invalid status '{status}'")
        for field in ("task_type", "assigned_path", "fallback", "deliverables"):
            if not (row.get(field) or "").strip():
                errors.append(f"{task_id}: {field} is empty")
        blocking = parse_bool(row.get("blocking") or "")
        if blocking is None:
            errors.append(f"{task_id}: blocking must be exactly true or false")
        if final and blocking is True:
            if status not in DONE:
                errors.append(f"{task_id}: blocking task is not done or waived")
            for field in ("owner", "due_at", "freeze_at", "evidence"):
                if not (row.get(field) or "").strip():
                    errors.append(f"{task_id}: final review requires {field}")

        for field in ("due_at", "freeze_at"):
            raw = (row.get(field) or "").strip()
            if not raw:
                continue
            try:
                when = parse_time(raw)
            except ValueError:
                errors.append(f"{task_id}: invalid ISO timestamp in {field}: {raw}")
                continue
            if when and when < datetime.now(timezone.utc) and status not in DONE:
                warnings.append(f"{task_id}: {field} has passed while status is {status}")

    graph: dict[str, list[str]] = {}
    for task_id, row in tasks.items():
        dependencies = [item.strip() for item in (row.get("depends_on") or "").split(";") if item.strip()]
        graph[task_id] = dependencies
        for dependency in dependencies:
            if dependency not in tasks:
                errors.append(f"{task_id}: unknown dependency {dependency}")
            elif (row.get("status") or "").strip().lower() in DONE and (
                tasks[dependency].get("status") or ""
            ).strip().lower() not in DONE:
                errors.append(f"{task_id}: marked done before dependency {dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visiting:
            errors.append("dependency cycle: " + " -> ".join(trail + [task_id]))
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph.get(task_id, []):
            if dependency in graph:
                visit(dependency, trail + [task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id, [])

    if workflow_version(board_path) == 15:
        missing = V15_REQUIRED_TASK_IDS - set(tasks)
        if missing:
            errors.append("workflow v15 task board is missing required task IDs: " + ", ".join(sorted(missing)))
        model_tasks = {
            task_id for task_id, row in tasks.items()
            if (row.get("task_type") or "").strip().lower() == "model"
        }
        if not model_tasks:
            errors.append("workflow v15 task board must contain at least one model task")
        freeze_dependencies = set(graph.get("model-freeze", []))
        missing_model_dependencies = model_tasks - freeze_dependencies
        if missing_model_dependencies:
            errors.append(
                "model-freeze does not depend on every model task: "
                + ", ".join(sorted(missing_model_dependencies))
            )
        if "model-freeze" not in set(graph.get("global-claim-draft", [])):
            errors.append("global-claim-draft must depend on model-freeze")
        required_certification_dependencies = {"paper", "reproduction", "global-claim-draft"}
        missing_certification_dependencies = required_certification_dependencies - set(
            graph.get("global-claim-certification", [])
        )
        if missing_certification_dependencies:
            errors.append(
                "global-claim-certification lacks required dependencies: "
                + ", ".join(sorted(missing_certification_dependencies))
            )

    return {
        "status": "pass" if not errors else "block",
        "final_mode": final,
        "task_count": len(tasks),
        "done_count": sum((row.get("status") or "").strip().lower() in DONE for row in tasks.values()),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the modeling task dependency board.")
    parser.add_argument("workspace")
    parser.add_argument("--final", action="store_true", help="Require all blocking tasks to be closed.")
    args = parser.parse_args()

    root = Path(args.workspace).expanduser().resolve()
    report = validate_task_board(root / "shared" / "task_board.csv", final=args.final)
    report_path = root / "audits" / "task_board_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
