#!/usr/bin/env python3
r"""Resolve the local TeX files reachable from a paper's main document.

This is a conservative static dependency closure, not a TeX interpreter.  It
follows literal ``\input``/``\include``/``\InputIfFileExists`` paths and never
leaves the paper directory.  Final PDF identity is still established by the
normal build and page-hash review.
"""

from __future__ import annotations

import re
from pathlib import Path


LITERAL_INPUT = re.compile(
    r"\\(?P<command>input|include|InputIfFileExists)\s*\{(?P<literal>[^{}]+)\}",
    re.IGNORECASE,
)
INPUT_START = re.compile(r"\\(?:input|include|InputIfFileExists)\b", re.IGNORECASE)
OPTIONAL_WRAPPED_INPUT = re.compile(
    r"\\IfFileExists\s*\{(?P<guard>[^{}]+)\}\s*"
    r"\{\s*(?P<input_command>\\input\s*\{(?P<input>[^{}]+)\})\s*\}\s*\{[^{}]*\}",
    re.IGNORECASE,
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        match = re.search(r"(?<!\\)%", line)
        lines.append(line[: match.start()] if match else line)
    return "\n".join(lines)


def resolve_literal(paper_root: Path, literal: str) -> tuple[Path | None, str | None]:
    value = literal.strip().replace("\\", "/")
    if not value or "#" in value or "\\" in literal:
        return None, "dynamic or empty input path"
    relative = Path(value)
    if relative.suffix == "":
        relative = relative.with_suffix(".tex")
    if relative.suffix.lower() != ".tex":
        return None, "non-TeX input path"
    resolved = (paper_root / relative).resolve()
    try:
        resolved.relative_to(paper_root)
    except ValueError:
        return None, "input path escapes paper directory"
    return resolved, None


def tex_source_closure(
    paper_root: Path, main_document: str = "main.tex"
) -> tuple[list[Path], list[str]]:
    """Return reachable TeX sources and fail-closed static-closure issues.

    LaTeX is executed with ``paper_root`` as its working directory, so literal
    inputs are resolved from that directory rather than from the including
    file. Dynamic input paths are unsupported because they can affect the PDF
    without being seen by the paper, claim, and similarity audits.
    """

    paper_root = paper_root.resolve()
    main = (paper_root / main_document).resolve()
    try:
        main.relative_to(paper_root)
    except ValueError:
        return [], [f"main document escapes paper directory: {main_document}"]
    if not main.is_file():
        return [], []

    pending = [main]
    seen: set[Path] = set()
    issues: list[str] = []
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        matches = list(LITERAL_INPUT.finditer(text))
        matched_starts = {match.start() for match in matches}
        optional_input_starts = {
            match.start("input_command")
            for match in OPTIONAL_WRAPPED_INPUT.finditer(text)
            if match.group("guard").strip() == match.group("input").strip()
        }
        relative_source = path.relative_to(paper_root).as_posix()
        for start in INPUT_START.finditer(text):
            if start.start() not in matched_starts:
                issues.append(
                    f"{relative_source}: non-literal TeX input is not auditable at character {start.start()}"
                )
        for match in matches:
            command = match.group("command")
            literal = match.group("literal").strip()
            target, resolution_issue = resolve_literal(paper_root, literal)
            if resolution_issue:
                issues.append(f"{relative_source}: {resolution_issue}: {literal}")
                continue
            if target is None or not target.is_file():
                if command.lower() == "inputiffileexists" or match.start() in optional_input_starts:
                    continue
                issues.append(
                    f"{relative_source}: required TeX input is missing: {literal}"
                )
                continue
            if target not in seen:
                pending.append(target)
    return sorted(seen), sorted(set(issues))


def loaded_tex_sources(paper_root: Path, main_document: str = "main.tex") -> list[Path]:
    sources, _ = tex_source_closure(paper_root, main_document)
    return sources


def recorded_tex_sources(paper_root: Path, recorder_path: Path) -> tuple[list[Path], list[str]]:
    """Return paper-local TeX inputs recorded by an engine ``.fls`` file."""
    paper_root = paper_root.resolve()
    try:
        lines = recorder_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], [f"cannot read LaTeX recorder file: {type(exc).__name__}"]

    sources: set[Path] = set()
    issues: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.startswith("INPUT "):
            continue
        value = line[6:].strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        if not value:
            issues.append(f"empty INPUT record at line {line_number}")
            continue
        try:
            candidate = Path(value)
            resolved = (candidate if candidate.is_absolute() else paper_root / candidate).resolve()
        except (OSError, RuntimeError, ValueError):
            issues.append(f"invalid INPUT path at line {line_number}")
            continue
        if resolved.suffix.lower() != ".tex":
            continue
        try:
            resolved.relative_to(paper_root)
        except ValueError:
            continue
        sources.add(resolved)
    return sorted(sources), sorted(set(issues))
