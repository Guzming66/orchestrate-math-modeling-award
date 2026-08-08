from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from finalize_submission import check_cumcm_ai_compliance, check_data_provenance, finalize
from package_submission import package_workspace
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
            )
            for relative in required:
                self.assertTrue((root / relative).is_file(), relative)

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

    def test_finalizer_passes_complete_cumcm_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.initialize(root)

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
            (root / "submission" / "support_manifest.json").write_text(json.dumps({"archive_name": "support.zip", "files": ["support/code.py", "paper/build/ai_usage_details.pdf"]}), encoding="utf-8")

            report = finalize(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertTrue((root / "submission" / "submission_manifest.json").is_file())

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
