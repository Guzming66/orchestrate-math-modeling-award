#!/usr/bin/env python3
"""Render the final PDF and preserve page reviews only while page pixels stay unchanged."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from evidence_utils import sha256_file


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve_pdftoppm() -> str | None:
    found = shutil.which("pdftoppm")
    if not found:
        return None
    path = Path(found).resolve()
    if path.suffix.lower() != ".cmd":
        return str(path)
    candidates = [path.with_suffix(".exe")]
    if len(path.parents) >= 3:
        candidates.append(path.parents[2] / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe")
    return str(next((candidate for candidate in candidates if candidate.is_file()), path))


def validate_review_records(document: dict[str, object], page_hashes: list[str]) -> list[str]:
    errors: list[str] = []
    reviews = document.get("page_reviews")
    if not isinstance(reviews, list) or len(reviews) != len(page_hashes):
        return ["final PDF visual review is incomplete"]
    for page, (review, digest) in enumerate(zip(reviews, page_hashes), start=1):
        label = f"visual review page {page}"
        if not isinstance(review, dict) or review.get("page") != page:
            errors.append(f"{label}: record is missing or out of order")
            continue
        if str(review.get("image_sha256", "")).lower() != digest:
            errors.append(f"{label}: rendered page changed after review")
        if review.get("status") != "pass":
            errors.append(f"{label}: status is not pass")
        for field in ("reviewer", "checked_at"):
            if not str(review.get(field, "")).strip():
                errors.append(f"{label}: {field} is empty")
        checked_at = str(review.get("checked_at", "")).strip()
        if checked_at:
            try:
                datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{label}: checked_at is not an ISO timestamp")
        checks = review.get("checks")
        required = {"crop_and_overlap", "fonts_and_symbols", "equations_tables_figures", "pagination_and_anonymity"}
        if not isinstance(checks, dict) or any(checks.get(key) != "pass" for key in required):
            errors.append(f"{label}: all required visual checks must pass")
    return errors


def render_and_validate_pdf(workspace: Path, pdf_path: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    pdf_path = pdf_path.resolve()
    review_path = workspace / "audits" / "presentation" / "final_pdf_visual_review.json"
    render_dir = workspace / "audits" / "presentation" / "final_pdf_pages"
    previous = load_json(review_path)
    errors: list[str] = []
    try:
        pdf_relative = pdf_path.relative_to(workspace).as_posix()
    except ValueError:
        return {"status": "block", "page_count": 0, "errors": ["final PDF path escapes workspace"], "warnings": []}
    if not pdf_path.is_file():
        return {"status": "block", "page_count": 0, "errors": ["final PDF is missing"], "warnings": []}
    executable = resolve_pdftoppm()
    if not executable:
        errors.append("pdftoppm is required for final PDF visual review")
        page_hashes: list[str] = []
    else:
        with tempfile.TemporaryDirectory(prefix="mathmodel-pages-") as temporary:
            prefix = Path(temporary) / "page"
            result = subprocess.run(
                [executable, "-png", "-r", "150", str(pdf_path), str(prefix)],
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            pages = sorted(
                Path(temporary).glob("page-*.png"),
                key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
            )
            if result.returncode != 0 or not pages:
                errors.append("final PDF page rendering failed")
                page_hashes = []
            else:
                render_dir.mkdir(parents=True, exist_ok=True)
                current_names: set[str] = set()
                page_hashes = []
                for page, source in enumerate(pages, start=1):
                    target = render_dir / f"page-{page:03d}.png"
                    shutil.copy2(source, target)
                    current_names.add(target.name)
                    page_hashes.append(sha256_file(target))
                for stale in render_dir.glob("page-*.png"):
                    if stale.name not in current_names:
                        stale.unlink()

    previous_reviews = previous.get("page_reviews") if isinstance(previous.get("page_reviews"), list) else []
    previous_pdf = str(previous.get("pdf_sha256", "")).lower()
    current_pdf = sha256_file(pdf_path)
    by_page = {
        item.get("page"): item
        for item in previous_reviews
        if isinstance(item, dict) and previous_pdf == current_pdf
    }
    page_reviews: list[dict[str, object]] = []
    for page, digest in enumerate(page_hashes, start=1):
        old = by_page.get(page)
        if isinstance(old, dict) and str(old.get("image_sha256", "")).lower() == digest:
            page_reviews.append(old)
        else:
            page_reviews.append(
                {
                    "page": page,
                    "image_path": f"audits/presentation/final_pdf_pages/page-{page:03d}.png",
                    "image_sha256": digest,
                    "status": "pending",
                    "checks": {
                        "crop_and_overlap": "pending",
                        "fonts_and_symbols": "pending",
                        "equations_tables_figures": "pending",
                        "pagination_and_anonymity": "pending",
                    },
                    "reviewer": "",
                    "checked_at": "",
                    "notes": "",
                }
            )
    document = {
        "schema_version": 1,
        "pdf_path": pdf_relative,
        "pdf_sha256": current_pdf,
        "page_count": len(page_hashes),
        "render_dpi": 150,
        "page_reviews": page_reviews,
    }
    errors.extend(validate_review_records(document, page_hashes))
    document["status"] = "pass" if not errors else "pending"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "pass" if not errors else "block",
        "page_count": len(page_hashes),
        "pdf_sha256": document["pdf_sha256"],
        "review_file": review_path.relative_to(workspace).as_posix(),
        "errors": sorted(set(errors)),
        "warnings": [],
    }
    report_path = workspace / "audits" / "presentation" / "final_pdf_visual_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate final PDF page reviews.")
    parser.add_argument("workspace")
    parser.add_argument("pdf")
    args = parser.parse_args()
    report = render_and_validate_pdf(Path(args.workspace).expanduser(), Path(args.pdf).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
