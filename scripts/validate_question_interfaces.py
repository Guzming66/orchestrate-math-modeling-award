#!/usr/bin/env python3
"""Invalidate downstream questions when frozen upstream result snapshots change."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from evidence_utils import artifact_errors


FINGERPRINT_FIELDS = (
    "question_id", "claim_location", "value", "unit", "relative_path", "generator",
    "command", "input_ids", "seed", "environment_file", "sha256", "status",
)


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_results(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row.get("result_id", "").strip(): row
            for row in csv.DictReader(handle)
            if row.get("result_id", "").strip()
        }


def result_fingerprint(row: dict[str, str]) -> str:
    payload = {field: row.get(field, "").strip() for field in FINGERPRINT_FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_question_interfaces(workspace: Path, *, final: bool = False) -> dict[str, object]:
    workspace = workspace.resolve()
    contract = load_json(workspace / "shared" / "problem_contract.json")
    questions = contract.get("questions")
    expected: set[tuple[str, str]] = set()
    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue
            producers = question.get("upstream_question_ids")
            if not isinstance(producers, list):
                continue
            consumer = str(question.get("question_id", "")).strip()
            expected.update((str(producer).strip(), consumer) for producer in producers)
    document = load_json(workspace / "shared" / "question_interfaces.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("question_interfaces.json schema_version must be 1")
    if final and document.get("status") != "frozen":
        errors.append("question interfaces must be frozen before finalization")
    interfaces = document.get("interfaces")
    if not isinstance(interfaces, list):
        errors.append("question interfaces must be an array")
        interfaces = []
    results = read_results(workspace / "synthesis" / "result_manifest.csv")
    actual: set[tuple[str, str]] = set()
    for index, interface in enumerate(interfaces, start=1):
        label = f"question interface {index}"
        if not isinstance(interface, dict):
            errors.append(f"{label} is invalid")
            continue
        interface_id = str(interface.get("interface_id", "")).strip()
        producer = str(interface.get("producer_question_id", "")).strip()
        consumer = str(interface.get("consumer_question_id", "")).strip()
        edge = (producer, consumer)
        if not interface_id:
            errors.append(f"{label}: interface_id is empty")
        if edge in actual:
            errors.append(f"{label}: duplicate dependency edge {producer}->{consumer}")
        actual.add(edge)
        if edge not in expected:
            errors.append(f"{label}: dependency edge is not declared in problem_contract.json")
        result_ids = interface.get("result_ids")
        if not isinstance(result_ids, list) or not result_ids or any(not isinstance(item, str) or not item.strip() for item in result_ids):
            errors.append(f"{label}: result_ids must be a non-empty array")
            result_ids = []
        fingerprints = interface.get("result_fingerprints")
        if not isinstance(fingerprints, dict):
            errors.append(f"{label}: result_fingerprints must be an object")
            fingerprints = {}
        for result_id_value in result_ids:
            result_id = str(result_id_value).strip()
            row = results.get(result_id)
            if row is None:
                errors.append(f"{label}: unknown result_id {result_id}")
                continue
            if row.get("question_id", "").strip() != producer:
                errors.append(f"{label}: {result_id} does not belong to {producer}")
            current = result_fingerprint(row)
            if str(fingerprints.get(result_id, "")).strip().lower() != current:
                errors.append(f"{label}: upstream result snapshot is stale for {result_id}")
        if set(str(key) for key in fingerprints) != {str(item).strip() for item in result_ids}:
            errors.append(f"{label}: result_fingerprints do not exactly cover result_ids")
        if str(interface.get("status", "")).lower() != "frozen":
            errors.append(f"{label}: status is not frozen")
        if not str(interface.get("reviewer", "")).strip():
            errors.append(f"{label}: reviewer is empty")
        errors.extend(artifact_errors(workspace, interface, f"{label} consumer evidence"))
    if actual != expected:
        missing = sorted(expected - actual)
        if missing:
            errors.append("question interfaces are missing dependency edges: " + ", ".join(f"{a}->{b}" for a, b in missing))

    report = {
        "status": "pass" if not errors else "block",
        "expected_edges": sorted(f"{a}->{b}" for a, b in expected),
        "validated_edges": sorted(f"{a}->{b}" for a, b in actual),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "question_interfaces_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cross-question result snapshots.")
    parser.add_argument("workspace")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    report = validate_question_interfaces(Path(args.workspace).expanduser(), final=args.final)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
