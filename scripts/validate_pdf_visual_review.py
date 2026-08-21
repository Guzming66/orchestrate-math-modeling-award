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


def validate_full_paper_page_fill(
    build_report: dict[str, object], page_count: int, pdf_sha256: str
) -> tuple[list[str], list[float]]:
    """Require a complete build-time page-fill audit for submission papers."""
    if build_report.get("artifact_class") != "full_paper" or build_report.get("mode") != "submission":
        return [], []
    errors: list[str] = []
    if str(build_report.get("sha256", "")).lower() != pdf_sha256.lower():
        errors.append("full-paper build report is not bound to the reviewed PDF")
    raw = build_report.get("page_text_fill")
    if not isinstance(raw, list) or len(raw) != page_count:
        errors.append("full-paper page_text_fill is empty or does not cover every PDF page")
        return errors, []
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1 for value in raw):
        errors.append("full-paper page_text_fill contains an invalid ratio")
        return errors, []
    fills = [float(value) for value in raw]
    return errors, fills


def validated_layout_metrics(build_report: dict[str, object], page_count: int) -> tuple[list[str], list[dict[str, object]]]:
    errors: list[str] = []
    raw = build_report.get("page_layout_metrics")
    if not isinstance(raw, list) or len(raw) != page_count:
        return ["full-paper page_layout_metrics is empty or does not cover every PDF page"], []
    metrics: list[dict[str, object]] = []
    for expected_page, item in enumerate(raw, start=1):
        label = f"page layout metric {expected_page}"
        if not isinstance(item, dict) or item.get("page") != expected_page:
            errors.append(f"{label}: record is missing or out of order")
            continue
        for field in ("content_top_ratio", "content_bottom_ratio", "bottom_blank_ratio"):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                errors.append(f"{label}: {field} is invalid")
        word_count = item.get("word_count")
        if isinstance(word_count, bool) or not isinstance(word_count, int) or word_count < 0:
            errors.append(f"{label}: word_count is invalid")
        excluded = item.get("excluded_footer_word_count")
        if isinstance(excluded, bool) or not isinstance(excluded, int) or excluded < 0:
            errors.append(f"{label}: excluded_footer_word_count is invalid")
        metrics.append(dict(item))
    return errors, metrics


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


def validate_review_records(
    document: dict[str, object],
    page_hashes: list[str],
    layout_metrics: list[dict[str, object]] | None = None,
) -> list[str]:
    errors: list[str] = []
    reviews = document.get("page_reviews")
    if not isinstance(reviews, list) or len(reviews) != len(page_hashes):
        return ["final PDF visual review is incomplete"]
    metrics = layout_metrics or []
    for page, (review, digest) in enumerate(zip(reviews, page_hashes), start=1):
        label = f"visual review page {page}"
        if not isinstance(review, dict) or review.get("page") != page:
            errors.append(f"{label}: record is missing or out of order")
            continue
        if str(review.get("image_sha256", "")).lower() != digest:
            errors.append(f"{label}: rendered page changed after review")
        expected_image = f"audits/presentation/final_pdf_pages/page-{page:03d}.png"
        if str(review.get("image_path", "")).replace("\\", "/").strip() != expected_image:
            errors.append(f"{label}: image_path is not the rendered page artifact")
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
        required = {
            "crop_and_overlap",
            "fonts_and_symbols",
            "equations_tables_figures",
            "plot_readability_and_density",
            "float_flow_and_page_balance",
            "pagination_and_anonymity",
        }
        if not isinstance(checks, dict) or any(checks.get(key) != "pass" for key in required):
            errors.append(f"{label}: all required visual checks must pass")
        if metrics:
            expected_metric = metrics[page - 1]
            if review.get("automated_metrics") != expected_metric:
                errors.append(f"{label}: automated page-layout metrics changed after review")
            flagged = float(expected_metric.get("bottom_blank_ratio", 0.0)) > 0.45
            disposition = str(review.get("layout_disposition", "")).strip()
            if flagged:
                if disposition not in {"intentional_end_matter", "intentional_structure"}:
                    errors.append(f"{label}: sparse page needs an explicit intentional layout disposition")
                if not str(review.get("notes", "")).strip():
                    errors.append(f"{label}: sparse-page disposition needs a concrete note")
            elif disposition != "not_flagged":
                errors.append(f"{label}: unflagged page layout_disposition must be not_flagged")
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
    build_report = load_json(pdf_path.parent / "build_report.json")
    fill_errors, page_text_fill = validate_full_paper_page_fill(build_report, len(page_hashes), current_pdf)
    errors.extend(fill_errors)
    metric_errors, page_layout_metrics = validated_layout_metrics(build_report, len(page_hashes))
    errors.extend(metric_errors)
    by_page = {
        item.get("page"): item
        for item in previous_reviews
        if isinstance(item, dict) and previous_pdf == current_pdf and previous.get("schema_version") == 2
    }
    page_reviews: list[dict[str, object]] = []
    for page, digest in enumerate(page_hashes, start=1):
        old = by_page.get(page)
        automated_metrics = page_layout_metrics[page - 1] if len(page_layout_metrics) == len(page_hashes) else {}
        if (
            isinstance(old, dict)
            and str(old.get("image_sha256", "")).lower() == digest
            and old.get("automated_metrics") == automated_metrics
        ):
            page_reviews.append(old)
        else:
            flagged = bool(automated_metrics) and float(automated_metrics.get("bottom_blank_ratio", 0.0)) > 0.45
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
                        "plot_readability_and_density": "pending",
                        "float_flow_and_page_balance": "pending",
                        "pagination_and_anonymity": "pending",
                    },
                    "automated_metrics": automated_metrics,
                    "layout_disposition": "pending" if flagged else "not_flagged",
                    "reviewer": "",
                    "checked_at": "",
                    "notes": "",
                }
            )
    document = {
        "schema_version": 2,
        "pdf_path": pdf_relative,
        "pdf_sha256": current_pdf,
        "page_count": len(page_hashes),
        "render_dpi": 150,
        "page_text_fill": page_text_fill,
        "page_layout_metrics": page_layout_metrics,
        "page_reviews": page_reviews,
    }
    errors.extend(validate_review_records(document, page_hashes, page_layout_metrics))
    document["status"] = "pass" if not errors else "pending"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "pass" if not errors else "block",
        "page_count": len(page_hashes),
        "pdf_sha256": document["pdf_sha256"],
        "review_file": review_path.relative_to(workspace).as_posix(),
        "page_text_fill": page_text_fill,
        "sparse_pages": [
            int(item["page"])
            for item in page_layout_metrics
            if float(item.get("bottom_blank_ratio", 0.0)) > 0.45
        ],
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
