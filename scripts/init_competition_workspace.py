#!/usr/bin/env python3
"""Create an isolated competition workspace with a direct-LaTeX paper tree."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


WORKFLOW_VERSION = 6


def write_text_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def write_json_if_missing(path: Path, value: object) -> None:
    if not path.exists():
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def copy_tree_without_overwrite(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise SystemExit(f"LaTeX template directory is missing: {source}")
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def check_existing_manifest(path: Path, expected: dict[str, object]) -> None:
    if not path.exists():
        return
    current = json.loads(path.read_text(encoding="utf-8"))
    keys = ("competition", "year", "problem", "branches")
    conflicts = [key for key in keys if current.get(key) != expected.get(key)]
    if conflicts:
        joined = ", ".join(conflicts)
        raise SystemExit(
            f"Existing manifest conflicts on {joined}; choose another workspace."
        )


def paper_profile(competition: str) -> tuple[str, str]:
    if competition == "CUMCM":
        return "cumcm", "xelatex"
    return "mcm", "pdflatex"


def paper_sections(competition: str) -> dict[str, str]:
    if competition == "CUMCM":
        return {
            "00_abstract.tex": "本文为可直接编译的草稿。DRAFT CONTENT\n",
            "01_problem_restatement.tex": "\\section{问题重述}\nDRAFT CONTENT\n",
            "02_problem_analysis.tex": "\\section{问题分析}\nDRAFT CONTENT\n",
            "03_assumptions.tex": "\\section{模型假设}\nDRAFT CONTENT\n",
            "04_notation.tex": "\\section{符号说明}\nDRAFT CONTENT\n",
            "05_models.tex": "\\section{模型建立与求解}\nDRAFT CONTENT\n",
            "06_robustness.tex": "\\section{敏感性与稳健性分析}\nDRAFT CONTENT\n",
            "07_evaluation.tex": "\\section{模型评价与推广}\nDRAFT CONTENT\n",
            "08_conclusion.tex": "\\section{结论}\nDRAFT CONTENT\n",
            "09_ai_statement.tex": (
                "\\section*{AI工具使用声明}\n"
                "本参赛队在竞赛过程中使用了AI工具，主要用于【DRAFT CONTENT】，详细使用情况见支撑材料。\n"
            ),
            "90_appendix.tex": (
                "\\section{支撑材料文件清单}\n"
                "DRAFT CONTENT\n\n"
                "\\section{完整源程序}\n"
                "% Use \\lstinputlisting to include every runnable source file.\n"
                "DRAFT CONTENT\n"
            ),
        }
    return {
        "00_summary.tex": "This is a directly compiled draft summary. DRAFT CONTENT\n",
        "01_problem_restatement.tex": "\\section{Problem Restatement}\nDRAFT CONTENT\n",
        "02_problem_analysis.tex": "\\section{Problem Analysis}\nDRAFT CONTENT\n",
        "03_assumptions.tex": "\\section{Assumptions}\nDRAFT CONTENT\n",
        "04_notation.tex": "\\section{Notation}\nDRAFT CONTENT\n",
        "05_models.tex": "\\section{Models and Results}\nDRAFT CONTENT\n",
        "06_robustness.tex": "\\section{Sensitivity and Robustness}\nDRAFT CONTENT\n",
        "07_evaluation.tex": "\\section{Evaluation and Extensions}\nDRAFT CONTENT\n",
        "08_conclusion.tex": "\\section{Conclusions}\nDRAFT CONTENT\n",
        "09_required_deliverable.tex": "% Add a required memo or letter here when applicable.\n",
        "90_appendix.tex": "\\section{Supporting Materials}\nDRAFT CONTENT\n",
        "99_ai_report.tex": "DRAFT CONTENT\n",
    }


def initialize_paper(root: Path, competition: str, problem: str) -> None:
    profile, _ = paper_profile(competition)
    skill_root = Path(__file__).resolve().parents[1]
    copy_tree_without_overwrite(
        skill_root / "assets" / "latex" / profile,
        root / "paper",
    )

    for relative in ("paper/sections", "paper/generated", "paper/figures", "paper/build"):
        (root / relative).mkdir(parents=True, exist_ok=True)

    for filename, content in paper_sections(competition).items():
        write_text_if_missing(root / "paper" / "sections" / filename, content)

    escaped_problem = latex_escape(problem)
    if competition == "CUMCM":
        metadata = (
            "\\renewcommand{\\PaperTitle}{DRAFT TITLE}\n"
            "\\renewcommand{\\PaperKeywords}{DRAFT KEYWORDS}\n"
            "\\IncludeAIUsageStatementtrue\n"
        )
    else:
        metadata = (
            "\\renewcommand{\\PaperTitle}{DRAFT TITLE}\n"
            "\\renewcommand{\\PaperKeywords}{DRAFT KEYWORDS}\n"
            f"\\renewcommand{{\\ProblemCode}}{{{escaped_problem}}}\n"
            "\\renewcommand{\\ControlNumber}{0000000}\n"
            "\\IncludeAIReporttrue\n"
        )
    write_text_if_missing(root / "paper" / "generated" / "metadata.tex", metadata)
    if competition == "CUMCM":
        write_text_if_missing(
            root / "paper" / "generated" / "ai_usage_entries.tex",
            "% Record tool name/version, purpose/stage, prompting/use process, and adoption/manual verification.\n"
            "DRAFT CONTENT\n",
        )
    write_text_if_missing(
        root / "paper" / "references.bib",
        "% Add only verified BibTeX records.\n",
    )


def create_workspace(args: argparse.Namespace) -> Path:
    root = Path(args.workspace).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    branch_names = [f"model-{chr(97 + index)}" for index in range(args.branches)]
    profile, engine = paper_profile(args.competition)
    manifest = {
        "workflow_version": WORKFLOW_VERSION,
        "competition": args.competition,
        "year": args.year,
        "problem": args.problem,
        "branches": branch_names,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "initialized",
        "paper_pipeline": "direct-latex",
        "paper_source": "paper/main.tex",
        "paper_profile": profile,
        "paper_engine": engine,
    }
    manifest_path = root / "competition_manifest.json"
    check_existing_manifest(manifest_path, manifest)

    base_dirs = [
        "inputs/original",
        "inputs/external",
        "shared",
        "audits/data",
        "audits/citations",
        "audits/rules",
        "audits/benchmark",
        "audits/statistics",
        "audits/uncertainty",
        "audits/reproduction",
        "audits/red-team",
        "audits/latex",
        "audits/submission",
        "environment",
        "submission",
        "synthesis",
        "paper",
        "compliance",
        "logs",
    ]
    for relative in base_dirs:
        (root / relative).mkdir(parents=True, exist_ok=True)

    for branch in branch_names:
        for relative in ("notes", "code", "results", "figures"):
            (root / "branches" / branch / relative).mkdir(parents=True, exist_ok=True)
        write_json_if_missing(
            root / "branches" / branch / "branch_manifest.json",
            {
                "branch": branch,
                "status": "not_started",
                "may_read": ["inputs/original", "inputs/external", "shared"],
                "may_write": [f"branches/{branch}"],
                "blind_until": "branch_freeze",
            },
        )

    write_json_if_missing(manifest_path, manifest)
    write_text_if_missing(root / "logs" / "decision_log.jsonl", "")
    write_text_if_missing(root / "compliance" / "ai_usage.jsonl", "")
    write_text_if_missing(
        root / "shared" / "problem_contract.md",
        "# Problem contract\n\n"
        "- Competition:\n- Year:\n- Problem:\n- Deadline:\n"
        "- Required questions:\n- Objectives:\n- Constraints:\n"
        "- Data dictionary:\n- Evaluation criteria:\n- Deliverables:\n",
    )
    write_text_if_missing(
        root / "shared" / "problem_route.md",
        "# Problem route\n\n"
        "- Problem version/hash:\n- Mathematical objects:\n- Task verbs:\n"
        "- Input modality and scale:\n- Constraint structure:\n"
        "- Data-generating mechanism:\n- Validation anchors:\n"
        "- Main uncertainty and failure risks:\n\n"
        "## Heterogeneous routes\n\n"
        "| route | structural idea | key assumptions | baseline | validation | compute budget | stop condition |\n"
        "|---|---|---|---|---|---|---|\n"
        "| A | | | | | | |\n| B | | | | | | |\n| C | | | | | | |\n\n"
        "- Why these routes are structurally different:\n"
        "- Letter-based stereotype explicitly rejected:\n",
    )
    official_sources: dict[str, object] = {
        "competition": args.competition,
        "status": "must_reverify_at_stage_0_8_9",
        "last_checked_at": None,
        "verified_by": None,
        "sources": [],
    }
    if args.competition == "CUMCM":
        official_sources["candidate_sources"] = [
            {
                "kind": "participation_rules",
                "url": "https://www.mcm.edu.cn/html_cn/node/9d8e511fe7a1447b35f53a82c908e2e0.html",
                "known_version": "2026 revision",
            },
            {
                "kind": "paper_format",
                "url": "https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html",
                "known_version": "2026 revision",
            },
            {
                "kind": "past_problems",
                "url": "https://www.mcm.edu.cn/html_cn/block/8579f5fce999cdc896f78bca5d4f8237.html",
                "known_version": "archive through 2025",
            },
            {
                "kind": "displayed_papers",
                "url": "https://dxs.moe.gov.cn/zx/hd/sxjm/sxjmlw/qkt_sxjm_lw_lwzs.shtml",
                "known_version": "gallery through 2025",
            },
        ]
    write_json_if_missing(root / "compliance" / "official_sources.json", official_sources)

    write_json_if_missing(
        root / "audits" / "gate_status.json",
        {
            "status": "not_reviewed",
            "gates": {
                f"G{index}": {
                    "status": "pending",
                    "reviewer": "",
                    "checked_at": "",
                    "evidence": [],
                    "blocking_findings": [],
                }
                for index in range(8)
            },
        },
    )
    write_json_if_missing(
        root / "audits" / "reproduction" / "reproduction_status.json",
        {
            "status": "pending",
            "reviewer": "",
            "checked_at": "",
            "clean_run_command": "",
            "core_results_reproduced": False,
            "evidence": [],
            "blocking_findings": [],
        },
    )
    write_json_if_missing(
        root / "submission" / "support_manifest.json",
        {
            "archive_name": "support_materials.zip",
            "files": [],
        },
    )
    write_text_if_missing(
        root / "compliance" / "anonymity_terms.txt",
        "# Add one forbidden identity string per line before packaging.\n"
        "# Include member names, school names, region names, usernames and team aliases.\n",
    )

    citation_ledger_path = root / "audits" / "citations" / "citation_ledger.csv"
    if not citation_ledger_path.exists():
        with citation_ledger_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "claim_id",
                    "claim_location",
                    "claim_text",
                    "citation_key",
                    "source_class",
                    "primary_source",
                    "identifier",
                    "canonical_url",
                    "metadata_sources",
                    "metadata_status",
                    "evidence_locator",
                    "support_status",
                    "correction_retraction_status",
                    "accessed_at",
                    "auditor",
                    "severity",
                    "notes",
                ]
            )
    write_text_if_missing(
        root / "audits" / "citations" / "citation_audit.md",
        "# Citation authenticity audit\n\n"
        "- Metadata report: `metadata_report.json`\n"
        "- Claim ledger: `citation_ledger.csv`\n"
        "- Blocking findings:\n"
        "- Major findings:\n"
        "- Exceptions and rationale:\n"
        "- Final status: not_reviewed\n",
    )

    data_ledger_path = root / "audits" / "data" / "data_provenance.csv"
    if not data_ledger_path.exists():
        with data_ledger_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "data_id",
                    "relative_path",
                    "source_type",
                    "source_url",
                    "license_or_terms",
                    "acquired_at",
                    "original_sha256",
                    "current_sha256",
                    "transform_script",
                    "fields_used",
                    "status",
                    "reviewer",
                    "notes",
                ]
            )

    result_manifest_path = root / "synthesis" / "result_manifest.csv"
    if not result_manifest_path.exists():
        with result_manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "result_id",
                    "claim_location",
                    "value",
                    "unit",
                    "relative_path",
                    "generator",
                    "command",
                    "input_ids",
                    "seed",
                    "environment_file",
                    "sha256",
                    "status",
                    "reviewer",
                    "notes",
                ]
            )

    task_board_path = root / "shared" / "task_board.csv"
    if not task_board_path.exists():
        model_task_ids = [f"model-{chr(97 + index)}" for index in range(args.branches)]
        task_rows = [
            ["rule-audit", "all", "rules", "", "", "audits/rules", "", "", "manual official-rule review", "pending", "true", "verified rule snapshot", ""],
            ["problem-route", "all", "routing", "rule-audit", "", "shared/problem_route.md", "", "", "two routes plus a strong baseline", "pending", "true", "frozen problem route", ""],
        ]
        for task_id in model_task_ids:
            task_rows.append(
                [task_id, "assigned", "model", "problem-route", "", f"branches/{task_id}", "", "", "baseline branch", "pending", "true", "model, code, results and branch summary", ""]
            )
        joined_models = ";".join(model_task_ids)
        task_rows.extend(
            [
                ["synthesis", "all", "synthesis", joined_models, "", "synthesis", "", "", "select strongest reproducible baseline", "pending", "true", "evidence matrix and selected route", ""],
                ["reproduction", "all", "reproduction", "synthesis", "", "audits/reproduction", "", "", "rerun selected baseline", "pending", "true", "clean-run report", ""],
                ["paper", "all", "writing", "synthesis", "", "paper", "", "", "minimal complete paper", "pending", "true", "direct-LaTeX paper", ""],
                ["citation-audit", "all", "citations", "paper", "", "audits/citations", "", "", "remove or weaken unsupported claims", "pending", "true", "verified citation ledger", ""],
                ["submission", "all", "submission", "paper;citation-audit;reproduction", "", "submission", "", "", "submit reproducible baseline package", "pending", "true", "paper PDF and support archive", ""],
            ]
        )
        with task_board_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "task_id",
                    "subproblem",
                    "task_type",
                    "depends_on",
                    "owner",
                    "assigned_path",
                    "due_at",
                    "freeze_at",
                    "fallback",
                    "status",
                    "blocking",
                    "deliverables",
                    "evidence",
                ]
            )
            writer.writerows(task_rows)

    if args.competition == "CUMCM":
        write_text_if_missing(
            root / "audits" / "benchmark" / "excellent_paper_review.md",
            "# Displayed-paper benchmark review\n\n"
            "Use a de-problematized structure card.\n\n"
            "| source/year/problem | task family | abstract evidence map | problem dependency | baseline/validation | figure duties | transferable structure | problem-specific content not to copy |\n"
            "|---|---|---|---|---|---|---|---|\n",
        )
        write_text_if_missing(
            root / "compliance" / "submission_checklist.md",
            "# CUMCM submission checklist\n\n"
            "- [ ] Current official rules, format, participation notice and regional additions reverified\n"
            "- [ ] Electronic paper begins with a one-page abstract; no commitment page, numbering page or contents\n"
            "- [ ] A4, margins >= 2.5 cm, body <= 30 pages, appendix begins after body\n"
            "- [ ] PDF <= 20 MB; ZIP/RAR <= 20 MB; files submitted separately\n"
            "- [ ] PDF, filenames, folders, metadata, code, figures and data contain no identity\n"
            "- [ ] Appendix lists support files and includes all complete runnable source programs\n"
            "- [ ] Support archive contains the same code version, external data and necessary intermediate results\n"
            "- [ ] Every core number reproduces from a clean run and matches abstract/body/tables\n"
            "- [ ] Every input file is covered by data_provenance.csv and every core result by result_manifest.csv\n"
            "- [ ] Every cited work exists and its identifier, title, authors, year and venue match authoritative records\n"
            "- [ ] Every core external claim has an exact evidence locator and the source supports the wording\n"
            "- [ ] Published versions and correction/retraction status have been checked\n"
            "- [ ] AI usage statement is before references and truthfully declares use of this Skill/Codex\n"
            "- [ ] AI工具使用详情.pdf covers tool/version, purpose, process, adoption, modification and verification\n"
            "- [ ] AI工具使用详情.pdf is listed in support_manifest.json and included in the support archive\n"
            "- [ ] Any additional material explicitly required by current rules is present\n"
            "- [ ] Task dependencies are closed and every blocking task has an owner, evidence and fallback\n"
            "- [ ] Support archive was built from support_manifest.json and passed identity/secret scanning\n"
            "- [ ] G0-G7 are marked pass with reviewer, timestamp and evidence\n"
            "- [ ] Submission build passes and every rendered PDF page has been visually inspected\n"
            "- [ ] Uploaded files match frozen hashes\n",
        )

    matrix_path = root / "synthesis" / "evidence_matrix.csv"
    if not matrix_path.exists():
        with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "branch",
                    "problem_fit",
                    "assumption_risk",
                    "data_support",
                    "baseline_gain",
                    "diagnostic_quality",
                    "uncertainty_stability",
                    "reproducibility",
                    "interpretability",
                    "implementation_risk",
                    "paper_communicability",
                    "rule_compliance",
                    "blocking_findings",
                    "decision",
                    "decision_evidence",
                ]
            )

    initialize_paper(root, args.competition, args.problem)
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize an isolated modeling workspace with direct LaTeX."
    )
    parser.add_argument("workspace", help="Target workspace directory")
    parser.add_argument(
        "--competition",
        required=True,
        choices=("CUMCM", "MCM", "ICM"),
    )
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--branches", type=int, default=3, choices=range(2, 9))
    return parser.parse_args()


if __name__ == "__main__":
    workspace = create_workspace(parse_args())
    print(f"Initialized competition workspace: {workspace}")
