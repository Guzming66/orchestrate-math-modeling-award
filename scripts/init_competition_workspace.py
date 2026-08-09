#!/usr/bin/env python3
"""Create an isolated competition workspace with a direct-LaTeX paper tree."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


WORKFLOW_VERSION = 9


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


def write_csv_header_if_missing(path: Path, fields: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerow(fields)


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
    if current.get("workflow_version") != WORKFLOW_VERSION:
        raise SystemExit(
            "Existing workspace uses another workflow version; run migrate_workspace.py first."
        )
    keys = ("competition", "year", "problem", "branches", "innovation_mode")
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
            "\\IncludeAIUsageStatementfalse\n"
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
        "schema_version": WORKFLOW_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "competition": args.competition,
        "year": args.year,
        "problem": args.problem,
        "branches": branch_names,
        "innovation_mode": args.innovation_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "initialized",
        "workflow_stage": "rule_verification",
        "paper_pipeline": "direct-latex",
        "paper_source": "paper/main.tex",
        "paper_profile": profile,
        "paper_engine": engine,
        "competition_profile": "compliance/competition_profile.json",
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
        "audits/statistics",
        "audits/uncertainty",
        "audits/reproduction",
        "audits/red-team",
        "audits/latex",
        "audits/innovation",
        "audits/submission",
        "environment",
        "submission",
        "synthesis",
        "innovation",
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
        "## Strong baseline and optional alternatives\n\n"
        "| role | structural idea | key assumptions | validation | compute budget | stop condition |\n"
        "|---|---|---|---|---|---|\n"
        "| strong baseline | | | | | |\n| optional alternative | | | | | |\n\n"
        "- Why any additional route is necessary:\n"
        "- Letter-based stereotype explicitly rejected:\n",
    )
    write_text_if_missing(
        root / "innovation" / "structure_map.md",
        "# Innovation structure map\n\n"
        "- Subproblem dependency graph:\n- Mathematical objects:\n- Data-generating mechanism:\n"
        "- Conservation, network, spatial, temporal, control or game structure:\n"
        "- Identifiability and uncertainty:\n- Validation anchors:\n"
        "- Structure gaps that may justify a minimal change:\n",
    )
    write_text_if_missing(
        root / "innovation" / "baseline_failure_map.md",
        "# Baseline failure map\n\n"
        "| subproblem | strong baseline | tested assumption | observed failure | artifact | minimal repair opportunity |\n"
        "|---|---|---|---|---|---|\n",
    )
    write_text_if_missing(
        root / "innovation" / "opportunity_map.md",
        "# Innovation opportunity map\n\n"
        "Map each verified baseline failure to the smallest plausible change across formulation, representation, mechanism, decomposition, objective/constraint, inference, solution, data, validation, decision explanation, or model structure. Cross-domain analogy is optional.\n",
    )
    write_text_if_missing(
        root / "innovation" / "jury_rationale.md",
        "# Innovation claim jury rationale\n\n"
        "- Hard vetoes applied:\n- Primary paper claim:\n- Supporting claims:\n"
        "- Simpler alternatives considered:\n- Backups and rejected claims:\n",
    )
    innovation_headers = {
        "claim_portfolio.csv": [
            "claim_id", "subproblem", "scout_id", "innovation_axis", "problem_structure",
            "baseline", "baseline_failure", "failure_evidence_artifact", "failure_evidence_sha256",
            "failure_check", "failure_checked_at", "proposed_change", "change_targets_failure",
            "mathematical_expression", "why_this_change", "minimality_argument", "extra_complexity",
            "extra_complexity_justified", "nearest_precedent", "difference_from_precedent",
            "expected_effect", "falsification_test", "ablation_required", "complexity_cost",
            "paper_location", "analogy_source", "is_fusion", "component_failure_map",
            "mathematical_interface", "status", "notes",
        ],
        "novelty_audit.csv": [
            "claim_id", "search_queries", "primary_sources", "nearest_precedent", "difference",
            "evidence_locator", "novelty_class", "metadata_status", "support_status",
            "correction_retraction_status", "source_artifact", "source_sha256",
            "verification_command", "checked_at", "auditor", "decision", "notes",
        ],
        "claim_experiments.csv": [
            "claim_id", "experiment_id", "test_type", "component", "hypothesis", "baseline",
            "dataset_or_fixture", "command", "seed", "metric", "baseline_value", "changed_value",
            "artifact_path", "sha256", "checked_at", "status", "reviewer", "decision", "notes",
        ],
        "critic_findings.csv": [
            "finding_id", "claim_id", "attack_surface", "severity", "finding",
            "repair_or_falsifier", "status", "artifact_path", "sha256", "command_or_check",
            "checked_at", "reviewer", "notes",
        ],
        "selection.csv": [
            "claim_id", "decision", "paper_role", "problem_fit", "evidence_strength", "necessity",
            "novelty", "robustness", "parsimony", "communication", "risks", "artifact_path",
            "sha256", "command_or_check", "checked_at", "reviewer", "notes",
        ],
    }
    for filename, fields in innovation_headers.items():
        write_csv_header_if_missing(root / "innovation" / filename, fields)
    competition_profile: dict[str, object] = {
        "schema_version": 2,
        "profile_id": f"{args.competition}-{args.year}-unverified",
        "competition": args.competition,
        "edition": str(args.year),
        "status": "unverified",
        "effective_from": "",
        "effective_to": None,
        "verified_at": "",
        "verified_by": None,
        "sources": [],
        "build": {
            "latex_engine": engine,
            "main_document": "main.tex",
        },
        "requirements": {
            "paper": {
                "format": None,
                "max_front_matter_pages": None,
                "max_total_pages": None,
                "max_body_pages": None,
                "max_pdf_bytes": None,
                "page_size": None,
                "table_of_contents_allowed": None,
                "anonymous": None,
            },
            "submission": {
                "support_archive_required": None,
                "support_archive_max_bytes": None,
            },
            "ai": {
                "policy_checked": False,
                "usage_statement_required": None,
                "details_pdf_required": None,
                "statement_source": None,
                "statement_enable_marker": None,
                "statement_position": None,
                "inline_disclosure_required": None,
                "tool_reference_required": None,
                "human_verification_required": None,
                "details_source": None,
                "details_filename": None,
            },
            "artifacts": [],
        },
        "rule_bindings": [],
        "notes": "Populate only from current official source snapshots. Bind every executable requirement to an exact source locator; do not infer rules from year.",
    }
    write_json_if_missing(root / "compliance" / "competition_profile.json", competition_profile)

    write_json_if_missing(
        root / "synthesis" / "model_selection.json",
        {
            "schema_version": 1,
            "status": "draft",
            "questions": [],
            "notes": "Record one decision per core question. A strong baseline may remain selected when alternatives add no validated value.",
        },
    )
    write_json_if_missing(
        root / "audits" / "review_findings.json",
        {
            "schema_version": 1,
            "status": "not_reviewed",
            "policy": {"max_open_major": 0 if args.innovation_mode == "championship" else 1},
            "coverage": [
                {"review_type": review_type, "status": "pending", "rationale": ""}
                for review_type in ("scientific", "statistical", "claims")
            ],
            "findings": [],
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
                    "verification_command",
                    "artifact_path",
                    "artifact_sha256",
                    "checked_at",
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
                    "verification_command",
                    "checked_at",
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

    write_csv_header_if_missing(
        root / "synthesis" / "innovation_claims.csv",
        [
            "claim_id", "claim_sentence", "problem_structure", "baseline_failure", "method_change",
            "evidence_result_ids", "novelty_source_keys", "paper_section", "paper_anchor",
            "figure_or_table", "claim_strength", "status", "artifact_path", "sha256",
            "command_or_check", "checked_at", "reviewer", "notes",
        ],
    )
    write_csv_header_if_missing(
        root / "compliance" / "ai_usage_ledger.csv",
        [
            "use_id", "tool", "version", "purpose", "paper_section", "paper_anchor",
            "citation_key", "human_changes", "verification_status", "artifact_path",
            "sha256", "command_or_check", "checked_at", "reviewer", "notes",
        ],
    )

    task_board_path = root / "shared" / "task_board.csv"
    if not task_board_path.exists():
        model_task_ids = [f"model-{chr(97 + index)}" for index in range(args.branches)]
        task_rows = [
            ["profile-audit", "all", "rules", "", "", "compliance/competition_profile.json", "", "", "stop until an official source-backed profile is verified", "pending", "true", "versioned profile and source snapshots", ""],
            ["problem-route", "all", "routing", "", "", "shared/problem_route.md", "", "", "unverified exploratory structure only until profile passes", "pending", "true", "frozen problem route", ""],
            ["strong-baseline", "all", "baseline", "problem-route", "", "innovation/baseline_failure_map.md", "", "", "simplest defensible baseline", "pending", "true", "baseline definition and assumption tests", ""],
            ["baseline-failure", "all", "diagnostic", "strong-baseline", "", "innovation/baseline_failure_map.md", "", "", "report no innovation if no material failure exists", "pending", "true", "artifact-backed failure map", ""],
            ["innovation-discovery", "all", "innovation", "baseline-failure", "", "innovation/claim_portfolio.csv", "", "", "minimal repair or no claim", "pending", "true", "innovation claim portfolio and opportunity map", ""],
            ["innovation-evidence", "all", "experiment", "innovation-discovery;profile-audit", "", "innovation/claim_experiments.csv", "", "", "do not promote while rules are unverified", "pending", "true", "nearest-precedent, falsification and ablation evidence", ""],
            ["innovation-critic", "all", "red-team", "innovation-evidence", "", "innovation/critic_findings.csv", "", "", "reject unsupported complexity", "pending", "true", "blind critic findings", ""],
            ["innovation-selection", "all", "jury", "innovation-critic", "", "innovation/selection.csv", "", "", "promote one evidence-backed primary claim", "pending", "true", "claim decisions and jury rationale", ""],
        ]
        for task_id in model_task_ids:
            task_rows.append(
                [task_id, "assigned", "model", "innovation-selection", "", f"branches/{task_id}", "", "", "baseline branch", "pending", "true", "model, code, results and branch summary", ""]
            )
        joined_models = ";".join(model_task_ids)
        task_rows.extend(
            [
                ["model-freeze", "all", "selection", joined_models, "", "synthesis/model_selection.json", "", "", "select the best validated solution, including the baseline when warranted", "pending", "true", "question-level model decisions and rejection reasons", ""],
                ["reproduction", "all", "reproduction", "model-freeze", "", "audits/reproduction", "", "", "rerun selected solution", "pending", "true", "clean-run report", ""],
                ["paper", "all", "writing", "model-freeze", "", "paper", "", "", "minimal complete paper", "pending", "true", "direct-LaTeX paper", ""],
                ["citation-audit", "all", "citations", "paper", "", "audits/citations", "", "", "remove or weaken unsupported claims", "pending", "true", "verified citation ledger", ""],
                ["scientific-review", "all", "review", "paper;citation-audit;reproduction", "", "audits/review_findings.json", "", "", "weaken claims or repair model", "pending", "true", "scientific, statistical and claim review", ""],
                ["submission", "all", "submission", "scientific-review", "", "submission", "", "", "submit only verified artifacts", "pending", "true", "paper PDF and profile-required artifacts", ""],
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
            root / "compliance" / "submission_checklist.md",
            "# CUMCM submission checklist\n\n"
            "- [ ] Versioned competition_profile.json is verified against current official source snapshots and hashes\n"
            "- [ ] Paper format, front matter, paper size, margins, contents, page limits and file-size limits match the verified profile\n"
            "- [ ] PDF, filenames, folders, metadata, code, figures and data satisfy the profile's anonymity requirements\n"
            "- [ ] Appendix and support archive satisfy only the current profile's explicit requirements\n"
            "- [ ] Any support archive contains the same code version, external data and necessary intermediate results\n"
            "- [ ] Every core number reproduces from a clean run and matches abstract/body/tables\n"
            "- [ ] Every input file is covered by data_provenance.csv and every core result by result_manifest.csv\n"
            "- [ ] Every cited work exists and its identifier, title, authors, year and venue match authoritative records\n"
            "- [ ] Every core external claim has an exact evidence locator and the source supports the wording\n"
            "- [ ] Published versions and correction/retraction status have been checked\n"
            "- [ ] Actual AI use is truthfully disclosed exactly where and how the verified profile requires\n"
            "- [ ] Any profile-required AI details artifact covers tool/version, purpose, process, adoption, modification and verification\n"
            "- [ ] Any profile-required AI details artifact appears in the required submission location\n"
            "- [ ] Any additional material explicitly required by current rules is present\n"
            "- [ ] Task dependencies are closed and every blocking task has an owner, evidence and fallback\n"
            "- [ ] Support archive was built from support_manifest.json and passed identity/secret scanning\n"
            "- [ ] Independent scientific, statistical and claim review is closed\n"
            "- [ ] Submission build passes and every rendered PDF page has been visually inspected\n"
            "- [ ] Uploaded files match frozen hashes\n",
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
    parser.add_argument("--branches", type=int, default=1, choices=range(1, 9))
    parser.add_argument("--innovation-mode", choices=("standard", "championship"), default="standard")
    return parser.parse_args()


if __name__ == "__main__":
    workspace = create_workspace(parse_args())
    print(f"Initialized competition workspace: {workspace}")
