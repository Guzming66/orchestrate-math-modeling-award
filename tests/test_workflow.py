from __future__ import annotations

import csv
import hashlib
import json
import shutil
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
from package_submission import package_workspace
from validate_innovation_portfolio import validate_innovation_portfolio
from validate_task_board import validate_task_board


class WorkflowTests(unittest.TestCase):
    def initialize(self, root: Path, competition: str = "CUMCM") -> None:
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
                "3",
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

    def complete_innovation_fixture(self, root: Path) -> None:
        candidates: list[dict[str, str]] = []
        for index in range(8):
            candidate_id = f"C{index + 1}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "scout_id": f"S{index % 4 + 1}",
                    "origin_lens": ("mechanism", "uncertainty", "optimization", "cross-domain")[index % 4],
                    "problem_structure": "verified dependency structure",
                    "mechanism_change": f"mechanism change {index + 1}",
                    "innovation_unit": "structure + change + tested gain",
                    "mechanism_family": f"family-{index % 4 + 1}",
                    "mathematical_formulation": "explicit objective and constraints",
                    "baseline": "strong baseline",
                    "cross_domain_source": "inventory control" if index == 0 else "reliability theory" if index == 1 else "",
                    "data_needs": "official input only",
                    "validation_plan": "held-out and edge-case tests",
                    "cheap_falsifier": "small exact fixture",
                    "failure_condition": "no verified gain",
                    "complexity_justification": "one necessary mechanism change",
                    "risk_role": "safe" if index == 0 else "stretch" if index == 1 else "balanced",
                    "status": "survivor" if index < 2 else "rejected",
                    "notes": "fixture",
                }
            )
        self.write_csv_rows(root / "innovation" / "candidate_portfolio.csv", candidates)

        novelty: list[dict[str, str]] = []
        experiments: list[dict[str, str]] = []
        findings: list[dict[str, str]] = []
        selection: list[dict[str, str]] = []
        for index, candidate_id in enumerate(("C1", "C2"), start=1):
            novelty.append(
                {
                    "candidate_id": candidate_id,
                    "claim": "problem-specific mechanism adaptation",
                    "search_queries": "verified query",
                    "primary_sources": "doi:10.0000/example",
                    "nearest_precedent": "verified baseline paper",
                    "difference": "changes the constraint mechanism for this structure",
                    "evidence_locator": "section 3",
                    "novelty_class": "adaptation" if index == 1 else "combination",
                    "metadata_status": "verified",
                    "support_status": "supported",
                    "accessed_at": "2026-08-08T00:00:00Z",
                    "auditor": "tester",
                    "decision": "continue",
                    "notes": "fixture",
                }
            )
            artifact = root / "innovation" / "results" / f"{candidate_id}.txt"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(f"verified experiment {candidate_id}\n", encoding="utf-8")
            experiments.append(
                {
                    "candidate_id": candidate_id,
                    "experiment_id": f"E{index}",
                    "hypothesis": "candidate improves the target mechanism",
                    "baseline": "strong baseline",
                    "dataset_or_fixture": "small exact fixture",
                    "command": "python support/code.py",
                    "seed": "deterministic",
                    "metric": "objective",
                    "baseline_value": "10",
                    "candidate_value": "9",
                    "result_artifact": artifact.relative_to(root).as_posix(),
                    "result_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "status": "verified",
                    "reviewer": "tester",
                    "decision": "pass",
                    "notes": "fixture",
                }
            )
            findings.append(
                {
                    "finding_id": f"F{index}",
                    "candidate_id": candidate_id,
                    "attack_surface": "complexity",
                    "severity": "clear",
                    "finding": "no open blocking issue",
                    "evidence": artifact.relative_to(root).as_posix(),
                    "repair_or_falsifier": "rerun exact fixture",
                    "status": "clear",
                    "reviewer": "tester",
                    "notes": "fixture",
                }
            )
            selection.append(
                {
                    "candidate_id": candidate_id,
                    "rank": str(index),
                    "decision": "promote",
                    "problem_fit": "5",
                    "structural_novelty": "4",
                    "expected_gain": "4",
                    "interpretability": "4",
                    "implementation_feasibility": "4",
                    "data_sufficiency": "5",
                    "validation_strength": "4",
                    "judge_readability": "4",
                    "risks": "bounded fixture risk",
                    "decision_evidence": artifact.relative_to(root).as_posix(),
                    "reviewer": "tester",
                    "notes": "fixture",
                }
            )
        self.write_csv_rows(root / "innovation" / "novelty_audit.csv", novelty)
        extra_artifact = root / "innovation" / "results" / "C3.txt"
        extra_artifact.write_text("verified experiment C3\n", encoding="utf-8")
        experiments.append(
            {
                "candidate_id": "C3",
                "experiment_id": "E3",
                "hypothesis": "third candidate survives a cheap screen",
                "baseline": "strong baseline",
                "dataset_or_fixture": "small exact fixture",
                "command": "python support/code.py",
                "seed": "deterministic",
                "metric": "objective",
                "baseline_value": "10",
                "candidate_value": "9.5",
                "result_artifact": extra_artifact.relative_to(root).as_posix(),
                "result_sha256": hashlib.sha256(extra_artifact.read_bytes()).hexdigest(),
                "status": "verified",
                "reviewer": "tester",
                "decision": "pass",
                "notes": "fixture",
            }
        )
        self.write_csv_rows(root / "innovation" / "feasibility_experiments.csv", experiments)
        self.write_csv_rows(root / "innovation" / "critic_findings.csv", findings)
        self.write_csv_rows(root / "innovation" / "selection.csv", selection)

    def test_initializer_creates_hard_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            required = (
                "audits/gate_status.json",
                "audits/data/data_provenance.csv",
                "audits/reproduction/reproduction_status.json",
                "synthesis/result_manifest.csv",
                "shared/task_board.csv",
                "compliance/anonymity_terms.txt",
                "submission/support_manifest.json",
                "innovation/candidate_portfolio.csv",
                "innovation/novelty_audit.csv",
                "innovation/feasibility_experiments.csv",
                "innovation/critic_findings.csv",
                "innovation/selection.csv",
            )
            for relative in required:
                self.assertTrue((root / relative).is_file(), relative)

    def test_innovation_validator_blocks_empty_and_passes_complete_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.assertEqual(validate_innovation_portfolio(root)["status"], "block")
            self.complete_innovation_fixture(root)
            report = validate_innovation_portfolio(root)
            self.assertEqual(report["status"], "pass", report["errors"])

    def test_task_board_rejects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            board = Path(temp) / "task_board.csv"
            with board.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["task_id", "task_type", "depends_on", "assigned_path", "fallback", "deliverables", "status", "blocking"]
                )
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
            json.dumps({"archive_name": "support.zip", "files": ["support/code.py"]}),
            encoding="utf-8",
        )
        (root / "support" / "code.py").write_text(content, encoding="utf-8")

    def test_packager_blocks_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
            self.package_fixture(root, f"API_KEY = '{fake_key}'\n")
            report = package_workspace(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("key" in item.lower() or "credential" in item.lower() for item in report["errors"]))

    def test_packager_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.package_fixture(root, "print('verified result')\n")
            first = package_workspace(root)
            second = package_workspace(root)
            self.assertEqual(first["status"], "pass")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])

    def test_provenance_rejects_unregistered_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "inputs" / "original" / "problem.txt").write_text("problem", encoding="utf-8")
            errors = check_data_provenance(root)
            self.assertTrue(any("missing from data_provenance" in item for item in errors))

    def test_finalizer_fails_closed_on_unreviewed_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            report = finalize(root)
            self.assertEqual(report["status"], "block")
            self.assertFalse((root / "submission" / "submission_manifest.json").exists())

    def test_cumcm_2026_ai_gate_requires_used_statement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            metadata = root / "paper" / "generated" / "metadata.tex"
            metadata.write_text(metadata.read_text(encoding="utf-8").replace("\\IncludeAIUsageStatementtrue", "\\IncludeAIUsageStatementfalse"), encoding="utf-8")
            errors = check_cumcm_ai_compliance(root, {"competition": "CUMCM", "year": "2026"})
            self.assertTrue(any("AI usage statement" in item for item in errors))

    def test_cumcm_ai_gate_ignores_commented_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            (root / "paper" / "generated" / "metadata.tex").write_text("% \\IncludeAIUsageStatementtrue\n\\IncludeAIUsageStatementfalse\n", encoding="utf-8")
            (root / "paper" / "sections" / "09_ai_statement.tex").write_text("% 本参赛队在竞赛过程中使用了AI工具\n本参赛队在竞赛过程中未使用任何AI工具。\n", encoding="utf-8")
            errors = check_cumcm_ai_compliance(root, {"competition": "CUMCM", "year": "2026"})
            self.assertTrue(any("not enabled" in item for item in errors))
            self.assertTrue(any("truthfully declare" in item for item in errors))

    def test_finalizer_passes_complete_cumcm_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)
            self.complete_innovation_fixture(root)

            problem = root / "inputs" / "original" / "problem.txt"
            problem.write_text("official problem", encoding="utf-8")
            problem_sha = hashlib.sha256(problem.read_bytes()).hexdigest()
            with (root / "audits" / "data" / "data_provenance.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["data_id", "relative_path", "source_type", "source_url", "license_or_terms", "acquired_at", "original_sha256", "current_sha256", "transform_script", "fields_used", "status", "reviewer", "notes"])
                writer.writerow(["problem", "inputs/original/problem.txt", "official_problem", "https://example.invalid/problem", "official contest input", "2026-08-08T00:00:00Z", problem_sha, problem_sha, "", "all", "verified", "tester", "fixture"])

            result_file = root / "results" / "core.txt"
            result_file.parent.mkdir()
            result_file.write_text("42\n", encoding="utf-8")
            result_sha = hashlib.sha256(result_file.read_bytes()).hexdigest()
            with (root / "synthesis" / "result_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["result_id", "claim_location", "value", "unit", "relative_path", "generator", "command", "input_ids", "seed", "environment_file", "sha256", "status", "reviewer", "notes"])
                writer.writerow(["R1", "abstract", "42", "dimensionless", "results/core.txt", "support/code.py", "python support/code.py", "problem", "deterministic", "environment/environment.json", result_sha, "verified", "tester", "fixture"])

            metadata = root / "paper" / "generated" / "metadata.tex"
            metadata.write_text("\\renewcommand{\\PaperTitle}{Verified Modeling Paper}\n\\renewcommand{\\PaperKeywords}{model, validation}\n\\IncludeAIUsageStatementtrue\n", encoding="utf-8")
            for path in (root / "paper").rglob("*.tex"):
                if path == metadata:
                    continue
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace("DRAFT CONTENT", "Verified content."), encoding="utf-8")

            gate_status = {
                "status": "pass",
                "gates": {
                    f"G{index}": {
                        "status": "pass",
                        "reviewer": "tester",
                        "checked_at": "2026-08-08T00:00:00Z",
                        "evidence": ["results/core.txt"],
                        "blocking_findings": [],
                    }
                    for index in range(8)
                },
            }
            (root / "audits" / "gate_status.json").write_text(json.dumps(gate_status), encoding="utf-8")
            (root / "compliance" / "official_sources.json").write_text(
                json.dumps({"competition": "CUMCM", "status": "verified", "last_checked_at": "2026-08-08T00:00:00Z", "verified_by": "tester", "sources": [{"kind": "rules", "url": "https://example.invalid/rules", "version": "fixture", "sha256": "0" * 64}]}),
                encoding="utf-8",
            )
            (root / "audits" / "reproduction" / "reproduction_status.json").write_text(
                json.dumps({"status": "pass", "reviewer": "tester", "checked_at": "2026-08-08T00:00:00Z", "clean_run_command": "python support/code.py", "core_results_reproduced": True, "evidence": ["results/core.txt"], "blocking_findings": []}),
                encoding="utf-8",
            )

            task_board = root / "shared" / "task_board.csv"
            with task_board.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames
                tasks = list(reader)
            self.assertIsNotNone(fieldnames)
            for row in tasks:
                row.update({"owner": "tester", "due_at": "2099-01-01T00:00:00Z", "freeze_at": "2099-01-01T00:00:00Z", "status": "done", "evidence": "results/core.txt"})
            with task_board.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(tasks)

            evidence = root / "synthesis" / "evidence_matrix.csv"
            with evidence.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                evidence_fields = reader.fieldnames
            self.assertIsNotNone(evidence_fields)
            selected = {field: "" for field in evidence_fields}
            selected.update({"branch": "model-a", "decision": "selected", "decision_evidence": "verified fixture", "blocking_findings": ""})
            with evidence.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=evidence_fields)
                writer.writeheader()
                writer.writerow(selected)

            support = root / "support" / "code.py"
            support.parent.mkdir()
            support.write_text("print(42)\n", encoding="utf-8")
            (root / "compliance" / "anonymity_terms.txt").write_text("Test University\nReal Name\n", encoding="utf-8")
            (root / "submission" / "support_manifest.json").write_text(json.dumps({"archive_name": "support.zip", "files": ["support/code.py", "paper/build/AI工具使用详情.pdf"]}), encoding="utf-8")

            report = finalize(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertTrue((root / "submission" / "submission_manifest.json").is_file())
            with zipfile.ZipFile(root / "submission" / "support.zip") as archive:
                self.assertIn("AI工具使用详情.pdf", archive.namelist())

    @unittest.skipUnless(
        all(shutil.which(name) for name in ("latexmk", "xelatex", "pdflatex", "pdfinfo")),
        "LaTeX or PDF tools are unavailable",
    )
    def test_existing_cumcm_and_mcm_templates_compile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for competition in ("CUMCM", "MCM"):
                root = base / competition.lower()
                self.initialize(root, competition)
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "build_latex.py"),
                        str(root / "paper"),
                        "--competition",
                        competition,
                        "--mode",
                        "draft",
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
