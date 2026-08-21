from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from finalize_submission import check_ai_compliance, check_data_provenance, finalize
from build_latex import (
    audit_question_standalone,
    classify_artifact,
    latex_environment,
    parse_page_fill,
    parse_page_layout_metrics,
    scan_sources,
)
from migrate_workspace import migrate
from package_submission import package_workspace
from score_claim_benchmark import score
from validate_competition_profile import validate_competition_profile
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_model_selection import validate_model_selection
from validate_paper_innovation import validate_paper_innovation
from validate_paper_presentation import validate_paper_presentation
from validate_paper_question_coverage import validate_paper_question_coverage
from validate_paper_integrity import validate_paper_integrity
from validate_pdf_visual_review import resolve_pdftoppm, validate_review_records
from validate_problem_contract import validate_problem_contract
from validate_question_interfaces import result_fingerprint, validate_question_interfaces
from validate_review_findings import validate_review_findings
from validate_review_route import validate_review_route
from validate_similarity_precheck import validate_similarity_precheck
from validate_task_board import validate_task_board
from audit_cumcm_corpus_style import build_cards, summarize
from run_reproduction import run_reproduction, validate_contract
from snapshot_environment import required_tools
from preflight import declared_cli_flags


STAMP = "2026-08-08T00:00:00+00:00"


