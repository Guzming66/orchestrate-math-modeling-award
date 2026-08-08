#!/usr/bin/env python3
"""Build a deterministic support ZIP and block identity or credential leaks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


MAX_SCAN_BYTES = 25_000_000
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I)),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("credential assignment", re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{8,}", re.I)),
    ("absolute user path", re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/][^\\/\s]+|/home/[^/\s]+)", re.I)),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_terms(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and len(line.strip()) >= 3
    ]


def decoded_views(data: bytes) -> list[str]:
    views = []
    for encoding in ("utf-8", "utf-16-le", "latin-1"):
        try:
            views.append(data.decode(encoding, errors="ignore"))
        except LookupError:
            pass
    return views


def scan_text(label: str, text: str, terms: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    lowered = text.casefold()
    for term in terms:
        if term.casefold() in lowered:
            errors.append(f"{label}: forbidden identity term found: {term}")
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{label}: possible {name}")
    if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text):
        warnings.append(f"{label}: email address found; confirm it is not team identity")
    return errors, warnings


def run_text(command: list[str]) -> str:
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def resolve_pdf_tool(name: str) -> str | None:
    executable = shutil.which(name)
    if not executable:
        return None
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        bundled = path.parents[2] / "native" / "poppler" / "Library" / "bin" / f"{name}.exe"
        if bundled.is_file():
            return str(bundled)
    return executable


def scan_file(path: Path, label: str, terms: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    errors_part, warnings_part = scan_text(label, label, terms)
    errors.extend(errors_part)
    warnings.extend(warnings_part)
    if path.stat().st_size > MAX_SCAN_BYTES:
        errors.append(f"{label}: file exceeds per-file scan limit of {MAX_SCAN_BYTES} bytes")
        return errors, warnings

    data = path.read_bytes()
    for index, view in enumerate(decoded_views(data)):
        found_errors, found_warnings = scan_text(f"{label}#encoding{index}", view, terms)
        errors.extend(found_errors)
        warnings.extend(found_warnings)

    if path.suffix.lower() == ".pdf":
        pdftotext = resolve_pdf_tool("pdftotext")
        pdfinfo = resolve_pdf_tool("pdfinfo")
        if pdftotext:
            found_errors, found_warnings = scan_text(label + "#pdftext", run_text([pdftotext, str(path), "-"]), terms)
            errors.extend(found_errors)
            warnings.extend(found_warnings)
        else:
            warnings.append(f"{label}: pdftotext missing; PDF visible text was not scanned")
        if pdfinfo:
            metadata = run_text([pdfinfo, str(path)])
            found_errors, found_warnings = scan_text(label + "#pdfmeta", metadata, terms)
            errors.extend(found_errors)
            warnings.extend(found_warnings)
            author = re.search(r"^Author:\s*(.+)$", metadata, flags=re.MULTILINE | re.I)
            if author and author.group(1).strip():
                errors.append(f"{label}: PDF Author metadata is not empty")
        else:
            warnings.append(f"{label}: pdfinfo missing; PDF metadata was not scanned")

    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        try:
            from PIL import Image

            with Image.open(path) as image:
                metadata = "\n".join(f"{key}={value}" for key, value in {**image.info, **dict(image.getexif())}.items())
            found_errors, found_warnings = scan_text(label + "#imagemeta", metadata, terms)
            errors.extend(found_errors)
            warnings.extend(found_warnings)
            if metadata.strip():
                warnings.append(f"{label}: image metadata exists and needs visual confirmation")
        except Exception as exc:
            warnings.append(f"{label}: image metadata scan failed: {exc}")

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            total = sum(member.file_size for member in archive.infolist())
            if total > 100_000_000:
                errors.append(f"{label}: nested archive expands beyond 100 MB")
            else:
                for member in archive.infolist():
                    found_errors, found_warnings = scan_text(f"{label}!{member.filename}", member.filename, terms)
                    errors.extend(found_errors)
                    warnings.extend(found_warnings)
                    if member.file_size <= MAX_SCAN_BYTES and not member.is_dir():
                        nested = archive.read(member)
                        for view in decoded_views(nested):
                            found_errors, found_warnings = scan_text(f"{label}!{member.filename}", view, terms)
                            errors.extend(found_errors)
                            warnings.extend(found_warnings)
    return sorted(set(errors)), sorted(set(warnings))


def resolve_member(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"manifest path escapes workspace: {relative}") from exc
    return candidate


def package_workspace(
    workspace: Path,
    manifest_path: Path | None = None,
    paper_path: Path | None = None,
    max_bytes: int = 20_000_000,
    require_paper: bool = False,
) -> dict[str, object]:
    manifest_path = manifest_path or workspace / "submission" / "support_manifest.json"
    paper_path = paper_path or workspace / "paper" / "build" / "main.pdf"
    errors: list[str] = []
    warnings: list[str] = []
    files_report: list[dict[str, object]] = []
    terms = read_terms(workspace / "compliance" / "anonymity_terms.txt")
    if not terms:
        errors.append("anonymity_terms.txt has no configured identity terms")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        manifest = {}
        errors.append(f"support manifest cannot be read: {exc}")
    entries = manifest.get("files", []) if isinstance(manifest, dict) else []
    if not isinstance(entries, list) or not entries:
        errors.append("support manifest has no files")
        entries = []

    archive_name = str(manifest.get("archive_name", "support_materials.zip")) if isinstance(manifest, dict) else "support_materials.zip"
    if Path(archive_name).name != archive_name or not archive_name.lower().endswith(".zip"):
        errors.append("archive_name must be a simple .zip filename")
        archive_name = "support_materials.zip"
    archive_path = workspace / "submission" / archive_name
    resolved: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for raw in entries:
        relative = str(raw).replace("\\", "/").strip()
        if not relative or relative in seen:
            errors.append(f"invalid or duplicate manifest entry: {relative!r}")
            continue
        seen.add(relative)
        try:
            source = resolve_member(workspace, relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not source.is_file():
            errors.append(f"support file is missing: {relative}")
            continue
        if relative.startswith("inputs/original/"):
            errors.append(f"original contest attachment must not be repackaged: {relative}")
            continue
        file_errors, file_warnings = scan_file(source, relative, terms)
        errors.extend(file_errors)
        warnings.extend(file_warnings)
        resolved.append((relative, source))
        files_report.append({"path": relative, "size_bytes": source.stat().st_size, "sha256": sha256_file(source)})

    if paper_path.is_file():
        paper_errors, paper_warnings = scan_file(paper_path, "paper/main.pdf", terms)
        errors.extend(paper_errors)
        warnings.extend(paper_warnings)
    elif require_paper:
        errors.append(f"paper PDF is missing: {paper_path}")

    archive_sha256 = None
    archive_size = None
    if not errors:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, source in sorted(resolved):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, source.read_bytes())
        archive_size = archive_path.stat().st_size
        archive_sha256 = sha256_file(archive_path)
        if archive_size > max_bytes:
            errors.append(f"support archive exceeds {max_bytes} bytes")

    report = {
        "status": "pass" if not errors else "block",
        "manifest": str(manifest_path),
        "archive": str(archive_path) if archive_path.exists() else None,
        "archive_size_bytes": archive_size,
        "archive_sha256": archive_sha256,
        "files": files_report,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "submission" / "package_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and scan the support-material archive.")
    parser.add_argument("workspace")
    parser.add_argument("--manifest")
    parser.add_argument("--paper")
    parser.add_argument("--max-bytes", type=int, default=20_000_000)
    parser.add_argument("--require-paper", action="store_true")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    report = package_workspace(
        workspace,
        Path(args.manifest).resolve() if args.manifest else None,
        Path(args.paper).resolve() if args.paper else None,
        args.max_bytes,
        args.require_paper,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
