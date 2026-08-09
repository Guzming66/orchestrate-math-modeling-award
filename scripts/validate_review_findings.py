#!/usr/bin/env python3
"""Validate independent scientific, statistical, and claim review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_utils import artifact_errors


REVIEW_TYPES = {"scientific", "statistical", "claims"}
SEVERITIES = {"critical", "major", "minor", "suggestion"}


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_review_findings(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load(workspace / "audits" / "review_findings.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("review_findings.json schema_version must be 1")
    if document.get("status") != "reviewed":
        errors.append("independent review is not complete")
    policy = document.get("policy")
    max_open_major = policy.get("max_open_major") if isinstance(policy, dict) else None
    if not isinstance(max_open_major, int) or max_open_major < 0:
        errors.append("review policy max_open_major must be a non-negative integer")
        max_open_major = 0

    coverage = document.get("coverage")
    covered: set[str] = set()
    if not isinstance(coverage, list):
        coverage = []
    for item in coverage:
        if not isinstance(item, dict):
            errors.append("invalid review coverage record")
            continue
        review_type = str(item.get("review_type", "")).strip().lower()
        status = str(item.get("status", "")).strip().lower()
        rationale = str(item.get("rationale", "")).strip()
        if review_type not in REVIEW_TYPES:
            errors.append(f"invalid review type: {review_type or '<empty>'}")
        else:
            covered.add(review_type)
        if status not in {"pass", "not_applicable"}:
            errors.append(f"{review_type or 'review'} coverage is not closed")
        if not rationale:
            errors.append(f"{review_type or 'review'} coverage rationale is empty")
    missing = REVIEW_TYPES - covered
    if missing:
        errors.append(f"review coverage is missing: {', '.join(sorted(missing))}")

    findings = document.get("findings")
    if not isinstance(findings, list):
        errors.append("review findings is not an array")
        findings = []
    open_major = 0
    seen: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        label = f"finding[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} is invalid")
            continue
        finding_id = str(finding.get("finding_id", "")).strip()
        if not finding_id or finding_id in seen:
            errors.append(f"{label}: finding_id is empty or duplicated")
        seen.add(finding_id)
        label = finding_id or label
        review_type = str(finding.get("review_type", "")).strip().lower()
        severity = str(finding.get("severity", "")).strip().lower()
        status = str(finding.get("status", "")).strip().lower()
        if review_type not in REVIEW_TYPES:
            errors.append(f"{label}: invalid review_type")
        if severity not in SEVERITIES:
            errors.append(f"{label}: invalid severity")
        if status not in {"open", "closed", "accepted_risk"}:
            errors.append(f"{label}: invalid status")
        for field in ("summary", "affected_claim_or_result", "resolution"):
            if not str(finding.get(field, "")).strip():
                errors.append(f"{label}: {field} is empty")
        if severity in {"critical", "major"}:
            errors.extend(artifact_errors(workspace, finding, f"{label} review evidence"))
        if severity == "critical" and status != "closed":
            errors.append(f"{label}: critical finding remains unresolved")
        if severity == "major" and status == "open":
            open_major += 1
        if severity in {"minor", "suggestion"} and status == "open":
            warnings.append(f"{label}: {severity} finding remains open")
    if open_major > max_open_major:
        errors.append(f"open major findings exceed policy: {open_major} > {max_open_major}")

    report = {
        "status": "pass" if not errors else "block",
        "covered_reviews": sorted(covered),
        "open_major": open_major,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "review_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate independent contest-paper review.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_review_findings(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
