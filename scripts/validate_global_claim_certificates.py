#!/usr/bin/env python3
"""Validate evidence-backed obligations for first-event and full-domain claims.

This validator checks certificate completeness and artifact identity.  It does not
prove the mathematical claim, the completeness argument, or the correctness of
the referenced computation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from evidence_utils import artifact_errors
from latex_sources import loaded_tex_sources


CLAIM_TYPES = {
    "first_event",
    "earliest",
    "global_minimum",
    "global_maximum",
    "optimal",
    "full_domain_safety",
    "other_global",
}
COVERAGE_STRATEGIES = {
    "analytical_exhaustion",
    "event_partition",
    "candidate_enumeration",
    "interval_subdivision",
    "monotonicity_reduction",
    "bounded_global_search",
    "hybrid",
    "other",
}
CHECK_TYPES = ("endpoints", "nonsmooth", "interior")
REQUIRED_CHECKS_BY_STRATEGY = {
    "analytical_exhaustion": {"endpoints", "interior"},
    "event_partition": set(CHECK_TYPES),
    "candidate_enumeration": set(),
    "interval_subdivision": {"endpoints", "interior"},
    "monotonicity_reduction": {"endpoints", "interior"},
    "bounded_global_search": {"endpoints", "interior"},
    "hybrid": set(CHECK_TYPES),
}
LOCAL_CLAIM_WINDOW_CHARS = 600
VALIDATION_SCOPE = (
    "Certificate structure, local claim-text/locator correspondence, paper-occurrence mapping, "
    "strategy-routed check presence, artifact existence, timestamps, and SHA-256 identity only; "
    "this report does not prove mathematical correctness, global coverage, optimality, safety, "
    "or truth of any claim."
)
DETECTION_SCOPE = (
    "Automatic occurrence discovery is a finite regular-expression sentinel over statically loaded "
    "paper TeX only. Frozen result artifacts and equivalent wording outside this vocabulary require "
    "a human inventory; the sentinel is not a complete strong-claim detector."
)
STRONG_CLAIM_PATTERN = re.compile(
    r"(?:全(?:局|域)(?:最大(?:值)?|最小(?:值)?|最优(?:解|方案|值)?|安全)|"
    r"绝对(?:最大|最小)(?:值)?|最优解|首次(?:发生|接触|碰撞|达到|进入|离开|出现|相交)|"
    r"最早(?:时刻|时间)|全(?:程|过程)(?:均|内|中)?(?:安全|无碰撞)|"
    r"最小(?:螺距|值|成本|时间|距离|半径)|"
    r"global(?:ly)?\s+(?:minimum|maximum|optimum|optimal(?:\s+(?:solution|value|plan))?)|"
    r"absolute\s+(?:minimum|maximum)|optimal\s+solution|"
    r"first\s+(?:event|contact|collision)|earliest\s+time|safe\s+over\s+the\s+full\s+domain)",
    re.IGNORECASE,
)


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def workspace_file(workspace: Path, relative: object, label: str) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    text = str(relative or "").replace("\\", "/").strip()
    if not text:
        return None, [f"{label}: path is empty"]
    path = (workspace / text).resolve()
    try:
        path.relative_to(workspace)
    except ValueError:
        return None, [f"{label}: path escapes workspace"]
    if not path.is_file():
        errors.append(f"{label}: source is missing: {text}")
        return None, errors
    return path, errors


def normalized_tex_with_offsets(text: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    index = 0
    while index < len(text):
        if text[index] == "\\":
            next_index = index + 1
            if next_index < len(text) and (text[next_index].isalpha() or text[next_index] == "@"):
                while next_index < len(text) and (text[next_index].isalpha() or text[next_index] == "@"):
                    next_index += 1
                if next_index < len(text) and text[next_index] == "*":
                    next_index += 1
                index = next_index
                continue
            index += 1
            continue
        if text[index].isalnum():
            normalized.append(text[index].lower())
            offsets.append(index)
        index += 1
    return "".join(normalized), offsets


def normalized_tex(text: str) -> str:
    return normalized_tex_with_offsets(text)[0]


def source_errors(
    workspace: Path,
    location: dict[str, object],
    claim_text: str,
    occurrences_by_source: dict[str, list[dict[str, object]]],
    label: str,
) -> tuple[list[str], tuple[str, int, int] | None]:
    path, errors = workspace_file(workspace, location.get("source_path"), label)
    locator = str(location.get("locator", "")).strip()
    if not locator:
        errors.append(f"{label}: locator is empty")
    if path is None or not locator:
        return errors, None
    try:
        source = strip_tex_comments(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        errors.append(f"{label}: source must be a UTF-8 text artifact")
        return errors, None

    locator_positions = [match.start() for match in re.finditer(re.escape(locator), source)]
    if not locator_positions:
        errors.append(f"{label}: locator is not present in source")
        return errors, None
    if len(locator_positions) > 1:
        errors.append(f"{label}: locator is ambiguous in source")
        return errors, None

    normalized_claim = normalized_tex(claim_text)
    if len(normalized_claim) < 6:
        errors.append(f"{label}: claim_text must state one specific strong claim")
        return errors, None
    normalized_source, offsets = normalized_tex_with_offsets(source)
    claim_spans: list[tuple[int, int]] = []
    search_from = 0
    while True:
        found = normalized_source.find(normalized_claim, search_from)
        if found < 0:
            break
        claim_spans.append((offsets[found], offsets[found + len(normalized_claim) - 1] + 1))
        search_from = found + 1
    locator_position = locator_positions[0]
    local_start = max(0, locator_position - LOCAL_CLAIM_WINDOW_CHARS)
    local_end = min(len(source), locator_position + len(locator) + LOCAL_CLAIM_WINDOW_CHARS)
    local_spans = [span for span in claim_spans if span[0] >= local_start and span[1] <= local_end]
    if not local_spans:
        errors.append(f"{label}: claim_text is not present near locator")
        return errors, None
    if len(local_spans) > 1:
        errors.append(f"{label}: claim_text is ambiguous near locator")
        return errors, None

    relative = path.relative_to(workspace).as_posix()
    claim_start, claim_end = local_spans[0]
    if not (relative.startswith("paper/") and path.suffix.lower() == ".tex"):
        return errors, None
    mapped = [
        occurrence
        for occurrence in occurrences_by_source.get(relative, [])
        if int(occurrence["start"]) < claim_end and int(occurrence["end"]) > claim_start
    ]
    if len(mapped) > 1 or (STRONG_CLAIM_PATTERN.search(claim_text) and len(mapped) != 1):
        errors.append(f"{label}: claim_text must map to exactly one detected strong-claim occurrence")
        return errors, None
    if not mapped:
        return errors, None
    occurrence = mapped[0]
    return errors, (relative, int(occurrence["start"]), int(occurrence["end"]))


def known_questions(workspace: Path) -> set[str]:
    selection = load(workspace / "synthesis" / "model_selection.json")
    questions = selection.get("questions")
    if not isinstance(questions, list):
        return set()
    return {
        str(item.get("question_id", "")).strip()
        for item in questions
        if isinstance(item, dict) and str(item.get("question_id", "")).strip()
    }


def strip_tex_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def detected_strong_claim_occurrences(workspace: Path) -> list[dict[str, object]]:
    paper = workspace / "paper"
    if not paper.is_dir():
        return []
    found: list[dict[str, object]] = []
    for path in loaded_tex_sources(paper):
        if path.name == "ai_usage_details.tex":
            continue
        text = strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))
        relative = path.relative_to(workspace).as_posix()
        for match in STRONG_CLAIM_PATTERN.finditer(text):
            found.append(
                {
                    "source_path": relative,
                    "start": match.start(),
                    "end": match.end(),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "matched_text": match.group(0),
                }
            )
    return found


def validate_claim(
    workspace: Path,
    claim: dict[str, object],
    label: str,
    questions: set[str],
    occurrences_by_source: dict[str, list[dict[str, object]]],
    errors: list[str],
    warnings: list[str],
) -> set[tuple[str, int, int]]:
    mapped_occurrences: set[tuple[str, int, int]] = set()
    question_id = str(claim.get("question_id", "")).strip()
    if not question_id:
        errors.append(f"{label}: question_id is empty")
    elif question_id != "GLOBAL" and questions and question_id not in questions:
        errors.append(f"{label}: question_id is not present in model_selection.json")
    if str(claim.get("claim_type", "")).strip() not in CLAIM_TYPES:
        errors.append(f"{label}: invalid claim_type")
    if not nonempty(claim.get("claim_text")):
        errors.append(f"{label}: claim_text is empty")
    if claim.get("status") != "supported":
        errors.append(f"{label}: claim certificate is not supported")

    locations = claim.get("locations")
    if not isinstance(locations, list) or not locations:
        errors.append(f"{label}: no paper or result location is recorded")
    else:
        seen_locations: set[tuple[str, str]] = set()
        for index, location in enumerate(locations, start=1):
            if not isinstance(location, dict):
                errors.append(f"{label}/location[{index}]: invalid location")
                continue
            key = (str(location.get("source_path", "")).strip(), str(location.get("locator", "")).strip())
            if key in seen_locations:
                errors.append(f"{label}: duplicate source location")
            seen_locations.add(key)
            location_errors, occurrence = source_errors(
                workspace,
                location,
                str(claim.get("claim_text", "")),
                occurrences_by_source,
                f"{label}/location[{index}]",
            )
            errors.extend(location_errors)
            if occurrence is not None:
                if occurrence in mapped_occurrences:
                    errors.append(f"{label}: multiple locations map to the same strong-claim occurrence")
                mapped_occurrences.add(occurrence)

    domain = claim.get("domain")
    if not isinstance(domain, dict):
        errors.append(f"{label}: domain is missing")
    else:
        variables = domain.get("variables")
        if not isinstance(variables, list) or not variables or any(not nonempty(value) for value in variables):
            errors.append(f"{label}: domain.variables is empty or invalid")
        elif len({str(value).strip() for value in variables}) != len(variables):
            errors.append(f"{label}: domain.variables contains duplicates")
        for field in ("bounds_or_set", "inclusions_exclusions"):
            if not nonempty(domain.get(field)):
                errors.append(f"{label}: domain.{field} is empty")

    coverage = claim.get("coverage")
    if not isinstance(coverage, dict):
        errors.append(f"{label}: coverage is missing")
    else:
        if str(coverage.get("strategy", "")).strip() not in COVERAGE_STRATEGIES:
            errors.append(f"{label}: invalid coverage.strategy")
        for field in ("candidate_partition_or_coverage", "completeness_argument"):
            if not nonempty(coverage.get(field)):
                errors.append(f"{label}: coverage.{field} is empty")

    evidence = claim.get("evidence")
    evidence_ids: set[str] = set()
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{label}: artifact-backed evidence is empty")
        evidence = []
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}/evidence[{index}]: invalid evidence record")
            continue
        evidence_id = str(item.get("evidence_id", "")).strip()
        if not evidence_id or evidence_id in evidence_ids:
            errors.append(f"{label}: evidence_id is empty or duplicated")
        evidence_ids.add(evidence_id)
        if not nonempty(item.get("supports")):
            errors.append(f"{label}/{evidence_id or '<empty>'}: supports is empty")
        errors.extend(artifact_errors(workspace, item, f"{label}/{evidence_id or '<empty>'} evidence"))

    checks = claim.get("checks")
    strategy = str(coverage.get("strategy", "")).strip() if isinstance(coverage, dict) else ""
    required_checks = REQUIRED_CHECKS_BY_STRATEGY.get(strategy, set())
    passed: set[str] = set()
    if not isinstance(checks, dict):
        errors.append(f"{label}: endpoint, nonsmooth, and interior checks are missing")
        checks = {}
    for check_type in CHECK_TYPES:
        check = checks.get(check_type)
        check_label = f"{label}/{check_type}"
        if not isinstance(check, dict):
            errors.append(f"{check_label}: check is missing")
            continue
        status = str(check.get("status", "")).strip()
        if status not in {"pass", "not_applicable"}:
            errors.append(f"{check_label}: status must be pass or not_applicable")
        if not nonempty(check.get("summary")):
            errors.append(f"{check_label}: summary is empty")
        references = check.get("evidence_ids")
        if not isinstance(references, list):
            errors.append(f"{check_label}: evidence_ids is not an array")
            references = []
        if status == "pass":
            passed.add(check_type)
            if not references:
                errors.append(f"{check_label}: a passing check needs evidence_ids")
        unknown = {str(value).strip() for value in references if str(value).strip()} - evidence_ids
        if unknown:
            errors.append(f"{check_label}: unknown evidence_ids: {', '.join(sorted(unknown))}")
    missing_required = required_checks - passed
    if missing_required:
        errors.append(
            f"{label}: {strategy} coverage requires passing checks: {', '.join(sorted(missing_required))}"
        )
    if strategy == "other" and not passed:
        errors.append(f"{label}: other coverage requires at least one passing check")

    for field in ("exclusion_argument", "scope_limitations"):
        if not nonempty(claim.get(field)):
            errors.append(f"{label}: {field} is empty")
    if evidence_ids and not questions and question_id != "GLOBAL":
        warnings.append(f"{label}: model-selection questions were unavailable for cross-checking")
    return mapped_occurrences


def validate_global_claim_certificates(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    document = load(workspace / "synthesis" / "global_claim_certificates.json")
    errors: list[str] = []
    warnings: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("global_claim_certificates.json schema_version must be 1")
    status = str(document.get("status", "")).strip()
    claims = document.get("claims")
    if not isinstance(claims, list):
        errors.append("global claim certificates claims is not an array")
        claims = []

    detected_occurrences = detected_strong_claim_occurrences(workspace)
    detected_sources = {str(item["source_path"]) for item in detected_occurrences}
    occurrences_by_source: dict[str, list[dict[str, object]]] = {}
    for occurrence in detected_occurrences:
        occurrences_by_source.setdefault(str(occurrence["source_path"]), []).append(occurrence)
    if status == "draft":
        errors.append("global claim certificates are still draft")
    elif status == "not_applicable":
        if claims:
            errors.append("not_applicable global claim certificates must not contain claims")
        if not nonempty(document.get("no_strong_claims_rationale")):
            errors.append("not_applicable status requires no_strong_claims_rationale")
        if detected_sources:
            errors.append(
                "not_applicable conflicts with strong first/global/full-domain wording in: "
                + ", ".join(sorted(detected_sources))
            )
    elif status != "complete":
        errors.append("global claim certificates status must be complete or not_applicable")
    elif not claims:
        errors.append("complete global claim certificates have no claims")

    seen: set[str] = set()
    mapped_occurrences: set[tuple[str, int, int]] = set()
    questions = known_questions(workspace)
    for index, claim in enumerate(claims, start=1):
        label = f"claim[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{label}: invalid claim certificate")
            continue
        claim_id = str(claim.get("claim_id", "")).strip()
        if not claim_id or claim_id in seen:
            errors.append(f"{label}: claim_id is empty or duplicated")
        seen.add(claim_id)
        claim_occurrences = validate_claim(
            workspace,
            claim,
            claim_id or label,
            questions,
            occurrences_by_source,
            errors,
            warnings,
        )
        duplicates = mapped_occurrences & claim_occurrences
        if duplicates:
            errors.append(f"{claim_id or label}: strong-claim occurrence is mapped by multiple certificates")
        mapped_occurrences.update(claim_occurrences)

    uncovered = [
        item
        for item in detected_occurrences
        if (str(item["source_path"]), int(item["start"]), int(item["end"])) not in mapped_occurrences
    ]
    if status == "complete" and uncovered:
        errors.append(
            "strong first/global/full-domain wording is not mapped at these occurrences: "
            + ", ".join(
                f"{item['source_path']}:{item['line']} ({item['matched_text']})" for item in uncovered
            )
        )

    report = {
        "status": "pass" if not errors else "block",
        "claim_count": len(claims),
        "supported_claims": sorted(
            str(claim.get("claim_id", "")).strip()
            for claim in claims
            if isinstance(claim, dict) and claim.get("status") == "supported"
        ),
        "detected_strong_claim_sources": sorted(detected_sources),
        "detected_strong_claim_occurrences": [
            {
                "source_path": item["source_path"],
                "line": item["line"],
                "matched_text": item["matched_text"],
                "mapped": (
                    str(item["source_path"]), int(item["start"]), int(item["end"])
                ) in mapped_occurrences,
            }
            for item in detected_occurrences
        ],
        "validation_scope": VALIDATION_SCOPE,
        "detection_scope": DETECTION_SCOPE,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "global_claim_certificate_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate first-event and full-domain claim certificates.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_global_claim_certificates(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
