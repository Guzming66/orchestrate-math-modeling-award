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
from build_latex import scan_sources
from migrate_workspace import migrate
from package_submission import package_workspace
from score_claim_benchmark import score
from validate_competition_profile import validate_competition_profile
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_model_selection import validate_model_selection
from validate_paper_innovation import validate_paper_innovation
from validate_paper_presentation import validate_paper_presentation
from validate_paper_question_coverage import validate_paper_question_coverage
from validate_review_findings import validate_review_findings
from validate_review_route import validate_review_route
from validate_task_board import validate_task_board


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

    def test_cumcm_question_coverage_matches_frozen_model_questions(self) -> None:
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
                "synthesis/review_route.json",
                "synthesis/paper_payload.json",
                "audits/review_findings.json",
            ):
                self.assertTrue((root / relative).is_file(), relative)
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 11)
            payload = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
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
            self.assertEqual(manifest["workflow_version"], 11)
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
            self.assertEqual(
                json.loads((root / "compliance" / "competition_profile.json").read_text(encoding="utf-8")),
                verified_profile,
            )
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

    def test_v10_migration_preserves_scientific_state_and_reopens_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 10,
                        "workflow_version": 10,
                        "competition": "CUMCM",
                        "year": 2026,
                        "branches": ["model-a"],
                        "innovation_mode": "standard",
                    }
                ),
                encoding="utf-8",
            )
            model = {"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "analytical"}]}
            review = {"schema_version": 2, "status": "reviewed", "policy": {"max_open_major": 1}, "coverage": [], "findings": []}
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
            self.assertEqual(json.loads((root / "audits" / "review_findings.json").read_text(encoding="utf-8")), review)
            migrated = json.loads((root / "synthesis" / "paper_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 2)
            self.assertEqual(migrated["status"], "draft")
            self.assertEqual(migrated["questions"][0]["presentation_plan"]["mechanism_visual"], "pending")
            self.assertTrue((root / "synthesis" / "paper_payload_v10.json").is_file())
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 11)

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
                "schema_version": 2,
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
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\\n"
                "由守恒关系建立最小费用流模型。\\subsection{验证}\\label{sec:q1-validation}\\n"
                "小规模枚举与网络流结果一致。\\n",
                encoding="utf-8",
            )
            (root / "synthesis" / "model_selection.json").write_text(
                json.dumps({"schema_version": 2, "status": "frozen", "questions": [{"question_id": "Q1", "evidence_profile": "optimization"}]}), encoding="utf-8"
            )
            payload = {
                "schema_version": 2,
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
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\n"
                "\\begin{figure}\\input{figures/q1_geometry.tex}\\caption{视线遮蔽几何关系}"
                "\\label{fig:q1-geometry}\\end{figure}\n"
                "\\subsection{验证}\\label{sec:q1-validation}\n加密计算与解析边界的差异小于 $10^{-4}$ s。\n",
                encoding="utf-8",
            )
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
                    "validation_form": "prose",
                    "validation_anchor": "sec:q1-validation",
                    "validation_takeaway": "边界时刻达到正文显示精度",
                    "mechanism_visual": "required",
                    "mechanism_visual_reason": "遮蔽判据依赖导弹、云团、圆柱和视线的空间关系",
                    "mechanism_visual_must_show": ["导弹—圆柱视线段", "云团球与遮蔽锥"],
                },
                "paper_section": "paper/sections/questions/q01.tex",
                "figures": [],
                "citations": [],
            }
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps({"schema_version": 2, "status": "ready", "questions": [question]}, ensure_ascii=False),
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
                }
            ]
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps({"schema_version": 2, "status": "ready", "questions": [question]}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")

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
                "schema_version": 2,
                "status": "reviewed",
                "policy": {"max_open_major": 1},
                "coverage": [
                    {"question_id": "Q1", "review_type": kind, "status": "pass", "rationale": "independently checked"}
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
            self.assertEqual(check_ai_compliance(root, profile), [])
            (root / "compliance" / "evidence" / "ai-use.txt").write_text("tampered\n", encoding="utf-8")
            self.assertTrue(any("sha256" in item for item in check_ai_compliance(root, profile)))


if __name__ == "__main__":
    unittest.main()
