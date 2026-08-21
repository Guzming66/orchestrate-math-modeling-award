#!/usr/bin/env python3
"""Validate routed scientific, implementation, statistical, uncertainty, and claim review."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from evidence_utils import artifact_errors


REVIEW_TYPES = {"scientific", "implementation", "statistical", "uncertainty", "claims"}
SEVERITIES = {"critical", "major", "minor", "suggestion"}
GENERIC_COVERAGE_TEXT = re.compile(
    r"^(?:review|reviewed|checked|independentlychecked|independentreviewcomplete|pass|"
    r"通过|检查通过|已检查|独立检查|已完成审查|符合要求|不适用)$",
    re.IGNORECASE,
)


def normalized_review_text(value: str) -> str:
    value = re.sub(r"(?i)q\s*\d+|问题[一二三四五六七八九十百\d]+|第[一二三四五六七八九十百\d]+问", "<q>", value)
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", value).lower()


def is_specific_review_text(value: str, minimum: int = 12) -> bool:
    normalized = normalized_review_text(value)
    return len(normalized) >= minimum and GENERIC_COVERAGE_TEXT.fullmatch(normalized) is None


def question_paper_source(workspace: Path, question_id: str) -> Path | None:
    payload = load(workspace / "synthesis" / "paper_payload.json")
    questions = payload.get("questions")
    if isinstance(questions, list):
        for item in questions:
            if not isinstance(item, dict) or str(item.get("question_id", "")).strip() != question_id:
                continue
            relative = str(item.get("paper_section", "")).replace("\\", "/").strip()
            if relative:
                candidate = (workspace / relative).resolve()
                try:
                    candidate.relative_to((workspace / "paper" / "sections").resolve())
                except ValueError:
                    return None
                if candidate.is_file():
                    return candidate
    match = re.fullmatch(r"Q(\d+)", question_id, re.IGNORECASE)
    if not match:
        return None
    number = int(match.group(1))
    folder = workspace / "paper" / "sections" / "questions"
    return next((path for path in (folder / f"q{number:02d}.tex", folder / f"q{number}.tex") if path.is_file()), None)


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def expected_coverage(workspace: Path) -> dict[tuple[str, str], str]:
    route = load(workspace / "synthesis" / "review_route.json")
    expected: dict[tuple[str, str], str] = {}
    if route.get("schema_version") != 1 or route.get("status") != "routed":
        return expected
    questions = route.get("questions")
    if not isinstance(questions, list):
        return expected
    for item in questions:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id", "")).strip()
        reviews = item.get("reviews")
        if not question_id or not isinstance(reviews, dict):
            continue
        for review_type, decision in reviews.items():
            if review_type not in REVIEW_TYPES or not isinstance(decision, dict):
                continue
            expected[(question_id, review_type)] = str(decision.get("status", "")).strip().lower()
    return expected


def validate_review_findings(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load(workspace / "audits" / "review_findings.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 3:
        errors.append("review_findings.json schema_version must be 3")
    if document.get("status") != "reviewed":
        errors.append("independent review is not complete")
    policy = document.get("policy")
    max_accepted_major = policy.get("max_accepted_major") if isinstance(policy, dict) else None
    if not isinstance(max_accepted_major, int) or max_accepted_major < 0:
        errors.append("review policy max_accepted_major must be a non-negative integer")
        max_accepted_major = 0

    expected = expected_coverage(workspace)
    if not expected:
        errors.append("review coverage cannot be checked without a completed review_route.json")
    coverage = document.get("coverage")
    covered: dict[tuple[str, str], str] = {}
    coverage_outcomes: dict[tuple[str, str], str] = {}
    rationale_uses: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    if not isinstance(coverage, list):
        coverage = []
    for item in coverage:
        if not isinstance(item, dict):
            errors.append("invalid review coverage record")
            continue
        question_id = str(item.get("question_id", "")).strip()
        review_type = str(item.get("review_type", "")).strip().lower()
        status = str(item.get("status", "")).strip().lower()
        rationale = str(item.get("rationale", "")).strip()
        key = (question_id, review_type)
        if not question_id:
            errors.append("review coverage question_id is empty")
        if review_type not in REVIEW_TYPES:
            errors.append(f"invalid review type: {review_type or '<empty>'}")
        if key in covered:
            errors.append(f"duplicate review coverage: {question_id}/{review_type}")
        covered[key] = status
        route_status = expected.get(key)
        if route_status is None:
            errors.append(f"review coverage is not routed: {question_id}/{review_type}")
        elif route_status == "required" and status != "pass":
            errors.append(f"{question_id}/{review_type} required review did not pass")
        elif route_status == "not_applicable" and status not in {"pass", "not_applicable"}:
            errors.append(f"{question_id}/{review_type} review is not closed")
        if status not in {"pass", "not_applicable"}:
            errors.append(f"{question_id}/{review_type} coverage is not closed")
        if not rationale:
            errors.append(f"{question_id}/{review_type} coverage rationale is empty")
        elif not is_specific_review_text(rationale):
            errors.append(f"{question_id}/{review_type} coverage rationale is generic")
        else:
            rationale_uses[(review_type, normalized_review_text(rationale))].append(key)

        requires_evidence = route_status == "required" or status == "pass"
        if requires_evidence:
            paper_anchor = str(item.get("paper_anchor", "")).strip()
            concrete_check = str(item.get("concrete_check", "")).strip()
            attack = str(item.get("falsification_or_boundary_attack", "")).strip()
            outcome = str(item.get("outcome", "")).strip().lower()
            for field, value in (
                ("paper_anchor", paper_anchor),
                ("concrete_check", concrete_check),
                ("falsification_or_boundary_attack", attack),
            ):
                if not value:
                    errors.append(f"{question_id}/{review_type} coverage {field} is empty")
            if concrete_check and not is_specific_review_text(concrete_check, minimum=16):
                errors.append(f"{question_id}/{review_type} concrete_check is generic")
            if attack and not is_specific_review_text(attack, minimum=16):
                errors.append(f"{question_id}/{review_type} falsification_or_boundary_attack is generic")
            if outcome not in {"no_material_issue", "finding_recorded"}:
                errors.append(f"{question_id}/{review_type} coverage outcome is invalid")
            else:
                coverage_outcomes[key] = outcome
            source = question_paper_source(workspace, question_id)
            if source is None:
                errors.append(f"{question_id}/{review_type} question paper source is missing")
            elif paper_anchor and paper_anchor not in source.read_text(encoding="utf-8", errors="replace"):
                errors.append(f"{question_id}/{review_type} paper_anchor is absent from its qNN.tex")
            errors.extend(artifact_errors(workspace, item, f"{question_id}/{review_type} coverage evidence"))

    for (review_type, _), uses in rationale_uses.items():
        questions = {question for question, _ in uses}
        if len(questions) >= 2:
            rendered = ", ".join(f"{question}/{kind}" for question, kind in sorted(uses))
            errors.append(f"copied coverage rationale across questions for {review_type}: {rendered}")
    missing = set(expected) - set(covered)
    if missing:
        rendered = ", ".join(f"{question}/{kind}" for question, kind in sorted(missing))
        errors.append(f"review coverage is missing: {rendered}")

    findings = document.get("findings")
    if not isinstance(findings, list):
        errors.append("review findings is not an array")
        findings = []
    accepted_major = 0
    seen: set[str] = set()
    finding_pairs: set[tuple[str, str]] = set()
    known_questions = {question for question, _ in expected}
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
        question_id = str(finding.get("question_id", "")).strip()
        review_type = str(finding.get("review_type", "")).strip().lower()
        severity = str(finding.get("severity", "")).strip().lower()
        status = str(finding.get("status", "")).strip().lower()
        if not question_id:
            errors.append(f"{label}: question_id is empty")
        elif question_id != "GLOBAL" and question_id not in known_questions:
            errors.append(f"{label}: finding references unknown question")
        if review_type not in REVIEW_TYPES:
            errors.append(f"{label}: invalid review_type")
        elif question_id:
            finding_pairs.add((question_id, review_type))
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
            errors.append(f"{label}: major finding remains open")
        if severity == "major" and status == "accepted_risk":
            accepted_major += 1
            for field in ("risk_owner", "impact_scope", "fallback"):
                if not str(finding.get(field, "")).strip():
                    errors.append(f"{label}: accepted major risk requires {field}")
        if severity in {"minor", "suggestion"} and status == "open":
            warnings.append(f"{label}: {severity} finding remains open")
    if accepted_major > max_accepted_major:
        errors.append(f"accepted major risks exceed policy: {accepted_major} > {max_accepted_major}")
    for key, outcome in coverage_outcomes.items():
        has_finding = key in finding_pairs
        rendered = f"{key[0]}/{key[1]}"
        if outcome == "finding_recorded" and not has_finding:
            errors.append(f"{rendered}: coverage says finding_recorded but no finding exists")
        if outcome == "no_material_issue" and has_finding:
            errors.append(f"{rendered}: coverage says no_material_issue but a finding is recorded")

    report = {
        "status": "pass" if not errors else "block",
        "covered_reviews": sorted(f"{question}/{kind}" for question, kind in covered),
        "accepted_major": accepted_major,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "review_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate routed independent contest-paper review.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_review_findings(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
