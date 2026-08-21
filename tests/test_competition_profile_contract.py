from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from finalize_submission import submission_build_contract_errors
from validate_competition_profile import validate_competition_profile


STAMP = "2026-08-08T00:00:00+00:00"


class CompetitionProfileContractTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, object]:
        (root / "compliance").mkdir(parents=True)
        (root / "audits" / "rules").mkdir(parents=True)
        (root / "competition_manifest.json").write_text(
            json.dumps({"competition": "CUMCM", "year": 2026}), encoding="utf-8"
        )
        source_path = root / "audits" / "rules" / "official-rules.txt"
        source_path.write_text("Paper format is PDF.\nAI policy checked.\n", encoding="utf-8")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        profile: dict[str, object] = {
            "schema_version": 2,
            "profile_id": "CUMCM-2026-test-v2",
            "competition": "CUMCM",
            "edition": "2026",
            "status": "verified",
            "effective_from": "2026-01-01",
            "effective_to": None,
            "verified_at": STAMP,
            "verified_by": "rule-auditor",
            "sources": [{
                "source_id": "official-rules",
                "kind": "official rules",
                "url": "https://example.invalid/rules",
                "artifact_path": "audits/rules/official-rules.txt",
                "sha256": digest,
                "command_or_check": "manual fixture verification",
                "checked_at": STAMP,
            }],
            "build": {"latex_engine": "xelatex", "main_document": "main.tex"},
            "requirements": {
                "paper": {
                    "format": "pdf",
                    "max_front_matter_pages": None,
                    "max_total_pages": None,
                    "max_body_pages": None,
                    "max_pdf_bytes": None,
                    "page_size": None,
                    "table_of_contents_allowed": None,
                    "anonymous": None,
                },
                "submission": {"support_archive_required": None, "support_archive_max_bytes": None},
                "ai": {
                    "policy_checked": True,
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
            "rule_bindings": [
                {
                    "requirement_pointer": "/requirements/paper/format",
                    "source_id": "official-rules",
                    "locator": "Paper format is PDF.",
                    "evidence_sha256": digest,
                },
                {
                    "requirement_pointer": "/requirements/ai/policy_checked",
                    "source_id": "official-rules",
                    "locator": "AI policy checked.",
                    "evidence_sha256": digest,
                },
            ],
            "notes": "fixture",
        }
        self.write_profile(root, profile)
        return profile

    @staticmethod
    def write_profile(root: Path, profile: dict[str, object]) -> None:
        (root / "compliance" / "competition_profile.json").write_text(
            json.dumps(profile, ensure_ascii=False), encoding="utf-8"
        )

    def test_schema_types_ranges_and_additional_properties_are_strict(self) -> None:
        mutations = (
            lambda profile: profile.update({"unexpected": True}),
            lambda profile: profile["requirements"]["paper"].update({"max_total_pages": "20"}),
            lambda profile: profile["requirements"]["paper"].update({"max_front_matter_pages": -1}),
            lambda profile: profile["requirements"]["paper"].update({"unexpected": True}),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                profile = copy.deepcopy(self.fixture(root))
                mutate(profile)
                self.write_profile(root, profile)
                report = validate_competition_profile(root)
                self.assertEqual(report["status"], "block")
                self.assertTrue(any("schema violation" in error for error in report["errors"]))

    def test_locator_must_exist_in_bound_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.fixture(root)
            self.assertEqual(validate_competition_profile(root)["status"], "pass")
            profile["rule_bindings"][0]["locator"] = "This sentence is absent."
            self.write_profile(root, profile)
            report = validate_competition_profile(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("locator is not present" in error for error in report["errors"]))

    def test_malformed_artifact_path_blocks_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.fixture(root)
            profile["sources"][0]["artifact_path"] = "bad\u0000path"
            self.write_profile(root, profile)
            report = validate_competition_profile(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(report["errors"])
            (root / "compliance" / "competition_profile.json").write_text("{broken", encoding="utf-8")
            self.assertEqual(validate_competition_profile(root)["status"], "block")

    def test_main_document_is_locked_to_paper_main_tex(self) -> None:
        for value in ("../main.tex", "C:/outside/main.tex", "sub/main.tex", "./main.tex"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                profile = self.fixture(root)
                profile["build"]["main_document"] = value
                self.write_profile(root, profile)
                report = validate_competition_profile(root)
                self.assertEqual(report["status"], "block")
                self.assertTrue(any("main_document" in error for error in report["errors"]))

    def test_finalizer_requires_submission_eligible_build_report(self) -> None:
        valid = {"status": "pass", "submission_eligible": True}
        self.assertEqual(submission_build_contract_errors(valid), [])
        for report in ({"status": "pass"}, {"status": "pass", "submission_eligible": False}):
            self.assertTrue(submission_build_contract_errors(report))


if __name__ == "__main__":
    unittest.main()
