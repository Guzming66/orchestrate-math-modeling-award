#!/usr/bin/env python3
"""Build a direct-LaTeX contest paper and fail closed on submission defects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ENGINE_BY_COMPETITION = {
    "CUMCM": "xelatex",
    "MCM": "pdflatex",
    "ICM": "pdflatex",
}
PLACEHOLDERS = ("DRAFT TITLE", "DRAFT KEYWORDS", "DRAFT CONTENT", "0000000")
BLOCKING_LOG_PATTERNS = (
    (r"^! LaTeX Error:", "LaTeX error"),
    (r"Undefined control sequence", "undefined control sequence"),
    (r"Emergency stop", "TeX emergency stop"),
    (r"Fatal error", "fatal TeX error"),
    (r"LaTeX Warning: Citation .+ undefined", "undefined citation"),
    (r"LaTeX Warning: Reference .+ undefined", "undefined reference"),
    (r"There were undefined references", "undefined references remain"),
    (r"Label\(s\) may have changed.*Rerun", "cross-references need another run"),
)


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def fallback_build(paper_dir: Path, main: Path, engine: str, build_dir: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["TEXINPUTS"] = str(paper_dir) + os.pathsep + environment.get("TEXINPUTS", "")
    environment["BIBINPUTS"] = str(paper_dir) + os.pathsep + environment.get("BIBINPUTS", "")
    command = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-output-directory={build_dir}",
        main.name,
    ]
    outputs: list[str] = []
    result = run(command, paper_dir, environment)
    outputs.append(result.stdout)
    if result.returncode != 0:
        result.stdout = "\n".join(outputs)
        return result

    aux_path = build_dir / f"{main.stem}.aux"
    if aux_path.exists() and "\\bibdata" in aux_path.read_text(encoding="utf-8", errors="replace"):
        bibtex = shutil.which("bibtex")
        if not bibtex:
            return subprocess.CompletedProcess(command, 1, "\n".join(outputs) + "\nbibtex is missing")
        bib_result = run([bibtex, str(build_dir / main.stem)], paper_dir, environment)
        outputs.append(bib_result.stdout)
        if bib_result.returncode != 0:
            bib_result.stdout = "\n".join(outputs)
            return bib_result

    for _ in range(2):
        result = run(command, paper_dir, environment)
        outputs.append(result.stdout)
        if result.returncode != 0:
            break
    result.stdout = "\n".join(outputs)
    return result


def compile_paper(paper_dir: Path, main: Path, engine: str, build_dir: Path) -> subprocess.CompletedProcess[str]:
    latexmk = shutil.which("latexmk")
    if latexmk:
        engine_flag = "-xelatex" if engine == "xelatex" else "-pdf"
        return run(
            [
                latexmk,
                engine_flag,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={build_dir}",
                main.name,
            ],
            paper_dir,
        )
    return fallback_build(paper_dir, main, engine, build_dir)


def strip_tex_comments(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        index = 0
        while True:
            marker = line.find("%", index)
            if marker < 0:
                cleaned.append(line)
                break
            backslashes = 0
            cursor = marker - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cleaned.append(line[:marker])
                break
            index = marker + 1
    return "\n".join(cleaned)


def scan_sources(
    paper_dir: Path,
    mode: str,
    competition: str,
    main_name: str,
) -> list[str]:
    if mode != "submission":
        return []
    errors: list[str] = []
    for path in paper_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".tex", ".bib"}:
            continue
        if "build" in path.relative_to(paper_dir).parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                errors.append(f"placeholder '{placeholder}' remains in {path.relative_to(paper_dir)}")
    return errors


def scan_log(log_text: str, mode: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for pattern, message in BLOCKING_LOG_PATTERNS:
        if re.search(pattern, log_text, flags=re.MULTILINE | re.IGNORECASE):
            errors.append(message)

    missing_chars = re.findall(r"Missing character: There is no .+", log_text)
    if missing_chars:
        target = errors if mode == "submission" else warnings
        target.append(f"{len(missing_chars)} missing-character warning(s)")

    overfull = [float(value) for value in re.findall(r"Overfull \\hbox \(([0-9.]+)pt too wide\)", log_text)]
    if overfull:
        maximum = max(overfull)
        message = f"{len(overfull)} overfull box(es), maximum {maximum:.2f}pt"
        if mode == "submission" and maximum > 5.0:
            errors.append(message)
        else:
            warnings.append(message)

    if re.search(r"multiply defined", log_text, flags=re.IGNORECASE):
        target = errors if mode == "submission" else warnings
        target.append("multiply defined labels")
    return errors, warnings


def pdf_metadata(pdf_path: Path) -> tuple[dict[str, object], str | None]:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return {}, "pdfinfo is missing"
    pdfinfo_path = Path(pdfinfo)
    if os.name == "nt" and pdfinfo_path.suffix.lower() in {".cmd", ".bat"}:
        bundled_exe = pdfinfo_path.parents[2] / "native" / "poppler" / "Library" / "bin" / "pdfinfo.exe"
        if bundled_exe.is_file():
            pdfinfo = str(bundled_exe)
    command = [pdfinfo, str(pdf_path)]
    result = run(command, pdf_path.parent)
    if result.returncode != 0:
        return {}, "pdfinfo failed"
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    pages_match = re.search(r"^Pages:\s+(\d+)", result.stdout, flags=re.MULTILINE | re.IGNORECASE)
    size_match = re.search(
        r"^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts",
        result.stdout,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    metadata: dict[str, object] = {
        "pages": int(pages_match.group(1)) if pages_match else None,
        "page_width_points": float(size_match.group(1)) if size_match else None,
        "page_height_points": float(size_match.group(2)) if size_match else None,
        "author": fields.get("author", ""),
        "title": fields.get("title", ""),
        "subject": fields.get("subject", ""),
        "keywords": fields.get("keywords", ""),
    }
    return metadata, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile and audit a direct-LaTeX contest paper.")
    parser.add_argument("paper_dir", help="Directory containing main.tex")
    parser.add_argument("--competition", required=True, choices=tuple(ENGINE_BY_COMPETITION))
    parser.add_argument("--mode", choices=("draft", "submission"), default="draft")
    parser.add_argument("--main", default="main.tex")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paper_dir = Path(args.paper_dir).expanduser().resolve()
    main_path = paper_dir / args.main
    build_dir = paper_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    if main_path.stem == "main":
        report_path = build_dir / "build_report.json"
        stdout_path = build_dir / "build_stdout.log"
    else:
        report_path = build_dir / f"build_report_{main_path.stem}.json"
        stdout_path = build_dir / f"build_stdout_{main_path.stem}.log"

    errors = scan_sources(paper_dir, args.mode, args.competition, main_path.name)
    warnings: list[str] = []
    engine = ENGINE_BY_COMPETITION[args.competition]
    if not main_path.is_file():
        errors.append(f"main file is missing: {main_path}")
        result = subprocess.CompletedProcess([], 1, "")
    elif not shutil.which(engine):
        errors.append(f"LaTeX engine is missing: {engine}")
        result = subprocess.CompletedProcess([], 1, "")
    else:
        result = compile_paper(paper_dir, main_path, engine, build_dir)
        stdout_path.write_text(result.stdout, encoding="utf-8")
        if result.returncode != 0:
            errors.append(f"compiler returned exit code {result.returncode}")

    log_path = build_dir / f"{main_path.stem}.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else result.stdout
    log_errors, log_warnings = scan_log(log_text, args.mode)
    errors.extend(log_errors)
    warnings.extend(log_warnings)

    pdf_path = build_dir / f"{main_path.stem}.pdf"
    pages: int | None = None
    front_matter_pages: int | None = None
    body_pages: int | None = None
    page_width_points: float | None = None
    page_height_points: float | None = None
    pdf_author: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    if pdf_path.is_file():
        metadata, metadata_warning = pdf_metadata(pdf_path)
        if metadata_warning:
            target = errors if args.mode == "submission" else warnings
            target.append(metadata_warning)
        pages_value = metadata.get("pages")
        pages = int(pages_value) if isinstance(pages_value, int) else None
        width_value = metadata.get("page_width_points")
        height_value = metadata.get("page_height_points")
        page_width_points = float(width_value) if isinstance(width_value, (int, float)) else None
        page_height_points = float(height_value) if isinstance(height_value, (int, float)) else None
        author_value = metadata.get("author")
        pdf_author = str(author_value) if author_value is not None else None
        file_size_bytes = pdf_path.stat().st_size
        sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    else:
        errors.append("compiled PDF is missing")

    front_match = re.search(r"MATHAWARD:FRONT_MATTER_PAGES=(\d+)", log_text)
    if front_match:
        front_matter_pages = int(front_match.group(1))
    body_match = re.search(r"MATHAWARD:(?:CUMCM_BODY|MCM_MAIN)_PAGES=(\d+)", log_text)
    if body_match:
        body_pages = int(body_match.group(1))

    report = {
        "status": "pass" if not errors else "block",
        "mode": args.mode,
        "competition": args.competition,
        "engine": engine,
        "source": str(main_path),
        "pdf": str(pdf_path) if pdf_path.exists() else None,
        "pages": pages,
        "front_matter_pages": front_matter_pages,
        "body_pages": body_pages,
        "page_width_points": page_width_points,
        "page_height_points": page_height_points,
        "file_size_bytes": file_size_bytes,
        "pdf_author": pdf_author,
        "sha256": sha256,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
