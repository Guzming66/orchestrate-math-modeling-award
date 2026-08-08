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

from finalize_submission import check_cumcm_ai_compliance, check_data_provenance, finalize
from migrate_workspace import migrate
from package_submission import package_workspace
from score_claim_benchmark import score
from validate_competition_profile import validate_competition_profile
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_paper_innovation import validate_paper_innovation
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

    def complete_profile(self, root: Path, competition: str = "CUMCM") -> None:
        source = self.make_artifact(root, "audits/rules/official-rules.html")
        profile = {
            "schema_version": 1,
            "profile_id": f"{competition}-2026-fixture-v1",
            "competition": competition,
            "edition": "2026",
            "status": "verified",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "verified_at": STAMP,
            "verified_by": "independent-rule-auditor",
            "sources": [
                {
                    "kind": "official rules",
                    "url": "https://example.invalid/official-rules",
                    **source,
                }
            ],
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
                    "statement_position": None,
                    "inline_disclosure_required": competition == "CUMCM",
                    "tool_reference_required": competition == "CUMCM",
                    "human_verification_required": competition == "CUMCM",
                    "details_filename": "AI工具使用详情.pdf" if competition == "CUMCM" else None,
                },
            },
        }
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
                "innovation/opportunity_map.md",
                "innovation/claim_portfolio.csv",
                "innovation/claim_experiments.csv",
                "synthesis/innovation_claims.csv",
                "audits/gate_status.json",
            ):
                self.assertTrue((root / relative).is_file(), relative)
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 8)
            self.assertEqual(manifest["branches"], ["model-a"])

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
            for relative in ("innovation", "compliance", "synthesis", "shared", "audits/citations", "audits/data", "audits/reproduction"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "competition_manifest.json").write_text(
                json.dumps({"workflow_version": 7, "competition": "CUMCM", "year": 2026, "branches": ["model-a"]}),
                encoding="utf-8",
            )
            with (root / "innovation" / "candidate_portfolio.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["candidate_id", "scout_id", "origin_lens", "problem_structure", "baseline", "mechanism_change", "status"])
                writer.writeheader()
                writer.writerow({"candidate_id": "OLD1", "scout_id": "S1", "origin_lens": "mechanism", "problem_structure": "network", "baseline": "shortest path", "mechanism_change": "capacity", "status": "survivor"})
            for filename in ("novelty_audit.csv", "critic_findings.csv", "selection.csv"):
                (root / "innovation" / filename).write_text("candidate_id,status\nOLD1,pass\n", encoding="utf-8")
            (root / "audits" / "citations" / "citation_ledger.csv").write_text("citation_key,status\nK1,verified\n", encoding="utf-8")
            (root / "audits" / "data" / "data_provenance.csv").write_text("data_id,status\nD1,verified\n", encoding="utf-8")
            (root / "audits" / "gate_status.json").write_text(json.dumps({"status": "pass", "gates": {}}), encoding="utf-8")
            (root / "audits" / "reproduction" / "reproduction_status.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
            (root / "shared" / "task_board.csv").write_text("task_id,status\nold,done\n", encoding="utf-8")

            report = migrate(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            manifest = json.loads((root / "competition_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow_version"], 8)
            with (root / "innovation" / "claim_portfolio.csv").open(encoding="utf-8-sig") as handle:
                claims = list(csv.DictReader(handle))
            self.assertEqual(claims[0]["claim_id"], "OLD1")
            self.assertEqual(claims[0]["baseline_failure"], "")
            self.assertTrue((root / "innovation" / "legacy_v7" / "selection.csv").is_file())
            self.assertTrue((root / "audits" / "gate_status_v7.json").is_file())
            gates = json.loads((root / "audits" / "gate_status.json").read_text(encoding="utf-8"))
            self.assertEqual(gates["status"], "not_reviewed")

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
                        "blind_quality_score": 4.0,
                    },
                    {
                        "supported_claim_count": 1,
                        "false_innovation_count": 0,
                        "mean_component_count": 1.0,
                        "baseline_gain_coverage": 0.5,
                        "reproducibility_rate": 1.0,
                        "paper_mapping_rate": 1.0,
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

    def test_cumcm_ai_gate_is_profile_driven(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            profile = {
                "competition": "CUMCM",
                "requirements": {
                    "ai": {
                        "usage_statement_required": True,
                        "details_pdf_required": True,
                        "statement_position": "before_references",
                    }
                },
            }
            metadata = root / "paper" / "generated" / "metadata.tex"
            metadata.write_text(
                metadata.read_text(encoding="utf-8").replace("\\IncludeAIUsageStatementtrue", "\\IncludeAIUsageStatementfalse"),
                encoding="utf-8",
            )
            errors = check_cumcm_ai_compliance(root, profile)
            self.assertTrue(any("AI usage statement" in item for item in errors))
            profile["requirements"]["ai"]["usage_statement_required"] = False
            profile["requirements"]["ai"]["details_pdf_required"] = False
            self.assertEqual(check_cumcm_ai_compliance(root, profile), [])

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
            self.assertEqual(check_cumcm_ai_compliance(root, profile), [])
            (root / "compliance" / "evidence" / "ai-use.txt").write_text("tampered\n", encoding="utf-8")
            self.assertTrue(any("sha256" in item for item in check_cumcm_ai_compliance(root, profile)))


if __name__ == "__main__":
    unittest.main()
