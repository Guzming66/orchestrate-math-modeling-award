#!/usr/bin/env python3
"""Check that promoted innovation claims appear in the paper with evidence links."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from build_latex import strip_tex_comments
from evidence_utils import artifact_errors, split_ids


STRONG_CLAIM = re.compile(r"首创|首次提出|\bnovel\b|\binnovative\b", re.IGNORECASE)
WEAK_CLAIM = re.compile(r"创新|改进|提升|\bimprov(?:e|ed|ement)\b", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def required(row: dict[str, str], fields: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}: {field} is empty" for field in fields if not row.get(field, "").strip()]


def validate_paper_innovation(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    selection = read_csv(workspace / "innovation" / "selection.csv")
    promoted = {
        row.get("claim_id", "").strip()
        for row in selection
        if row.get("decision", "").strip().lower() == "promote"
    }
    promoted.discard("")
    if not promoted:
        warnings.append("no innovation claim was promoted; strong innovation wording is prohibited")
    rows = read_csv(workspace / "synthesis" / "innovation_claims.csv")
    by_claim: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_claim.setdefault(row.get("claim_id", "").strip(), []).append(row)
    result_ids = {
        row.get("result_id", "").strip()
        for row in read_csv(workspace / "synthesis" / "result_manifest.csv")
        if row.get("status", "").strip().lower() == "verified"
    }
    citation_keys = {
        row.get("citation_key", "").strip()
        for row in read_csv(workspace / "audits" / "citations" / "citation_ledger.csv")
        if row.get("metadata_status", "").strip().lower() == "verified"
        and row.get("support_status", "").strip().lower() == "supported"
    }

    known_markers: set[str] = set()
    for claim_id in sorted(promoted):
        mapped = by_claim.get(claim_id, [])
        if len(mapped) != 1:
            errors.append(f"{claim_id}: exactly one paper innovation record is required; found {len(mapped)}")
            continue
        row = mapped[0]
        errors.extend(
            required(
                row,
                (
                    "claim_id", "claim_sentence", "problem_structure", "reasoning_path",
                    "method_change", "evidence_result_ids", "novelty_source_keys", "paper_section",
                    "paper_anchor", "claim_strength", "status", "artifact_path", "sha256",
                    "command_or_check", "checked_at", "reviewer",
                ),
                claim_id,
            )
        )
        reasoning_path = row.get("reasoning_path", "").strip().lower()
        if reasoning_path == "failure_driven":
            errors.extend(required(row, ("baseline_failure",), claim_id))
        elif reasoning_path == "faithful_formulation":
            errors.extend(required(row, ("semantic_requirement",), claim_id))
        else:
            errors.append(f"{claim_id}: invalid reasoning_path")
        if row.get("status", "").strip().lower() != "verified":
            errors.append(f"{claim_id}: paper innovation record is not verified")
        evidence_ids = split_ids(row.get("evidence_result_ids", ""))
        if not evidence_ids:
            errors.append(f"{claim_id}: evidence_result_ids is empty")
        for result_id in evidence_ids:
            if result_id not in result_ids:
                errors.append(f"{claim_id}: unknown or unverified result_id: {result_id}")
        source_keys = split_ids(row.get("novelty_source_keys", ""))
        if not source_keys:
            errors.append(f"{claim_id}: novelty_source_keys is empty")
        for key in source_keys:
            if key not in citation_keys:
                errors.append(f"{claim_id}: unknown or unverified citation key: {key}")

        section_rel = row.get("paper_section", "").replace("\\", "/").strip()
        artifact_rel = row.get("artifact_path", "").replace("\\", "/").strip()
        if artifact_rel != section_rel:
            errors.append(f"{claim_id}: artifact_path must be the mapped paper_section")
        section = (workspace / section_rel).resolve()
        try:
            section.relative_to(workspace)
        except ValueError:
            errors.append(f"{claim_id}: paper_section escapes workspace")
        else:
            if not section.is_file():
                errors.append(f"{claim_id}: paper_section is missing")
            else:
                text = section.read_text(encoding="utf-8", errors="replace")
                anchor = row.get("paper_anchor", "").strip()
                sentence = row.get("claim_sentence", "").strip()
                if anchor not in text:
                    errors.append(f"{claim_id}: paper anchor is absent from {section_rel}")
                if sentence not in text:
                    errors.append(f"{claim_id}: claim sentence is absent from {section_rel}")
                known_markers.add(anchor)
        errors.extend(artifact_errors(workspace, row, f"{claim_id} paper mapping"))

    paper_sections = workspace / "paper" / "sections"
    for path in paper_sections.rglob("*.tex") if paper_sections.is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            visible = strip_tex_comments(line)
            if STRONG_CLAIM.search(visible) and not any(marker in line for marker in known_markers):
                errors.append(f"unmapped strong innovation claim in {path.relative_to(workspace)}:{line_number}")
            elif WEAK_CLAIM.search(visible) and not any(marker in line for marker in known_markers):
                warnings.append(f"possibly unmapped improvement claim in {path.relative_to(workspace)}:{line_number}")

    for claim_id in sorted(set(by_claim) - promoted):
        if claim_id:
            warnings.append(f"paper innovation record is not promoted: {claim_id}")
    report = {
        "status": "pass" if not errors else "block",
        "promoted_claims": sorted(promoted),
        "mapped_claims": sorted(set(by_claim)),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    path = workspace / "audits" / "innovation" / "paper_innovation_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the paper innovation evidence chain.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_paper_innovation(Path(args.workspace).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