class WorkflowTests(unittest.TestCase):
    def initialize(self, root: Path, competition: str = "CUMCM", mode: str = "standard") -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "init_competition_workspace.py"),
                str(root),
                "--competition",
                competition,
                "--year",
                "2026",
                "--problem",
                "A",
                "--branches",
                "1",
                "--innovation-mode",
                mode,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def write_csv_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            fieldnames = csv.DictReader(handle).fieldnames
        self.assertIsNotNone(fieldnames)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def load_paper_sections(self, root: Path, *relative_sections: str) -> None:
        loader = root / "paper" / "generated" / "question_sections.tex"
        loader.write_text(
            "\n".join(f"\\input{{{relative}}}" for relative in relative_sections) + "\n",
            encoding="utf-8",
        )

    def make_artifact(self, root: Path, relative: str, text: str = "verified evidence\n") -> dict[str, str]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return {
            "artifact_path": relative.replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "command_or_check": "manual fixture verification",
            "checked_at": STAMP,
        }

    def test_submission_source_audit_keeps_internal_artifacts_out_of_paper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper = Path(temporary)
            sections = paper / "sections"
            sections.mkdir()
            (sections / "00_abstract.tex").write_text(
                "结果良好，详见\\cite{demo}。\\[x=1\\]\n",
                encoding="utf-8",
            )
            (sections / "03_question.tex").write_text(
                "\\section{符号说明}\n"
                "证据见 audits/results.json，artifact_path 与 sha256 已记录。\n"
                "该方法具有较强的鲁棒性。\\begin{lstlisting}x = 1\\end{lstlisting}\n",
                encoding="utf-8",
            )
            errors, warnings = scan_sources(paper, "submission")
            self.assertTrue(any("artifact_path" in item for item in errors))
            self.assertTrue(any("audits path" in item for item in errors))
            self.assertTrue(any("vague result quality" in item for item in warnings))
            self.assertTrue(any("contains a citation" in item for item in warnings))
            self.assertTrue(any("displayed mathematics" in item for item in warnings))
            self.assertTrue(any("standalone notation section" in item for item in warnings))
            self.assertTrue(any("tested boundary" in item for item in warnings))
            self.assertTrue(any("full code listing" in item for item in warnings))

    def test_draft_source_audit_marks_placeholders_as_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper = Path(temporary)
            sections = paper / "sections"
            sections.mkdir()
            (sections / "q01.tex").write_text("\\section{问题一}\n待补充验证表。\n", encoding="utf-8")
            errors, warnings = scan_sources(paper, "draft")
            self.assertEqual(errors, [])
            self.assertTrue(any("review-only" in item for item in warnings))
            errors, _ = scan_sources(paper, "submission")
            self.assertTrue(any("placeholder" in item for item in errors))

    def test_submission_source_audit_rejects_dynamic_and_missing_required_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper = Path(temporary)
            (paper / "main.tex").write_text(
                "\\def\\questionfile{sections/q01.tex}\n"
                "\\input{\\questionfile}\n"
                "\\input{sections/missing.tex}\n"
                "\\InputIfFileExists{sections/optional.tex}{}{}\n"
                "\\IfFileExists{sections/guarded.tex}{\\input{sections/guarded.tex}}{}\n",
                encoding="utf-8",
            )
            errors, warnings = scan_sources(paper, "main.tex", "submission")
            self.assertEqual(warnings, [])
            self.assertTrue(any("dynamic" in item and "questionfile" in item for item in errors))
            self.assertTrue(any("sections/missing.tex" in item for item in errors))
            self.assertFalse(any("sections/optional.tex" in item for item in errors))
            self.assertFalse(any("sections/guarded.tex" in item for item in errors))

    def test_standalone_question_uses_strict_handoff_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper = Path(temporary)
            section = paper / "sections" / "questions" / "q01.tex"
            section.parent.mkdir(parents=True)
            main = paper / "q01_standalone.tex"
            main.write_text("\\input{sections/questions/q01.tex}\n", encoding="utf-8")
            section.write_text(
                "\\section{问题一}\n"
                "\\subsection{任务与判定}\n根据给定轨迹计算满足遮蔽判据的持续时间。\n"
                "\\subsection{模型与求解}\n在统一坐标系中建立距离函数并搜索判据边界。\n"
                "\\subsection{结果}\n计算得到有效遮蔽持续时间 $T=1.4$ s。\n"
                "\\subsection{数值验证与边界}\n网格加密、步长缩小与独立复算结果一致。\n",
                encoding="utf-8",
            )
            audit, errors, warnings = audit_question_standalone(paper, main, "submission")
            self.assertEqual(warnings, [])
            self.assertTrue(any("paper-visible LaTeX label" in item for item in errors))
            self.assertTrue(any("judge-visible table or figure" in item for item in errors))
            self.assertEqual(audit["duties"], {"task": True, "model": True, "result": True, "validation": True})
            self.assertEqual(audit["duty_content"], {"task": True, "model": True, "result": True, "validation": True})
            self.assertEqual(classify_artifact(main), "question_standalone")

            section.write_text(
                section.read_text(encoding="utf-8").replace(
                    "\\subsection{数值验证与边界}",
                    "\\subsection{数值验证与边界}\\label{sec:q1-validation}\n"
                    "\\begin{table}\\caption{加密结果}\\begin{tabular}{cc}网格&时长\\\\45&1.4\\end{tabular}\\end{table}",
                ),
                encoding="utf-8",
            )
            _, errors, warnings = audit_question_standalone(paper, main, "submission")
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_page_fill_parser_detects_sparse_final_page(self) -> None:
        bbox = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>'
            '<page height="800"><word yMin="700" yMax="720">full</word></page>'
            '<page height="800"><word yMin="300" yMax="320">sparse</word></page>'
            '</doc></body></html>'
        )
        self.assertEqual(parse_page_fill(bbox), [0.9, 0.4])

    def test_page_layout_parser_excludes_lone_numeric_footer(self) -> None:
        bbox = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>'
            '<page height="800">'
            '<line yMin="100"><word yMin="100" yMax="500">正文</word></line>'
            '<line yMin="760"><word yMin="760" yMax="775">12</word></line>'
            '</page></doc></body></html>'
        )
        metrics = parse_page_layout_metrics(bbox)
        self.assertEqual(metrics[0]["content_bottom_ratio"], 0.625)
        self.assertEqual(metrics[0]["bottom_blank_ratio"], 0.375)
        self.assertEqual(metrics[0]["word_count"], 1)
        self.assertEqual(metrics[0]["excluded_footer_word_count"], 1)

    def test_latex_build_uses_reproducible_timestamp_environment(self) -> None:
        environment = latex_environment(Path("paper"))
        self.assertEqual(environment["SOURCE_DATE_EPOCH"], "946684800")
        self.assertEqual(environment["FORCE_SOURCE_DATE"], "1")

    def test_environment_snapshot_requires_only_the_selected_build_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            tools = required_tools(root)
            self.assertIn("xelatex", tools)
            self.assertNotIn("pdflatex", tools)
            self.assertNotIn("latexmk", tools)
            self.assertNotIn("bibtex", tools)
            (root / "paper" / "references.bib").write_text(
                "@article{demo, title={Verified}}\n", encoding="utf-8"
            )
            self.assertIn("bibtex", required_tools(root))

    def test_preflight_reads_companion_cli_without_importing_its_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "validator.py"
            script.write_text(
                "import dependency_that_is_not_installed\n"
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--check-dois', action='store_true')\n"
                "p.add_argument('--report')\n",
                encoding="utf-8",
            )
            flags, error = declared_cli_flags(script)
            self.assertIsNone(error)
            self.assertEqual(flags, {"--check-dois", "--report"})

    def test_cumcm_initializer_uses_lean_question_level_latex_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.initialize(root)
            main = (root / "paper" / "main.tex").read_text(encoding="utf-8")
            self.assertIn("generated/question_sections.tex", main)
            self.assertNotIn("01_problem_restatement.tex", main)
            self.assertTrue((root / "paper" / "sections" / "questions").is_dir())
            self.assertTrue((root / "paper" / "sections" / "01_task_analysis.tex").is_file())
            appendix = (root / "paper" / "sections" / "90_appendix.tex").read_text(encoding="utf-8")
            self.assertNotIn("DRAFT CONTENT", appendix)

    def test_cumcm_question_coverage_matches_frozen_problem_questions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.initialize(root)
            selection = {
                "schema_version": 1,
                "status": "frozen",
                "questions": [{"question_id": "Q1"}, {"question_id": "Q2"}],
            }
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps(selection, ensure_ascii=False), encoding="utf-8"
            )
            (root / "shared" / "problem_contract.json").write_text(
                json.dumps({"schema_version": 1, "status": "frozen", "questions": [{"question_id": "Q1"}, {"question_id": "Q2"}]}),
                encoding="utf-8",
            )
            question_dir = root / "paper" / "sections" / "questions"
            (question_dir / "q01.tex").write_text("\\section{问题一}\n直接答案。\n", encoding="utf-8")
            (root / "paper" / "generated" / "question_sections.tex").write_text(
                "\\input{sections/questions/q01.tex}\n", encoding="utf-8"
            )
            report = validate_paper_question_coverage(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("freezes 2" in item for item in report["errors"]))

            (question_dir / "q02.tex").write_text("\\section{问题二}\n直接答案。\n", encoding="utf-8")
            (root / "paper" / "generated" / "question_sections.tex").write_text(
                "\\input{sections/questions/q01.tex}\n\\input{sections/questions/q02.tex}\n",
                encoding="utf-8",
            )
            report = validate_paper_question_coverage(root)
            self.assertEqual(report["status"], "pass")

            (root / "paper" / "generated" / "question_sections.tex").write_text(
                "\\input{sections/questions/q02.tex}\n\\input{sections/questions/q01.tex}\n",
                encoding="utf-8",
            )
            report = validate_paper_question_coverage(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("Q1 must load" in item for item in report["errors"]))
            (root / "paper" / "generated" / "question_sections.tex").write_text(
                "\\input{sections/questions/q01.tex}\n\\input{sections/questions/q02.tex}\n",
                encoding="utf-8",
            )

            (question_dir / "q02.tex").write_text("\\section{问题二}\n", encoding="utf-8")
            report = validate_paper_question_coverage(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("empty or still a draft" in item for item in report["errors"]))

    def complete_profile(self, root: Path, competition: str = "CUMCM") -> None:
        source = self.make_artifact(root, "audits/rules/official-rules.html")
        profile = {
            "schema_version": 2,
            "profile_id": f"{competition}-2026-fixture-v2",
            "competition": competition,
            "edition": "2026",
            "status": "verified",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "verified_at": STAMP,
            "verified_by": "independent-rule-auditor",
            "sources": [
                {
                    "source_id": "official-rules",
                    "kind": "official rules",
                    "url": "https://example.invalid/official-rules",
                    **source,
                }
            ],
            "build": {
                "latex_engine": "xelatex" if competition == "CUMCM" else "pdflatex",
                "main_document": "main.tex",
            },
            "requirements": {
                "paper": {
                    "format": "pdf",
                    "max_front_matter_pages": 1,
                    "max_total_pages": None,
                    "max_body_pages": 30,
                    "max_pdf_bytes": 20_000_000,
                    "page_size": "A4",
                    "table_of_contents_allowed": False,
                    "anonymous": True,
                },
                "submission": {
                    "support_archive_required": competition == "CUMCM",
                    "support_archive_max_bytes": 20_000_000 if competition == "CUMCM" else None,
                },
                "ai": {
                    "policy_checked": True,
                    "usage_statement_required": False,
                    "details_pdf_required": competition == "CUMCM",
                    "statement_source": None,
                    "statement_enable_marker": None,
                    "statement_position": None,
                    "inline_disclosure_required": competition == "CUMCM",
                    "tool_reference_required": competition == "CUMCM",
                    "human_verification_required": competition == "CUMCM",
                    "details_source": "paper/ai_usage_details.tex" if competition == "CUMCM" else None,
                    "details_filename": "AI工具使用详情.pdf" if competition == "CUMCM" else None,
                },
                "artifacts": [],
            },
            "rule_bindings": [],
        }
        for group in ("paper", "submission", "ai"):
            for field, value in profile["requirements"][group].items():
                if value is not None:
                    profile["rule_bindings"].append(
                        {
                            "requirement_pointer": f"/requirements/{group}/{field}",
                            "source_id": "official-rules",
                            "locator": f"fixture section for {group}.{field}",
                            "evidence_sha256": source["sha256"],
                        }
                    )
        source_path = root / source["artifact_path"]
        source_path.write_text("\n".join(item["locator"] for item in profile["rule_bindings"]) + "\n", encoding="utf-8")
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        profile["sources"][0]["sha256"] = source_sha256
        for binding in profile["rule_bindings"]:
            binding["evidence_sha256"] = source_sha256
        (root / "compliance" / "competition_profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def complete_single_claim(self, root: Path) -> None:
        failure = self.make_artifact(root, "innovation/evidence/failure.txt", "baseline violates conservation\n")
        novelty = self.make_artifact(root, "innovation/evidence/precedent.txt", "nearest precedent inspected\n")
        experiment = self.make_artifact(root, "innovation/evidence/falsification.txt", "constraint removes violation\n")
        critic = self.make_artifact(root, "innovation/evidence/critic.txt", "complexity is necessary and minimal\n")
        jury = self.make_artifact(root, "innovation/evidence/jury.txt", "primary claim selected\n")

        self.write_csv_rows(
            root / "innovation" / "claim_portfolio.csv",
            [
                {
                    "claim_id": "C1",
                    "subproblem": "1",
                    "scout_id": "S1",
                    "innovation_axis": "objective_constraint",
                    "problem_structure": "the predicted shares must satisfy a conservation identity",
                    "reasoning_path": "failure_driven",
                    "baseline": "ordinary least squares without a conservation constraint",
                    "baseline_failure": "the fitted shares do not sum to the conserved total",
                    "failure_evidence_artifact": failure["artifact_path"],
                    "failure_evidence_sha256": failure["sha256"],
                    "failure_check": failure["command_or_check"],
                    "failure_checked_at": failure["checked_at"],
                    "proposed_change": "add the single conservation equality",
                    "change_targets_failure": "true",
                    "mathematical_expression": "min L(theta) s.t. sum_i f_theta(x_i)=C",
                    "why_this_change": "the equality directly removes the observed structural violation",
                    "minimality_argument": "one equality is sufficient; no new predictor or optimizer is added",
                    "extra_complexity": "none",
                    "extra_complexity_justified": "not_applicable",
                    "nearest_precedent": "constrained least squares",
                    "difference_from_precedent": "the contest-specific conserved total defines the constraint",
                    "expected_effect": "zero conservation error without material predictive loss",
                    "falsification_test": "turn the equality on and off on held-out and boundary cases",
                    "ablation_required": "false",
                    "complexity_cost": "one linear equality",
                    "paper_location": "paper/sections/04_model.tex",
                    "analogy_source": "",
                    "is_fusion": "false",
                    "component_failure_map": "not_applicable",
                    "mathematical_interface": "not_applicable",
                    "status": "supported",
                    "notes": "single simple primary claim",
                }
            ],
        )
        self.write_csv_rows(
            root / "innovation" / "novelty_audit.csv",
            [
                {
                    "claim_id": "C1",
                    "search_queries": "constrained least squares conservation equality",
                    "primary_sources": "K1",
                    "nearest_precedent": "constrained least squares",
                    "difference": "problem-specific conservation identity and validation",
                    "evidence_locator": "artifact line 1",
                    "novelty_class": "problem_specific",
                    "metadata_status": "verified",
                    "support_status": "supported",
                    "correction_retraction_status": "clear",
                    "source_artifact": novelty["artifact_path"],
                    "source_sha256": novelty["sha256"],
                    "verification_command": novelty["command_or_check"],
                    "checked_at": novelty["checked_at"],
                    "auditor": "literature-auditor",
                    "decision": "pass",
                    "notes": "no claim of a new general theory",
                }
            ],
        )
        self.write_csv_rows(
            root / "innovation" / "claim_experiments.csv",
            [
                {
                    "claim_id": "C1",
                    "experiment_id": "E1",
                    "test_type": "falsification",
                    "component": "conservation equality",
                    "hypothesis": "the change removes the diagnosed failure",
                    "baseline": "unconstrained least squares",
                    "dataset_or_fixture": "held-out and boundary fixture",
                    "command": "python verify_claim.py --claim C1",
                    "seed": "deterministic",
                    "metric": "conservation error",
                    "baseline_value": "0.18",
                    "changed_value": "0.00",
                    "artifact_path": experiment["artifact_path"],
                    "sha256": experiment["sha256"],
                    "checked_at": experiment["checked_at"],
                    "status": "verified",
                    "reviewer": "experiment-reviewer",
                    "decision": "pass",
                    "notes": "minimal change enabled",
                }
            ],
        )
        self.write_csv_rows(
            root / "innovation" / "critic_findings.csv",
            [
                {
                    "finding_id": "F1",
                    "claim_id": "C1",
                    "attack_surface": "necessity and parsimony",
                    "severity": "clear",
                    "finding": "no simpler change removes the verified failure",
                    "repair_or_falsifier": "repeat the change-off test",
                    "status": "clear",
                    "artifact_path": critic["artifact_path"],
                    "sha256": critic["sha256"],
                    "command_or_check": critic["command_or_check"],
                    "checked_at": critic["checked_at"],
                    "reviewer": "blind-critic",
                    "notes": "clear",
                }
            ],
        )
        self.write_csv_rows(
            root / "innovation" / "selection.csv",
            [
                {
                    "claim_id": "C1",
                    "decision": "promote",
                    "paper_role": "primary",
                    "problem_fit": "5",
                    "evidence_strength": "5",
                    "necessity": "5",
                    "novelty": "3",
                    "robustness": "4",
                    "parsimony": "5",
                    "communication": "5",
                    "risks": "contest-specific rather than general novelty",
                    "artifact_path": jury["artifact_path"],
                    "sha256": jury["sha256"],
                    "command_or_check": jury["command_or_check"],
                    "checked_at": jury["checked_at"],
                    "reviewer": "blind-jury",
                    "notes": "one primary claim is sufficient",
                }
            ],
        )

    def test_initializer_creates_claim_engine_and_versioned_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            for relative in (
                "competition_manifest.json",
                "compliance/competition_profile.json",
                "innovation/baseline_failure_map.md",
                "innovation/strong_baseline.md",
                "innovation/semantic_fidelity_map.md",
                "innovation/opportunity_map.md",
                "innovation/claim_portfolio.csv",
                "innovation/claim_experiments.csv",
                "synthesis/innovation_claims.csv",
                "synthesis/model_selection.json",
                "synthesis/global_claim_certificates.json",
                "synthesis/review_route.json",
                "synthesis/paper_payload.json",
                "synthesis/entity_lexicon.csv",
                "audits/review_findings.json",
                "compliance/ai_artifact_inventory.csv",
                "synthesis/implementation_trace.csv",
                "audits/similarity/reference_corpus.csv",
                "shared/problem_contract.json",
                "shared/question_interfaces.json",
                "audits/reproduction/reproduction_status.json",
                "audits/presentation/final_pdf_visual_review.json",
            ):
                self.assertTrue((root / relative).is_file(), relative)
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 15)
            payload = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 4)
            review = json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8"))
            self.assertEqual(review["schema_version"], 3)
            visual_review = json.loads(
                (root / "audits" / "presentation" / "final_pdf_visual_review.json").read_text(encoding="utf-8")
            )
            self.assertEqual(visual_review["schema_version"], 2)
            self.assertEqual(visual_review["page_layout_metrics"], [])
            reproduction = json.loads(
                (root / "audits" / "reproduction" / "reproduction_status.json").read_text(encoding="utf-8")
            )
            self.assertIn("entrypoint", reproduction["runner"])
            self.assertIn("entrypoint_sha256", reproduction["runner"])
            self.assertEqual(manifest["workflow_stage"], "rule_verification")
            self.assertEqual(manifest["branches"], ["model-a"])
            self.assertEqual(validate_task_board(root / "shared" / "task_board.csv")["status"], "pass")
            with (root / "shared" / "task_board.csv").open(encoding="utf-8-sig", newline="") as handle:
                tasks = {row["task_id"]: row for row in csv.DictReader(handle)}
            self.assertNotIn("innovation-selection", tasks["model-a"]["depends_on"])
            self.assertEqual(tasks["innovation-selection"]["blocking"], "false")
            self.assertNotEqual(tasks["strong-baseline"]["assigned_path"], tasks["baseline-failure"]["assigned_path"])

    def test_initializer_refuses_to_partially_upgrade_old_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "competition_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow_version": 7,
                        "competition": "CUMCM",
                        "year": 2026,
                        "problem": "A",
                        "branches": ["model-a"],
                        "innovation_mode": "standard",
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_competition_workspace.py"),
                    str(root),
                    "--competition", "CUMCM",
                    "--year", "2026",
                    "--problem", "A",
                    "--branches", "1",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("migrate_workspace.py", result.stdout)
            self.assertFalse((root / "innovation" / "claim_portfolio.csv").exists())

    def test_one_simple_claim_passes_with_breadth_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root, mode="championship")
            self.complete_single_claim(root)
            report = validate_innovation_portfolio(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertEqual(report["promoted_claims"], ["C1"])
            self.assertTrue(any("search breadth" in item for item in report["warnings"]))

    def test_no_innovation_claim_is_allowed_without_innovation_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            portfolio = validate_innovation_portfolio(root)
            paper = validate_paper_innovation(root)
            self.assertEqual(portfolio["status"], "pass", portfolio["errors"])
            self.assertEqual(paper["status"], "pass", paper["errors"])
            self.assertTrue(any("no innovation claim" in item for item in portfolio["warnings"]))

    def test_claim_without_baseline_failure_evidence_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.complete_single_claim(root)
            with (root / "innovation" / "claim_portfolio.csv").open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["failure_evidence_sha256"] = "0" * 64
            self.write_csv_rows(root / "innovation" / "claim_portfolio.csv", rows)
            report = validate_innovation_portfolio(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("sha256" in item for item in report["errors"]))

    def test_fusion_gets_no_credit_without_component_ablation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.complete_single_claim(root)
            path = root / "innovation" / "claim_portfolio.csv"
            with path.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            rows[0].update(
                {
                    "innovation_axis": "model_fusion",
                    "is_fusion": "true",
                    "extra_complexity": "second component",
                    "extra_complexity_justified": "true",
                    "component_failure_map": "component A: prediction; component B: observation noise",
                    "mathematical_interface": "p(y|x)=p(y|z)p(z|x)",
                }
            )
            self.write_csv_rows(path, rows)
            report = validate_innovation_portfolio(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("requires a verified ablation" in item for item in report["errors"]))

    def test_competition_profile_requires_real_artifact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.assertEqual(validate_competition_profile(root)["status"], "block")
            self.complete_profile(root)
            self.assertEqual(validate_competition_profile(root)["status"], "pass")
            (root / "audits" / "rules" / "official-rules.html").write_text("tampered\n", encoding="utf-8")
            report = validate_competition_profile(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("sha256" in item for item in report["errors"]))

    def complete_paper_claim_mapping(self, root: Path) -> None:
        section = root / "paper" / "sections" / "04_model.tex"
        sentence = "针对基线违反守恒的失败，我们加入一个守恒等式作为最小创新改变。"
        section.write_text(sentence + " % INNOVATION_CLAIM:C1\n", encoding="utf-8")
        result = root / "results" / "R1.txt"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text("conservation error: 0\n", encoding="utf-8")
        self.write_csv_rows(
            root / "synthesis" / "result_manifest.csv",
            [{"result_id": "R1", "status": "verified"}],
        )
        self.write_csv_rows(
            root / "audits" / "citations" / "citation_ledger.csv",
            [{"citation_key": "K1", "metadata_status": "verified", "support_status": "supported"}],
        )
        self.write_csv_rows(
            root / "synthesis" / "innovation_claims.csv",
            [
                {
                    "claim_id": "C1",
                    "claim_sentence": sentence,
                    "problem_structure": "conservation identity",
                    "reasoning_path": "failure_driven",
                    "baseline_failure": "unconstrained fit violates conservation",
                    "method_change": "one equality constraint",
                    "evidence_result_ids": "R1",
                    "novelty_source_keys": "K1",
                    "paper_section": "paper/sections/04_model.tex",
                    "paper_anchor": "INNOVATION_CLAIM:C1",
                    "figure_or_table": "Table 2",
                    "claim_strength": "problem-specific adaptation",
                    "status": "verified",
                    "artifact_path": "paper/sections/04_model.tex",
                    "sha256": hashlib.sha256(section.read_bytes()).hexdigest(),
                    "command_or_check": "manual claim-to-section audit",
                    "checked_at": STAMP,
                    "reviewer": "paper-claim-auditor",
                    "notes": "mapped",
                }
            ],
        )

    def test_paper_claim_audit_maps_promoted_claim_and_blocks_unmapped_superlative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.complete_single_claim(root)
            self.complete_paper_claim_mapping(root)
            self.load_paper_sections(root, "sections/04_model.tex", "sections/05_solution.tex")
            (root / "paper" / "sections" / "05_solution.tex").write_text("% 我们首次提出占位注释。\n", encoding="utf-8")
            self.assertEqual(validate_paper_innovation(root)["status"], "pass")
            extra = root / "paper" / "sections" / "05_solution.tex"
            extra.write_text("我们首次提出一种全新的通用理论。\n", encoding="utf-8")
            report = validate_paper_innovation(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("unmapped strong" in item for item in report["errors"]))

    def test_migration_preserves_legacy_but_resets_evidence_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps(
                    {
                        "workflow_version": 8,
                        "competition": "CUMCM",
                        "year": 2026,
                        "branches": ["model-a"],
                        "innovation_mode": "fast",
                        "paper_engine": "xelatex",
                        "paper_source": "paper/main.tex",
                    }
                ),
                encoding="utf-8",
            )
            (root / "compliance" / "competition_profile.json").write_text(
                json.dumps({"schema_version": 1, "status": "verified", "requirements": {"paper": {"max_body_pages": 30}}}),
                encoding="utf-8",
            )
            (root / "synthesis" / "evidence_matrix.csv").write_text("branch,decision\nmodel-a,selected\n", encoding="utf-8")
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")

            report = migrate(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 15)
            self.assertEqual(manifest["workflow_stage"], "rule_verification")
            self.assertEqual(manifest["innovation_mode"], "standard")
            profile = json.loads((root / "compliance" / "competition_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["schema_version"], 2)
            self.assertEqual(profile["status"], "unverified")
            self.assertEqual(profile["rule_bindings"], [])
            self.assertTrue((root / "compliance" / "competition_profile_v8.json").is_file())
            self.assertTrue((root / "shared" / "task_board_v8.csv").is_file())
            self.assertTrue((root / "synthesis" / "evidence_matrix.csv").is_file())
            self.assertEqual(json.loads((root / "synthesis" / "model_selection.json").read_text(encoding="utf-8"))["status"], "draft")

    def test_v9_migration_preserves_verified_profile_but_resets_changed_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 9,
                        "workflow_version": 9,
                        "competition": "CUMCM",
                        "year": 2026,
                        "branches": ["model-a"],
                        "innovation_mode": "championship",
                    }
                ),
                encoding="utf-8",
            )
            verified_profile = {"schema_version": 2, "status": "verified", "profile_id": "fixture-v2"}
            (root / "compliance" / "competition_profile.json").write_text(json.dumps(verified_profile), encoding="utf-8")
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 1, "status": "frozen", "questions": [{"question_id": "Q1"}]}),
                encoding="utf-8",
            )
            (root / "audits" / "review_findings.json").write_text(
                json.dumps({"schema_version": 1, "status": "reviewed", "coverage": [], "findings": []}),
                encoding="utf-8",
            )
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")

            report = migrate(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            migrated_profile = json.loads(
                (root / "compliance" / "competition_profile.json").read_text(encoding="utf-8")
            )
            self.assertEqual(migrated_profile["status"], "unverified")
            self.assertTrue((root / "compliance" / "competition_profile_v9.json").is_file())
            self.assertTrue((root / "synthesis" / "model_selection_v9.json").is_file())
            self.assertTrue((root / "audits" / "review_findings_v9.json").is_file())
            self.assertEqual(
                json.loads((root / "synthesis" / "model_selection.json").read_text(encoding="utf-8"))["schema_version"],
                2,
            )
            self.assertEqual(
                json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8"))["status"],
                "not_reviewed",
            )
            self.assertTrue((root / "innovation" / "semantic_fidelity_map.md").is_file())

    def test_v11_migration_preserves_scientific_state_and_reopens_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 11,
                        "workflow_version": 11,
                        "competition": "CUMCM",
                        "year": 2026,
                        "branches": ["model-a"],
                        "innovation_mode": "standard",
                    }
                ),
                encoding="utf-8",
            )
            model = {"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "analytical"}]}
            review = {"schema_version": 2, "status": "reviewed", "policy": {"max_accepted_major": 1}, "coverage": [], "findings": []}
            payload = {
                "schema_version": 1,
                "status": "ready",
                "questions": [{"question_id": "Q1", "figures": []}],
            }
            (root / "synthesis" / "model_selection.json").write_text(json.dumps(model), encoding="utf-8")
            (root / "audits" / "review_findings.json").write_text(json.dumps(review), encoding="utf-8")
            (root / "synthesis" / "paper_payload.json").write_text(json.dumps(payload), encoding="utf-8")
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")

            report = migrate(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertEqual(json.loads((root / "synthesis" / "model_selection.json").read_text(encoding="utf-8")), model)
            migrated_review = json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated_review["schema_version"], 3)
            self.assertEqual(migrated_review["status"], "not_reviewed")
            migrated = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 4)
            self.assertEqual(migrated["status"], "draft")
            self.assertEqual(migrated["questions"][0]["presentation_plan"]["answer_form"], "pending")
            self.assertEqual(migrated["questions"][0]["presentation_plan"]["mechanism_visual"], "pending")
            self.assertTrue((root / "synthesis" / "paper_payload_v11.json").is_file())
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 15)

    def test_v12_migration_preserves_payload_and_adds_integrity_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema_version": 12, "workflow_version": 12, "competition": "CUMCM",
                "year": 2026, "branches": ["model-a"], "innovation_mode": "standard",
            }
            payload = {"schema_version": 3, "status": "ready", "questions": [{"question_id": "Q1"}]}
            (root / "competition_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "synthesis" / "paper_payload.json").write_text(json.dumps(payload), encoding="utf-8")
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")
            report = migrate(root)
            self.assertEqual(report["status"], "pass")
            migrated = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 4)
            self.assertEqual(migrated["status"], "draft")
            self.assertEqual(migrated["questions"][0]["question_id"], "Q1")
            self.assertEqual(migrated["questions"][0]["geometry_claims"], [])
            self.assertTrue((root / "compliance" / "ai_artifact_inventory.csv").is_file())
            self.assertTrue((root / "synthesis" / "implementation_trace.csv").is_file())
            self.assertTrue((root / "audits" / "similarity" / "reference_corpus.csv").is_file())
            self.assertEqual(json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))["workflow_version"], 15)
            self.assertEqual(validate_task_board(root / "shared" / "task_board.csv")["status"], "pass")

    def test_v13_migration_invalidates_old_reproduction_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("compliance", "synthesis", "shared", "audits/reproduction", "audits/presentation", "innovation"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps({"schema_version": 13, "workflow_version": 13, "competition": "CUMCM", "year": 2026, "problem": "A", "innovation_mode": "standard"}),
                encoding="utf-8",
            )
            (root / "audits" / "reproduction" / "reproduction_status.json").write_text(
                json.dumps({"status": "pass", "core_results_reproduced": True}), encoding="utf-8"
            )
            (root / "audits" / "review_findings.json").write_text(
                json.dumps({"schema_version": 2, "status": "reviewed", "policy": {"max_open_major": 1}, "coverage": [], "findings": []}), encoding="utf-8"
            )
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")
            report = migrate(root)
            self.assertEqual(report["status"], "pass")
            reproduction = json.loads((root / "audits" / "reproduction" / "reproduction_status.json").read_text(encoding="utf-8"))
            self.assertEqual(reproduction["schema_version"], 2)
            self.assertEqual(reproduction["status"], "pending")
            self.assertTrue((root / "audits" / "reproduction" / "reproduction_status_v13.json").is_file())
            review = json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8"))
            self.assertEqual(review["schema_version"], 3)
            self.assertEqual(review["policy"], {"max_accepted_major": 1})
            self.assertEqual(validate_task_board(root / "shared" / "task_board.csv")["status"], "pass")

    def test_v14_migration_reopens_v15_presentation_and_review_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("compliance", "synthesis", "shared", "audits/reproduction", "audits/presentation", "innovation"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps({
                    "schema_version": 14,
                    "workflow_version": 14,
                    "competition": "CUMCM",
                    "year": 2026,
                    "problem": "A",
                    "innovation_mode": "standard",
                }),
                encoding="utf-8",
            )
            legacy_payload = {
                "schema_version": 3,
                "status": "ready",
                "questions": [{"question_id": "Q1", "figures": [{"role": "data"}]}],
            }
            (root / "synthesis" / "paper_payload.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
            (root / "audits" / "review_findings.json").write_text(
                json.dumps({
                    "schema_version": 2,
                    "status": "reviewed",
                    "policy": {"max_accepted_major": 1},
                    "coverage": [],
                    "findings": [],
                }),
                encoding="utf-8",
            )
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")

            report = migrate(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 15)
            payload = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual((payload["schema_version"], payload["status"]), (4, "draft"))
            self.assertEqual(payload["questions"][0]["geometry_claims"], [])
            figure = payload["questions"][0]["figures"][0]
            self.assertEqual(figure["final_width"], "pending")
            self.assertFalse(figure["final_size_reviewed"])
            review = json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8"))
            self.assertEqual((review["schema_version"], review["status"]), (3, "not_reviewed"))
            visual = json.loads(
                (root / "audits" / "presentation" / "final_pdf_visual_review.json").read_text(encoding="utf-8")
            )
            self.assertEqual(visual["schema_version"], 2)
            self.assertEqual(visual["page_layout_metrics"], [])
            self.assertTrue((root / "synthesis" / "paper_payload_v14.json").is_file())
            self.assertTrue((root / "audits" / "review_findings_v14.json").is_file())
            self.assertTrue((root / "shared" / "task_board_v14.csv").is_file())

    def test_simple_baseline_can_win_model_selection_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            evidence = self.make_artifact(root, "synthesis/evidence/q1-baseline.txt", "diagnostics and robustness passed\n")
            document = {
                "schema_version": 2,
                "status": "frozen",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "statistical",
                        "problem_structure": {
                            "target": "estimate demand",
                            "data": "hourly counts",
                            "constraints": "nonnegative demand",
                            "validation_anchor": "blocked time holdout",
                        },
                        "candidates": [
                            {
                                "model_id": "baseline",
                                "role": "strong_baseline",
                                "pre_fit_rationale": "matches the additive seasonal structure",
                                "complexity_level": "low",
                            }
                        ],
                        "strong_baseline_id": "baseline",
                        "post_fit_evidence": [
                            {
                                "model_id": "baseline",
                                "result_summary": "blocked holdout error is stable across time blocks",
                                "verification_checks": [
                                    {"check_type": "assumptions", "status": "pass", "summary": "seasonality and dependence checked"},
                                    {"check_type": "residual_or_fit", "status": "pass", "summary": "residual seasonality checked"},
                                    {"check_type": "uncertainty", "status": "pass", "summary": "forecast uncertainty quantified"},
                                    {"check_type": "out_of_sample", "status": "pass", "summary": "blocked holdout MAE recorded"},
                                ],
                                **evidence,
                            }
                        ],
                        "selected_model_id": "baseline",
                        "selection_rationale": "no structural failure justified a more complex alternative",
                        "complexity_tradeoff": "extra components add cost without validated benefit",
                        "rejected_models": [],
                    }
                ],
            }
            (root / "synthesis" / "model_selection.json").write_text(json.dumps(document), encoding="utf-8")
            report = validate_model_selection(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertTrue(any("baseline" in item for item in report["warnings"]))

    def test_deterministic_optimization_profile_does_not_require_statistical_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            evidence = self.make_artifact(root, "synthesis/evidence/q1-optimization.txt", "feasible optimum verified\n")
            document = {
                "schema_version": 2,
                "status": "frozen",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "optimization",
                        "problem_structure": {
                            "target": "minimize deterministic transport cost",
                            "data": "fixed network and demand",
                            "constraints": "flow conservation and capacity",
                            "validation_anchor": "exact small instances and independent feasibility check",
                        },
                        "candidates": [
                            {
                                "model_id": "min_cost_flow",
                                "role": "strong_baseline",
                                "pre_fit_rationale": "the constraints have network-flow structure",
                                "complexity_level": "low",
                            }
                        ],
                        "strong_baseline_id": "min_cost_flow",
                        "post_fit_evidence": [
                            {
                                "model_id": "min_cost_flow",
                                "result_summary": "the returned solution is feasible and matches exact small cases",
                                "verification_checks": [
                                    {"check_type": "feasibility", "status": "pass", "summary": "all constraints verified independently"},
                                    {"check_type": "boundary", "status": "pass", "summary": "zero and saturated demand cases verified"},
                                    {"check_type": "optimality_or_search", "status": "pass", "summary": "exact small cases and solver bound agree"},
                                    {"check_type": "sensitivity", "status": "pass", "summary": "capacity perturbations preserve the decision regime"},
                                ],
                                **evidence,
                            }
                        ],
                        "selected_model_id": "min_cost_flow",
                        "selection_rationale": "the simple exact formulation already answers the question",
                        "complexity_tradeoff": "additional predictors do not address a verified failure",
                        "rejected_models": [],
                    }
                ],
            }
            (root / "synthesis" / "model_selection.json").write_text(json.dumps(document), encoding="utf-8")
            report = validate_model_selection(root)
            self.assertEqual(report["status"], "pass", report["errors"])

    def test_draft_model_selection_defers_final_rejection_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            document = {
                "schema_version": 2,
                "status": "draft",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "analytical",
                        "problem_structure": {
                            "target": "derive the boundary",
                            "data": "fixed geometry",
                            "constraints": "finite domains",
                            "validation_anchor": "special cases",
                        },
                        "candidates": [{"model_id": "direct", "pre_fit_rationale": "matches the geometry"}],
                        "strong_baseline_id": "direct",
                        "post_fit_evidence": [],
                        "selected_model_id": "",
                        "selection_rationale": "",
                        "complexity_tradeoff": "",
                        "rejected_models": [],
                    }
                ],
            }
            (root / "synthesis" / "model_selection.json").write_text(json.dumps(document), encoding="utf-8")
            report = validate_model_selection(root)
            self.assertEqual(report["status"], "block")
            self.assertEqual(report["errors"], ["model selection is not frozen"])
            self.assertFalse(any("rejected candidates" in item for item in report["errors"]))

    def test_review_router_is_conditional_but_never_skips_implementation_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            implementation = self.make_artifact(root, "audits/implementation/q1.txt", "equations and code domains agree\n")
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "optimization"}]}),
                encoding="utf-8",
            )
            reviews = {
                kind: {"status": "required", "rationale": "required review"}
                for kind in ("scientific", "implementation", "uncertainty", "claims")
            }
            reviews["statistical"] = {
                "status": "not_applicable",
                "rationale": "the inputs and optimization are deterministic; uncertainty is handled by sensitivity analysis",
            }
            route = {
                "schema_version": 1,
                "status": "routed",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "optimization",
                        "reviews": reviews,
                        "uncertainty_focus": ["parameter_sensitivity", "numerical_solver"],
                        "implementation_assumption_check": {
                            "status": "pass",
                            "summary": "domains, endpoints, constraints and tolerances match the mathematical definition",
                            **implementation,
                        },
                    }
                ],
            }
            (root / "synthesis" / "review_route.json").write_text(json.dumps(route), encoding="utf-8")
            self.assertEqual(validate_review_route(root)["status"], "pass")

            route["questions"][0]["evidence_profile"] = "statistical"
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "statistical"}]}),
                encoding="utf-8",
            )
            (root / "synthesis" / "review_route.json").write_text(json.dumps(route), encoding="utf-8")
            report = validate_review_route(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("statistical review is required" in item for item in report["errors"]))

    def test_draft_review_route_allows_pending_implementation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "analytical"}]}),
                encoding="utf-8",
            )
            reviews = {
                kind: {"status": "required", "rationale": "planned independent review"}
                for kind in ("scientific", "implementation", "uncertainty", "claims")
            }
            reviews["statistical"] = {"status": "not_applicable", "rationale": "fixed analytical inputs"}
            route = {
                "schema_version": 1,
                "status": "draft",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "analytical",
                        "reviews": reviews,
                        "uncertainty_focus": ["model_form"],
                        "implementation_assumption_check": {
                            "status": "pending",
                            "summary": "endpoint and domain checks are planned",
                        },
                    }
                ],
            }
            (root / "synthesis" / "review_route.json").write_text(json.dumps(route), encoding="utf-8")
            report = validate_review_route(root)
            self.assertEqual(report["errors"], ["review routing is not complete"])

    def test_draft_paper_payload_defers_final_content_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "draft", "questions": [{"question_id": "Q1", "evidence_profile": "analytical"}]}),
                encoding="utf-8",
            )
            payload = {
                "schema_version": 4,
                "status": "draft",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "analytical",
                        "problem_summary": "",
                        "assumptions": [],
                        "core_model": "",
                        "derivation_summary": "",
                        "algorithm_summary": "",
                        "key_results": [],
                        "comparison_summary": "",
                        "validation_summary": "",
                        "sensitivity_and_limits": "",
                        "precision_policy": {"display_rule": "", "justification": "", "dominant_uncertainty": ""},
                        "complexity_value": {
                            "mode": "semantics_required",
                            "added_complexity": "题意规定的边界条件",
                            "structural_need": "保持题意完整",
                            "incremental_gain": None,
                            "decision": "保留",
                        },
                        "paper_section": "paper/sections/questions/q01.tex",
                        "figures": [],
                        "citations": [],
                    }
                ],
            }
            (root / "synthesis" / "paper_payload.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            report = validate_paper_presentation(root)
            self.assertEqual(
                report["errors"],
                ["paper payload is not ready", "paper payload requires frozen model_selection.json schema v2"],
            )

    def test_paper_presentation_firewall_accepts_contest_prose_and_blocks_control_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            support = root / "support" / "solve.py"
            support.parent.mkdir(parents=True)
            support.write_text("def solve(): return 1\n", encoding="utf-8")
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\\n"
                "由守恒关系建立最小费用流模型。\\subsection{结果}\\label{sec:q1-answer}\\n"
                "所得方案满足全部守恒与容量约束。\\subsection{验证}\\label{sec:q1-validation}\\n"
                "小规模枚举与网络流结果一致。\\n",
                encoding="utf-8",
            )
            self.load_paper_sections(root, "sections/questions/q01.tex")
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "optimization"}]}), encoding="utf-8"
            )
            payload = {
                "schema_version": 4,
                "status": "ready",
                "questions": [
                    {
                        "question_id": "Q1",
                        "evidence_profile": "optimization",
                        "problem_summary": "在容量约束下确定最低成本的运输方案",
                        "core_model": "最小费用流",
                        "derivation_summary": "由节点流量守恒和弧容量得到线性约束",
                        "algorithm_summary": "使用确定性网络流求解器并复核约束",
                        "comparison_summary": "与直接枚举的小规模算例结果一致",
                        "validation_summary": "可行性、最优界和边界情形均通过检查",
                        "sensitivity_and_limits": "容量扰动下策略稳定，结论依赖网络成本定义",
                        "paper_section": "paper/sections/questions/q01.tex",
                        "key_results": ["所得方案满足全部守恒与容量约束"],
                        "assumptions": ["运输成本在研究时段内保持不变"],
                        "precision_policy": {
                            "display_rule": "成本保留到输入数据支持的两位小数",
                            "justification": "更高位数不改变方案排序",
                            "dominant_uncertainty": "成本参数的测量精度",
                        },
                        "complexity_value": {
                            "mode": "no_extra_complexity",
                            "added_complexity": "未增加额外模型组件",
                            "structural_need": "网络流结构直接对应守恒与容量约束",
                            "incremental_gain": None,
                            "decision": "保留最小费用流模型",
                        },
                        "presentation_plan": {
                            "answer_form": "prose",
                            "answer_anchor": "sec:q1-answer",
                            "answer_takeaway": "所得方案满足全部守恒与容量约束",
                            "validation_form": "prose",
                            "validation_anchor": "sec:q1-validation",
                            "validation_takeaway": "小规模枚举与网络流结果一致",
                            "mechanism_visual": "not_applicable",
                            "mechanism_visual_reason": "本问的核心是代数守恒与容量约束，不依赖空间几何关系",
                            "mechanism_visual_must_show": [],
                        },
                        "figures": [],
                    }
                ],
            }
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")
            section.write_text(
                section.read_text(encoding="utf-8").replace("\\label{sec:q1-answer}", ""),
                encoding="utf-8",
            )
            (root / "paper" / "sections" / "06_global_validation.tex").write_text(
                "\\section{全局验证}\\label{sec:q1-answer}\n",
                encoding="utf-8",
            )
            report = validate_paper_presentation(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("answer_anchor is not present in its own question section" in item for item in report["errors"]))
            section.write_text(
                section.read_text(encoding="utf-8").replace(
                    "\\subsection{结果}", "\\subsection{结果}\\label{sec:q1-answer}"
                ),
                encoding="utf-8",
            )
            payload["questions"][0]["review_type"] = "implementation"
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(validate_paper_presentation(root)["status"], "block")
            del payload["questions"][0]["review_type"]
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            section.write_text("\\section{问题一}\\nQ1验收后冻结，并作为下游接口。\\n", encoding="utf-8")
            report = validate_paper_presentation(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("leaked into final paper" in item for item in report["errors"]))

    def test_geometry_reasoning_requires_registered_mechanism_visual(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            implementation = root / "support" / "solve.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("def balance_constraint(x):\n    return sum(x)\n", encoding="utf-8")
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\n"
                "\\subsection{遮蔽判据}\\label{claim:q1-geometry}\n"
                "\\begin{equation}d(t)\\leq r_c\\label{eq:q1-geometry}\\end{equation}\n"
                "\\begin{figure}\\resizebox{0.84\\linewidth}{!}{\\input{figures/q1_geometry.tex}}\\caption{视线遮蔽几何关系}"
                "\\label{fig:q1-geometry}\\end{figure}\n"
                "\\subsection{结果}\\label{sec:q1-answer}\n有效遮蔽持续 1.39 s。\n"
                "\\subsection{验证}\\label{sec:q1-validation}\n加密计算与解析边界的差异小于 $10^{-4}$ s。\n",
                encoding="utf-8",
            )
            self.load_paper_sections(root, "sections/questions/q01.tex")
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "deterministic_numerical"}]}),
                encoding="utf-8",
            )
            question = {
                "question_id": "Q1",
                "evidence_profile": "deterministic_numerical",
                "problem_summary": "计算导弹视线被球形云团遮蔽的持续时间",
                "assumptions": ["各物体按题意给定轨迹运动"],
                "core_model": "计算云团中心到导弹—圆柱视线段的最远距离",
                "derivation_summary": "在统一坐标系中由轨迹和相交判据得到遮蔽裕度",
                "algorithm_summary": "确定性扫描后对边界时刻二分加密",
                "key_results": ["有效遮蔽持续 1.39 s"],
                "comparison_summary": "与目标中心线简化判据比较，入界时刻推迟 0.04 s",
                "validation_summary": "加密计算与解析边界差异小于 10^{-4} s",
                "sensitivity_and_limits": "结论适用于题面给定的球形云团与直线轨迹",
                "precision_policy": {
                    "display_rule": "正文报告到 0.01 s",
                    "justification": "更高位数小于判据口径差异",
                    "dominant_uncertainty": "遮蔽判据口径",
                },
                "complexity_value": {
                    "mode": "semantics_required",
                    "added_complexity": "完整圆柱边界",
                    "structural_need": "题面目标具有有限尺寸",
                    "incremental_gain": None,
                    "decision": "保留完整圆柱判据",
                },
                "presentation_plan": {
                    "answer_form": "prose",
                    "answer_anchor": "sec:q1-answer",
                    "answer_takeaway": "有效遮蔽持续 1.39 s",
                    "validation_form": "prose",
                    "validation_anchor": "sec:q1-validation",
                    "validation_takeaway": "边界时刻达到正文显示精度",
                    "mechanism_visual": "required",
                    "mechanism_visual_reason": "遮蔽判据依赖导弹、云团、圆柱和视线的空间关系",
                    "mechanism_visual_must_show": ["导弹—圆柱视线段", "云团球与遮蔽锥"],
                },
                "geometry_claims": [{
                    "claim_anchor": "claim:q1-geometry",
                    "objects": ["导弹—圆柱视线段", "云团球"],
                    "relations": ["球与视线束相交时形成有效遮蔽"],
                    "formula_anchor": "eq:q1-geometry",
                    "figure_anchor": "fig:q1-geometry",
                    "not_needed_reason": None,
                    "placement": "判据公式之后、数值结果之前",
                    "ten_second_takeaway": "云团必须覆盖通向有限圆柱目标的视线束，而非只覆盖中心线",
                    "final_size_reviewed": True,
                }],
                "paper_section": "paper/sections/questions/q01.tex",
                "figures": [],
                "citations": [],
            }
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps({"schema_version": 4, "status": "ready", "questions": [question]}, ensure_ascii=False),
                encoding="utf-8",
            )
            report = validate_paper_presentation(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("mechanism visual" in item for item in report["errors"]))

            figure = root / "paper" / "figures" / "q1_geometry.tex"
            figure.write_text("% reproducible TikZ geometry source\n", encoding="utf-8")
            question["figures"] = [
                {
                    "path": "paper/figures/q1_geometry.tex",
                    "role": "mechanism",
                    "supported_claim": "说明完整圆柱遮蔽判据中的对象与空间关系",
                    "source_data": "题面坐标、云团半径和轨迹方程",
                    "generator": "TikZ",
                    "paper_anchor": "fig:q1-geometry",
                    "final_width": "0.84\\linewidth",
                    "minimum_label_pt": 7.0,
                    "final_size_reviewed": True,
                }
            ]
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps({"schema_version": 4, "status": "ready", "questions": [question]}, ensure_ascii=False),
                encoding="utf-8",
            )
            report = validate_paper_presentation(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("never cited" in item for item in report["errors"]))
            section.write_text(
                section.read_text(encoding="utf-8").replace(
                    "\\begin{figure}", "如图~\\ref{fig:q1-geometry} 所示，完整判据同时考虑目标边界与云团。\n\\begin{figure}",
                ),
                encoding="utf-8",
            )
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")
            question["figures"][0]["generator"] = "SciPilot"
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps({"schema_version": 4, "status": "ready", "questions": [question]}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertTrue(any("not mechanism diagrams" in item for item in validate_paper_presentation(root)["errors"]))

    def test_corpus_style_audit_builds_distinct_per_paper_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cards = root / "cards.csv"
            fields = [
                "year", "paper_id", "problem", "title", "source_sha256",
                "abstract_question_mapping_signal", "abstract_numeric_result_signal",
                "abstract_validation_signal", "question_alignment", "per_question_closure_review",
                "validation_signal_breadth", "problem_restatement_section", "problem_analysis_section",
                "assumptions_section", "notation_section", "figure_caption_count_main",
                "table_caption_count_main", "figure_table_roles_review",
            ]
            rows = [
                {
                    "year": "2025", "paper_id": "A001", "problem": "A", "title": "几何定位",
                    "source_sha256": "a" * 64, "abstract_question_mapping_signal": "True",
                    "abstract_numeric_result_signal": "True", "abstract_validation_signal": "True",
                    "question_alignment": "complete", "per_question_closure_review": "model_result_with_validation",
                    "validation_signal_breadth": "broad_signals", "problem_restatement_section": "False",
                    "problem_analysis_section": "True", "assumptions_section": "True", "notation_section": "True",
                    "figure_caption_count_main": "8", "table_caption_count_main": "2",
                    "figure_table_roles_review": "mechanism_or_workflow|diagnostic_or_comparison",
                },
                {
                    "year": "2025", "paper_id": "C002", "problem": "C", "title": "数据预测",
                    "source_sha256": "b" * 64, "abstract_question_mapping_signal": "True",
                    "abstract_numeric_result_signal": "True", "abstract_validation_signal": "False",
                    "question_alignment": "partial", "per_question_closure_review": "model_result_validation_sparse",
                    "validation_signal_breadth": "sparse_signals", "problem_restatement_section": "True",
                    "problem_analysis_section": "True", "assumptions_section": "True", "notation_section": "True",
                    "figure_caption_count_main": "12", "table_caption_count_main": "6",
                    "figure_table_roles_review": "data_or_structure|result_or_decision",
                },
            ]
            with cards.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            for paper_id, text in {
                "A001": "针对问题一求得时长为1.4秒，并通过误差检验。",
                "C002": "针对问题一得到预测值为20。首先处理数据，然后建立模型。",
            }.items():
                folder = root / "ocr" / "2025" / paper_id
                folder.mkdir(parents=True)
                (folder / "combined.txt").write_text(
                    f"===== PAGE 1 =====\n摘要\n{text}\n关键词：测试\n===== PAGE 2 =====\n正文",
                    encoding="utf-8",
                )
            result = build_cards(cards, root / "ocr")
            self.assertEqual(len(result), 2)
            self.assertNotEqual(result[0]["abstract_profile"], result[1]["abstract_profile"])
            self.assertNotEqual(result[0]["visual_profile"], result[1]["visual_profile"])
            report = summarize(result)
            self.assertEqual(report["paper_count"], 2)
            self.assertEqual(report["papers_with_three_or_more_front_matter_sections"], 2)

    def test_faithful_formulation_claim_can_pass_without_baseline_failure_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.complete_single_claim(root)
            semantic = self.make_artifact(root, "innovation/evidence/semantic.txt", "network distance preserves admissible paths\n")
            claim_path = root / "innovation" / "claim_portfolio.csv"
            with claim_path.open(encoding="utf-8-sig") as handle:
                claims = list(csv.DictReader(handle))
            claims[0].update(
                {
                    "reasoning_path": "faithful_formulation",
                    "semantic_requirement": "distance must follow admissible network paths",
                    "faithfulness_argument": "network shortest-path distance preserves the feasible movement semantics",
                    "simplified_benchmark": "Euclidean distance baseline",
                    "faithfulness_evidence_artifact": semantic["artifact_path"],
                    "faithfulness_evidence_sha256": semantic["sha256"],
                    "faithfulness_check": semantic["command_or_check"],
                    "faithfulness_checked_at": semantic["checked_at"],
                }
            )
            self.write_csv_rows(claim_path, claims)
            experiment_path = root / "innovation" / "claim_experiments.csv"
            with experiment_path.open(encoding="utf-8-sig") as handle:
                experiments = list(csv.DictReader(handle))
            experiments.append(
                {
                    "claim_id": "C1",
                    "experiment_id": "E2",
                    "test_type": "semantic_fidelity",
                    "component": "network distance",
                    "hypothesis": "the formulation excludes physically inadmissible shortcuts",
                    "baseline": "Euclidean distance",
                    "dataset_or_fixture": "network with a blocked crossing",
                    "command": "python verify_claim.py --claim C1 --semantic",
                    "seed": "deterministic",
                    "metric": "inadmissible shortcut count",
                    "baseline_value": "1",
                    "changed_value": "0",
                    "artifact_path": semantic["artifact_path"],
                    "sha256": semantic["sha256"],
                    "checked_at": semantic["checked_at"],
                    "status": "verified",
                    "reviewer": "semantic-reviewer",
                    "decision": "pass",
                    "notes": "faithful formulation check",
                }
            )
            self.write_csv_rows(experiment_path, experiments)
            report = validate_innovation_portfolio(root)
            self.assertEqual(report["status"], "pass", report["errors"])

    def test_scientific_review_blocks_unresolved_critical_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            evidence = self.make_artifact(root, "audits/review/critical.txt", "leakage found in split\n")
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text("\\section{问题一}\\label{sec:q1-review}\n直接结论。\n", encoding="utf-8")
            (root / "synthesis" / "review_route.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "routed",
                        "questions": [
                            {
                                "question_id": "Q1",
                                "reviews": {
                                    kind: {"status": "required", "rationale": "independently checked"}
                                    for kind in ("scientific", "implementation", "statistical", "uncertainty", "claims")
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            document = {
                "schema_version": 3,
                "status": "reviewed",
                "policy": {"max_accepted_major": 1},
                "coverage": [
                    {
                        "question_id": "Q1",
                        "review_type": kind,
                        "status": "pass",
                        "rationale": f"针对第一问执行{kind}专项审查并核对结论边界",
                        "paper_anchor": "sec:q1-review",
                        "concrete_check": f"逐项核对第一问的{kind}定义、实现细节和直接答案",
                        "falsification_or_boundary_attack": f"改变第一问边界条件并尝试推翻{kind}结论",
                        "outcome": "finding_recorded" if kind == "statistical" else "no_material_issue",
                        **evidence,
                    }
                    for kind in ("scientific", "implementation", "statistical", "uncertainty", "claims")
                ],
                "findings": [
                    {
                        "finding_id": "F1",
                        "question_id": "Q1",
                        "review_type": "statistical",
                        "severity": "critical",
                        "summary": "time leakage invalidates validation",
                        "affected_claim_or_result": "Q1 forecast accuracy",
                        "status": "open",
                        "resolution": "replace random split with blocked holdout",
                        **evidence,
                    }
                ],
            }
            (root / "audits" / "review_findings.json").write_text(json.dumps(document), encoding="utf-8")
            report = validate_review_findings(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("critical" in item for item in report["errors"]))

    def test_problem_contract_is_source_bound_and_matches_model_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            source = self.make_artifact(root, "inputs/original/problem.txt", "问题一：计算结果。\n问题二：沿用问题一。\n")
            contract = {
                "schema_version": 1,
                "status": "frozen",
                "problem_artifacts": [
                    {
                        "source_id": "P1",
                        "relative_path": source["artifact_path"],
                        "sha256": source["sha256"],
                        "verification_command": source["command_or_check"],
                        "verified_at": source["checked_at"],
                        "reviewer": "prompt-auditor",
                    }
                ],
                "questions": [
                    {
                        "question_id": "Q1", "source_id": "P1", "source_locator": "line 1",
                        "task_verbs": ["计算"], "required_answer": "数值结果", "required_artifacts": [],
                        "inputs": "原题数据", "upstream_question_ids": [], "constraints_precision": "题面精度",
                        "verified_against_prompt": True, "verification_notes": "逐字核对",
                    },
                    {
                        "question_id": "Q2", "source_id": "P1", "source_locator": "line 2",
                        "task_verbs": ["沿用"], "required_answer": "下游结果", "required_artifacts": [],
                        "inputs": "原题与 Q1", "upstream_question_ids": ["Q1"], "constraints_precision": "题面精度",
                        "verified_against_prompt": True, "verification_notes": "逐字核对",
                    },
                ],
            }
            (root / "shared" / "problem_contract.json").write_text(json.dumps(contract), encoding="utf-8")
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"questions": [{"question_id": "Q1"}, {"question_id": "Q2"}]}), encoding="utf-8"
            )
            self.assertEqual(validate_problem_contract(root, final=True)["status"], "pass")
            contract["problem_artifacts"][0]["sha256"] = "0" * 64
            (root / "shared" / "problem_contract.json").write_text(json.dumps(contract), encoding="utf-8")
            report = validate_problem_contract(root, final=True)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("sha256" in item for item in report["errors"]))

    def test_question_interface_detects_stale_upstream_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "shared" / "problem_contract.json").write_text(
                json.dumps({"questions": [{"question_id": "Q1", "upstream_question_ids": []}, {"question_id": "Q2", "upstream_question_ids": ["Q1"]}]}),
                encoding="utf-8",
            )
            result_file = root / "branches" / "model-a" / "results" / "q1.txt"
            result_file.write_text("1.0\n", encoding="utf-8")
            environment = root / "environment" / "snapshot.json"
            environment.write_text("{}\n", encoding="utf-8")
            row = {
                "result_id": "R1", "question_id": "Q1", "claim_location": "Q1",
                "value": "1.0", "unit": "s", "relative_path": "branches/model-a/results/q1.txt",
                "generator": "fixture", "command": "python solve.py", "input_ids": "D1", "seed": "deterministic",
                "environment_file": "environment/snapshot.json", "sha256": hashlib.sha256(result_file.read_bytes()).hexdigest(),
                "status": "verified", "reviewer": "reviewer", "notes": "",
            }
            self.write_csv_rows(root / "synthesis" / "result_manifest.csv", [row])
            evidence = self.make_artifact(root, "branches/model-a/results/q2-used-r1.txt")
            interface = {
                "schema_version": 1, "status": "frozen", "interfaces": [
                    {
                        "interface_id": "I1", "producer_question_id": "Q1", "consumer_question_id": "Q2",
                        "result_ids": ["R1"], "result_fingerprints": {"R1": result_fingerprint(row)},
                        "status": "frozen", "reviewer": "integrator", **evidence,
                    }
                ],
            }
            (root / "shared" / "question_interfaces.json").write_text(json.dumps(interface), encoding="utf-8")
            self.assertEqual(validate_question_interfaces(root, final=True)["status"], "pass")
            row["value"] = "1.1"
            self.write_csv_rows(root / "synthesis" / "result_manifest.csv", [row])
            report = validate_question_interfaces(root, final=True)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("stale" in item for item in report["errors"]))

    def test_malformed_question_dependency_blocks_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "shared" / "problem_contract.json").write_text(
                json.dumps({"schema_version": 1, "status": "frozen", "problem_artifacts": [], "questions": [{"question_id": "Q1", "upstream_question_ids": None}]}),
                encoding="utf-8",
            )
            self.assertEqual(validate_problem_contract(root, final=True)["status"], "block")
            self.assertEqual(validate_question_interfaces(root, final=True)["status"], "block")

    def test_reproduction_executes_in_clean_copy_and_checks_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            output = root / "results" / "answer.txt"
            output.parent.mkdir()
            output.write_text("42\n", encoding="utf-8")
            self.write_csv_rows(
                root / "synthesis" / "result_manifest.csv",
                [{"result_id": "R1", "question_id": "Q1", "relative_path": "results/answer.txt"}],
            )
            runner_script = root / "support" / "reproduce.py"
            runner_script.parent.mkdir(exist_ok=True)
            runner_script.write_text(
                "from pathlib import Path\n"
                "Path('results').mkdir(exist_ok=True)\n"
                "Path('results/answer.txt').write_text('42\\n')\n",
                encoding="utf-8",
            )
            document = {
                "schema_version": 2, "status": "ready", "reviewer": "independent-runner", "checked_at": STAMP,
                "runner": {
                    "argv": [sys.executable, "support/reproduce.py"],
                    "entrypoint": "support/reproduce.py",
                    "entrypoint_sha256": hashlib.sha256(runner_script.read_bytes()).hexdigest(),
                    "working_directory": ".", "timeout_seconds": 30, "clean_paths": ["results"],
                },
                "expected_artifacts": [{"relative_path": "results/answer.txt", "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}],
                "blocking_findings": [],
            }
            (root / "audits" / "reproduction" / "reproduction_status.json").write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(run_reproduction(root)["status"], "pass")
            runner_script.write_text("print('did not generate result')\n", encoding="utf-8")
            document["runner"]["entrypoint_sha256"] = hashlib.sha256(runner_script.read_bytes()).hexdigest()
            (root / "audits" / "reproduction" / "reproduction_status.json").write_text(json.dumps(document), encoding="utf-8")
            report = run_reproduction(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("hash-mismatched" in item for item in report["errors"]))

    def test_reproduction_rejects_inline_unbound_and_dangerous_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            script = root / "support" / "reproduce.py"
            script.parent.mkdir(exist_ok=True)
            script.write_text("print('reproduce')\n", encoding="utf-8")
            output = root / "results" / "answer.txt"
            output.parent.mkdir()
            output.write_text("42\n", encoding="utf-8")
            document = {
                "schema_version": 2,
                "status": "ready",
                "reviewer": "independent-runner",
                "checked_at": STAMP,
                "runner": {
                    "argv": [sys.executable, "support/reproduce.py"],
                    "entrypoint": "support/reproduce.py",
                    "entrypoint_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
                    "working_directory": ".",
                    "timeout_seconds": 30,
                    "clean_paths": ["results/./"],
                },
                "expected_artifacts": [{
                    "relative_path": "results/../results/answer.txt",
                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                }],
                "blocking_findings": [],
            }
            self.assertEqual(validate_contract(root, document)[0], [])

            document["runner"]["argv"] = [sys.executable, "-c", "print(42)", "support/reproduce.py"]
            self.assertTrue(any("inline command" in item for item in validate_contract(root, document)[0]))
            document["runner"]["argv"] = [sys.executable, "support/reproduce.py"]
            document["runner"]["entrypoint_sha256"] = "0" * 64
            self.assertTrue(any("hash-mismatched" in item for item in validate_contract(root, document)[0]))
            document["runner"]["entrypoint_sha256"] = hashlib.sha256(script.read_bytes()).hexdigest()

            for clean_path, expected_fragment in (
                (".", "workspace root"),
                ("inputs/../inputs/cache", "protected inputs"),
                ("support", "protected inputs"),
                ("environment", "protected inputs"),
                ("scratch", "named output"),
            ):
                document["runner"]["clean_paths"] = [clean_path]
                self.assertTrue(
                    any(expected_fragment in item for item in validate_contract(root, document)[0]),
                    clean_path,
                )

            document["runner"].update({
                "argv": [sys.executable, "../../support/reproduce.py"],
                "working_directory": "results/run",
                "clean_paths": ["results"],
            })
            errors = validate_contract(root, document)[0]
            self.assertTrue(any(
                "runner working directory or its ancestor" in item
                for item in errors
            ), errors)

            document["runner"].update({
                "argv": [sys.executable, "support/reproduce.py"],
                "working_directory": ".",
                "clean_paths": ["results"],
            })
            document["expected_artifacts"][0]["relative_path"] = "other/answer.txt"
            other = root / "other" / "answer.txt"
            other.parent.mkdir()
            other.write_text("42\n", encoding="utf-8")
            document["expected_artifacts"][0]["sha256"] = hashlib.sha256(other.read_bytes()).hexdigest()
            self.assertTrue(any("outside the declared output" in item for item in validate_contract(root, document)[0]))

    def test_accepted_major_risk_requires_owner_scope_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            evidence = self.make_artifact(root, "audits/review/major.txt")
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text("\\section{问题一}\\label{sec:q1-review}\n直接结论。\n", encoding="utf-8")
            reviews = {kind: {"status": "required", "rationale": "review"} for kind in ("scientific", "implementation", "statistical", "uncertainty", "claims")}
            (root / "synthesis" / "review_route.json").write_text(
                json.dumps({"schema_version": 1, "status": "routed", "questions": [{"question_id": "Q1", "reviews": reviews}]}), encoding="utf-8"
            )
            finding = {
                "finding_id": "M1", "question_id": "Q1", "review_type": "scientific", "severity": "major",
                "summary": "limited boundary evidence", "affected_claim_or_result": "Q1", "status": "accepted_risk",
                "resolution": "restrict conclusion", **evidence,
            }
            document = {
                "schema_version": 3, "status": "reviewed", "policy": {"max_accepted_major": 1},
                "coverage": [{
                    "question_id": "Q1", "review_type": kind, "status": "pass",
                    "rationale": f"针对第一问执行{kind}专项审查并限定结论范围",
                    "paper_anchor": "sec:q1-review",
                    "concrete_check": f"逐项核对第一问的{kind}定义、实现和直接答案",
                    "falsification_or_boundary_attack": f"改变第一问边界条件并尝试推翻{kind}结论",
                    "outcome": "finding_recorded" if kind == "scientific" else "no_material_issue",
                    **evidence,
                } for kind in reviews],
                "findings": [finding],
            }
            (root / "audits" / "review_findings.json").write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(validate_review_findings(root)["status"], "block")
            finding.update({"risk_owner": "team lead", "impact_scope": "one boundary scenario", "fallback": "report conservative bound"})
            (root / "audits" / "review_findings.json").write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(validate_review_findings(root)["status"], "pass")

    def test_visual_reviews_are_bound_to_rendered_page_hashes(self) -> None:
        digest = "a" * 64
        metric = {
            "page": 1,
            "content_top_ratio": 0.1,
            "content_bottom_ratio": 0.8,
            "bottom_blank_ratio": 0.2,
            "word_count": 120,
            "excluded_footer_word_count": 1,
        }
        document = {
            "page_reviews": [{
                "page": 1,
                "image_path": "audits/presentation/final_pdf_pages/page-001.png",
                "image_sha256": digest,
                "status": "pass",
                "reviewer": "page-reviewer",
                "checked_at": STAMP,
                "checks": {
                    "crop_and_overlap": "pass",
                    "fonts_and_symbols": "pass",
                    "equations_tables_figures": "pass",
                    "plot_readability_and_density": "pass",
                    "float_flow_and_page_balance": "pass",
                    "pagination_and_anonymity": "pass",
                },
                "automated_metrics": metric,
                "layout_disposition": "not_flagged",
                "notes": "页面布局均衡",
            }]
        }
        self.assertEqual(validate_review_records(document, [digest], [metric]), [])
        self.assertTrue(any("changed" in item for item in validate_review_records(document, ["b" * 64], [metric])))

    def test_sparse_visual_review_requires_intentional_disposition_and_note(self) -> None:
        digest = "a" * 64
        metric = {
            "page": 1,
            "content_top_ratio": 0.1,
            "content_bottom_ratio": 0.35,
            "bottom_blank_ratio": 0.65,
            "word_count": 45,
            "excluded_footer_word_count": 1,
        }
        review = {
            "page": 1,
            "image_path": "audits/presentation/final_pdf_pages/page-001.png",
            "image_sha256": digest,
            "status": "pass",
            "checks": {
                "crop_and_overlap": "pass",
                "fonts_and_symbols": "pass",
                "equations_tables_figures": "pass",
                "plot_readability_and_density": "pass",
                "float_flow_and_page_balance": "pass",
                "pagination_and_anonymity": "pass",
            },
            "automated_metrics": metric,
            "layout_disposition": "not_flagged",
            "reviewer": "page-reviewer",
            "checked_at": STAMP,
            "notes": "",
        }
        document = {"page_reviews": [review]}
        errors = validate_review_records(document, [digest], [metric])
        self.assertTrue(any("explicit intentional layout disposition" in item for item in errors))
        review["layout_disposition"] = "intentional_end_matter"
        errors = validate_review_records(document, [digest], [metric])
        self.assertTrue(any("concrete note" in item for item in errors))
        review["notes"] = "参考文献在本页结束，留白由文献条目自然收束形成。"
        self.assertEqual(validate_review_records(document, [digest], [metric]), [])

    def test_pdftoppm_resolver_returns_runnable_binary_or_none(self) -> None:
        executable = resolve_pdftoppm()
        if executable is None:
            return
        self.assertTrue(Path(executable).is_file())
        if sys.platform == "win32":
            self.assertNotEqual(Path(executable).suffix.lower(), ".cmd")

    def test_benchmark_score_tracks_false_innovation_and_simplicity(self) -> None:
        report = score(
            {
                "cases": [
                    {
                        "supported_claim_count": 2,
                        "false_innovation_count": 1,
                        "mean_component_count": 1.5,
                        "baseline_gain_coverage": 1.0,
                        "reproducibility_rate": 1.0,
                        "paper_mapping_rate": 0.5,
                        "paper_meta_language_rate": 0.0,
                        "adaptive_review_accuracy": 1.0,
                        "implementation_gap_detection_rate": 1.0,
                        "presentation_blind_score": 4.0,
                        "blind_quality_score": 4.0,
                    },
                    {
                        "supported_claim_count": 1,
                        "false_innovation_count": 0,
                        "mean_component_count": 1.0,
                        "baseline_gain_coverage": 0.5,
                        "reproducibility_rate": 1.0,
                        "paper_mapping_rate": 1.0,
                        "paper_meta_language_rate": 0.0,
                        "adaptive_review_accuracy": 1.0,
                        "implementation_gap_detection_rate": 0.5,
                        "presentation_blind_score": 5.0,
                        "blind_quality_score": 5.0,
                    },
                ]
            }
        )
        self.assertAlmostEqual(report["false_innovation_rate"], 0.25)
        self.assertAlmostEqual(report["mean_component_count"], 1.25)

    def test_task_board_rejects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            board = Path(temp) / "task_board.csv"
            with board.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["task_id", "task_type", "depends_on", "assigned_path", "fallback", "deliverables", "status", "blocking"])
                writer.writerow(["a", "model", "b", "a", "baseline", "result", "pending", "true"])
                writer.writerow(["b", "model", "a", "b", "baseline", "result", "pending", "true"])
            report = validate_task_board(board)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("cycle" in item for item in report["errors"]))

    def test_v15_task_board_requires_core_tasks_strict_booleans_and_dynamic_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            board = root / "shared" / "task_board.csv"
            with board.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                if row["task_id"] == "model-a":
                    row["task_id"] = "model-geometry"
                    row["assigned_path"] = "branches/model-geometry"
                dependencies = ["model-geometry" if item == "model-a" else item for item in row["depends_on"].split(";")]
                row["depends_on"] = ";".join(dependencies)
            self.write_csv_rows(board, rows)
            self.assertEqual(validate_task_board(board)["status"], "pass")

            rows[0]["blocking"] = "yes"
            self.write_csv_rows(board, rows)
            report = validate_task_board(board)
            self.assertTrue(any("exactly true or false" in item for item in report["errors"]))

            rows[0]["blocking"] = "true"
            rows = [row for row in rows if row["task_id"] != "reproduction"]
            self.write_csv_rows(board, rows)
            report = validate_task_board(board)
            self.assertTrue(any("missing required task IDs" in item and "reproduction" in item for item in report["errors"]))

            self.initialize(root)
            with board.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows = [row for row in rows if row["task_id"] != "baseline-failure"]
            self.write_csv_rows(board, rows)
            self.assertTrue(any("baseline-failure" in item for item in validate_task_board(board)["errors"]))

    def package_fixture(self, root: Path, content: str) -> None:
        (root / "compliance").mkdir(parents=True)
        (root / "submission").mkdir(parents=True)
        (root / "support").mkdir(parents=True)
        (root / "compliance" / "anonymity_terms.txt").write_text("Test University\nReal Name\n", encoding="utf-8")
        (root / "submission" / "support_manifest.json").write_text(
            json.dumps({"archive_name": "support.zip", "files": ["support/code.py"]}), encoding="utf-8"
        )
        (root / "support" / "code.py").write_text(content, encoding="utf-8")

    def test_packager_blocks_credentials_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
            self.package_fixture(root, f"API_KEY = '{fake_key}'\n")
            self.assertEqual(package_workspace(root)["status"], "block")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.package_fixture(root, "print('verified result')\n")
            first = package_workspace(root)
            second = package_workspace(root)
            self.assertEqual(first["status"], "pass")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            (root / "submission" / "support_manifest.json").write_text(
                json.dumps(
                    {
                        "archive_name": "renamed.zip",
                        "files": [{"source": "support/code.py", "archive_path": "code.py"}],
                    }
                ),
                encoding="utf-8",
            )
            renamed = package_workspace(root)
            self.assertEqual(renamed["status"], "pass")
            with zipfile.ZipFile(root / "submission" / "renamed.zip") as archive:
                self.assertEqual(archive.namelist(), ["code.py"])

    def test_provenance_rejects_unregistered_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "inputs" / "original" / "problem.txt").write_text("problem", encoding="utf-8")
            self.assertTrue(any("missing from data_provenance" in item for item in check_data_provenance(root)))

    def test_finalizer_fails_closed_on_unreviewed_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            report = finalize(root)
            self.assertEqual(report["status"], "block")
            self.assertEqual(report["build_status"], "skipped_upstream_block")
            self.assertFalse((root / "submission" / "submission_manifest.json").exists())

    def test_ai_gate_is_profile_driven_not_competition_hardcoded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            profile = {
                "competition": "ANY-CONTEST",
                "build": {"latex_engine": "xelatex", "main_document": "main.tex"},
                "requirements": {
                    "ai": {
                        "usage_statement_required": True,
                        "details_pdf_required": False,
                        "statement_source": "paper/sections/09_ai_statement.tex",
                        "statement_enable_marker": "\\IncludeAIUsageStatementtrue",
                        "statement_position": "before_references",
                    }
                },
            }
            statement = root / "paper" / "sections" / "09_ai_statement.tex"
            statement.write_text("\\section*{AI 工具使用声明}\n所有 AI 使用均由队员复核。\n", encoding="utf-8")
            metadata = root / "paper" / "generated" / "metadata.tex"
            metadata.write_text(
                metadata.read_text(encoding="utf-8").replace("\\IncludeAIUsageStatementtrue", "\\IncludeAIUsageStatementfalse"),
                encoding="utf-8",
            )
            errors = check_ai_compliance(root, profile)
            self.assertTrue(any("not enabled" in item for item in errors))
            profile["requirements"]["ai"]["usage_statement_required"] = False
            profile["requirements"]["ai"]["details_pdf_required"] = False
            self.assertEqual(check_ai_compliance(root, profile), [])

    def test_cumcm_ai_ledger_requires_inline_anchor_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            evidence = self.make_artifact(root, "compliance/evidence/ai-use.txt", "prompt and verification record\n")
            section = root / "paper" / "sections" / "04_model.tex"
            section.write_text("AI assisted code was independently checked. % AI_USE:U1\n", encoding="utf-8")
            self.write_csv_rows(
                root / "compliance" / "ai_usage_ledger.csv",
                [
                    {
                        "use_id": "U1",
                        "tool": "Codex",
                        "version": "recorded-at-use",
                        "purpose": "draft and test code",
                        "paper_section": "paper/sections/04_model.tex",
                        "paper_anchor": "AI_USE:U1",
                        "citation_key": "",
                        "human_changes": "reviewed equations, reran tests, and rewrote prose",
                        "verification_status": "verified",
                        **evidence,
                        "reviewer": "team-member",
                        "notes": "fixture",
                    }
                ],
            )
            profile = {
                "competition": "CUMCM",
                "requirements": {
                    "ai": {
                        "usage_statement_required": False,
                        "details_pdf_required": False,
                        "inline_disclosure_required": True,
                        "tool_reference_required": False,
                        "human_verification_required": True,
                        "details_filename": None,
                    }
                },
            }
            inventory_rows = []
            for path in sorted((root / "paper").rglob("*")):
                if not path.is_file() or "build" in path.relative_to(root).parts or path.name == "ai_usage_details.tex":
                    continue
                rel = path.relative_to(root).as_posix()
                inventory_rows.append({
                    "artifact_id": f"A{len(inventory_rows) + 1}", "artifact_type": "paper",
                    "relative_path": rel, "ai_used": "true" if path == section else "false",
                    "use_ids": "U1" if path == section else "",
                    "human_verification": "reviewed equations and reran tests" if path == section else "",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewer": "team-member",
                    "checked_at": STAMP,
                })
            self.write_csv_rows(root / "compliance" / "ai_artifact_inventory.csv", inventory_rows)
            self.assertEqual(check_ai_compliance(root, profile), [])
            (root / "compliance" / "evidence" / "ai-use.txt").write_text("tampered\n", encoding="utf-8")
            self.assertTrue(any("sha256" in item for item in check_ai_compliance(root, profile)))

    def test_ai_inventory_detects_unmapped_use_and_unclassified_deliverable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            section = root / "paper" / "sections" / "04_model.tex"
            section.write_text("人工复核后的模型说明。 % AI_USE:U1\n", encoding="utf-8")
            evidence = self.make_artifact(root, "compliance/evidence/u1.txt", "prompt, response and rerun evidence\n")
            self.write_csv_rows(
                root / "compliance" / "ai_usage_ledger.csv",
                [{
                    "use_id": "U1", "tool": "Codex", "version": "recorded", "purpose": "code review",
                    "paper_section": "paper/sections/04_model.tex", "paper_anchor": "AI_USE:U1",
                    "human_changes": "reran the implementation and rewrote the explanation",
                    "verification_status": "verified", **evidence, "reviewer": "team-member",
                }],
            )
            profile = {"requirements": {"ai": {"human_verification_required": True}}}
            errors = check_ai_compliance(root, profile)
            self.assertTrue(any("artifact inventory" in item for item in errors))

            inventory_rows = []
            for path in sorted((root / "paper").rglob("*")):
                if not path.is_file() or "build" in path.relative_to(root).parts or path.name == "ai_usage_details.tex":
                    continue
                rel = path.relative_to(root).as_posix()
                inventory_rows.append({
                    "artifact_id": f"A{len(inventory_rows) + 1}", "artifact_type": "paper",
                    "relative_path": rel, "ai_used": "true" if path == section else "false",
                    "use_ids": "U1" if path == section else "",
                    "human_verification": "rerun and rewrite" if path == section else "",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewer": "team-member",
                    "checked_at": STAMP,
                })
            self.write_csv_rows(root / "compliance" / "ai_artifact_inventory.csv", inventory_rows)
            self.assertEqual(check_ai_compliance(root, profile), [])
            inventory_rows[0]["use_ids"] = "UNKNOWN"
            inventory_rows[0]["ai_used"] = "true"
            inventory_rows[0]["human_verification"] = "checked"
            self.write_csv_rows(root / "compliance" / "ai_artifact_inventory.csv", inventory_rows)
            self.assertTrue(any("unknown use_id" in item for item in check_ai_compliance(root, profile)))

    def test_paper_integrity_blocks_chat_residue_and_missing_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            implementation = root / "support" / "solve.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("def balance_constraint(x):\n    return sum(x)\n", encoding="utf-8")
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text("\\section{问题一}\n作为一个人工智能，以下给出答案。\n", encoding="utf-8")
            self.load_paper_sections(root, "sections/questions/q01.tex")
            report = validate_paper_integrity(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("chat-assistant" in item for item in report["errors"]))
            self.assertTrue(any("implementation_trace" in item for item in report["errors"]))

            section.write_text("\\section{问题一}\n由守恒关系建立约束。\\label{eq:q1-balance}\n", encoding="utf-8")
            test = self.make_artifact(root, "audits/implementation/q1.txt", "balance constraint test passed\n")
            result = root / "results" / "r1.txt"
            result.parent.mkdir(parents=True)
            result.write_text("0\n", encoding="utf-8")
            self.write_csv_rows(root / "synthesis" / "result_manifest.csv", [{"result_id": "R1"}])
            self.write_csv_rows(
                root / "synthesis" / "implementation_trace.csv",
                [{
                    "trace_id": "T1", "question_id": "Q1", "paper_section": "paper/sections/questions/q01.tex",
                    "equation_or_claim_anchor": "eq:q1-balance", "mathematical_role": "conservation constraint",
                    "implementation_path": "support/solve.py", "implementation_symbol": "balance_constraint",
                    "test_artifact_path": test["artifact_path"], "test_sha256": test["sha256"],
                    "test_command": test["command_or_check"], "result_ids": "R1", "reviewer": "implementation-reviewer",
                    "checked_at": STAMP,
                }],
            )
            self.assertEqual(validate_paper_integrity(root)["status"], "pass")

    def test_similarity_precheck_reports_excellent_paper_and_template_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            phrase = "针对观测序列中的周期变化我们构造分段状态变量并以滚动窗口完成参数更新"
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text("\\section{问题一}\n" + phrase * 3 + "\n", encoding="utf-8")
            self.load_paper_sections(root, "sections/questions/q01.tex")
            excellent = root / "audits" / "similarity" / "corpus" / "E1.txt"
            template = root / "audits" / "similarity" / "corpus" / "T1.txt"
            excellent.write_text(phrase * 3, encoding="utf-8")
            template.write_text("另一段固定模板语言用于解释计算结果与实际约束之间的对应关系", encoding="utf-8")
            self.write_csv_rows(
                root / "audits" / "similarity" / "reference_corpus.csv",
                [
                    {"source_id": "E1", "source_type": "excellent_paper", "text_path": excellent.relative_to(root).as_posix(), "sha256": hashlib.sha256(excellent.read_bytes()).hexdigest(), "status": "verified"},
                    {"source_id": "T1", "source_type": "template", "text_path": template.relative_to(root).as_posix(), "sha256": hashlib.sha256(template.read_bytes()).hexdigest(), "status": "verified"},
                ],
            )
            report = validate_similarity_precheck(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("excellent-paper overlap" in item for item in report["errors"]))
            section.write_text("\\section{问题一}\n根据数据中的局部变化建立状态量，并用留出区间检验结果。\n", encoding="utf-8")
            self.assertEqual(validate_similarity_precheck(root)["status"], "pass")


if __name__ == "__main__":
    unittest.main()
