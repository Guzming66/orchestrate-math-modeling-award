from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from init_competition_workspace import create_workspace
from validate_competition_profile import validate_competition_profile
from validate_task_board import validate_task_board


STAMP = "2026-08-08T00:00:00+00:00"


class EffectivityAndClaimTaskContractTests(unittest.TestCase):
    def initialize(self, root: Path) -> None:
        create_workspace(argparse.Namespace(
            workspace=str(root),
            competition="CUMCM",
            year=2026,
            problem="A",
            branches=2,
            innovation_mode="standard",
        ))

    def verified_profile(self, root: Path) -> dict[str, object]:
        source = root / "audits" / "rules" / "official-rules.txt"
        source.write_text("AI policy checked.\n", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        path = root / "compliance" / "competition_profile.json"
        profile = json.loads(path.read_text(encoding="utf-8"))
        profile.update({
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
            "rule_bindings": [{
                "requirement_pointer": "/requirements/ai/policy_checked",
                "source_id": "official-rules",
                "locator": "AI policy checked.",
                "evidence_sha256": digest,
            }],
        })
        profile["requirements"]["ai"]["policy_checked"] = True
        path.write_text(json.dumps(profile), encoding="utf-8")
        return profile

    @staticmethod
    def write_profile(root: Path, profile: dict[str, object]) -> None:
        (root / "compliance" / "competition_profile.json").write_text(
            json.dumps(profile), encoding="utf-8"
        )

    @staticmethod
    def write_board(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            fields = csv.DictReader(handle).fieldnames
        assert fields is not None
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_verified_profile_requires_ordered_effective_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            self.initialize(root)
            profile = self.verified_profile(root)
            self.assertEqual(validate_competition_profile(root)["status"], "pass")

            for effective_from, effective_to, fragment in (
                ("", None, "effective_from is empty"),
                ("not-a-date", None, "effective_from is not a valid ISO"),
                ("2026-01-02", "2026-01-01", "effective_to precedes effective_from"),
            ):
                with self.subTest(effective_from=effective_from, effective_to=effective_to):
                    profile["status"] = "verified"
                    profile["effective_from"] = effective_from
                    profile["effective_to"] = effective_to
                    self.write_profile(root, profile)
                    report = validate_competition_profile(root)
                    self.assertEqual(report["status"], "block")
                    self.assertTrue(any(fragment in error for error in report["errors"]), report["errors"])

            profile.update({"status": "unverified", "effective_from": "", "effective_to": None})
            self.write_profile(root, profile)
            errors = validate_competition_profile(root)["errors"]
            self.assertFalse(any("effective_from is empty" in error for error in errors))

    def test_initializer_and_validator_split_claim_draft_from_paper_certification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            self.initialize(root)
            board = root / "shared" / "task_board.csv"
            with board.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            tasks = {row["task_id"]: row for row in rows}
            self.assertEqual(tasks["global-claim-draft"]["depends_on"], "model-freeze")
            self.assertEqual(
                set(tasks["global-claim-certification"]["depends_on"].split(";")),
                {"paper", "reproduction", "global-claim-draft"},
            )
            self.assertEqual(validate_task_board(board)["status"], "pass")

            missing_draft = [row for row in rows if row["task_id"] != "global-claim-draft"]
            self.write_board(board, missing_draft)
            report = validate_task_board(board)
            self.assertTrue(any("missing required task IDs" in error for error in report["errors"]))

            tasks["global-claim-draft"]["depends_on"] = ""
            self.write_board(board, rows)
            report = validate_task_board(board)
            self.assertIn("global-claim-draft must depend on model-freeze", report["errors"])

            tasks["global-claim-draft"]["depends_on"] = "model-freeze"
            tasks["global-claim-certification"]["depends_on"] = "paper;global-claim-draft"
            self.write_board(board, rows)
            report = validate_task_board(board)
            self.assertTrue(any("lacks required dependencies: reproduction" in error for error in report["errors"]))

    def test_schema_requires_effectivity_fields(self) -> None:
        schema = json.loads((SKILL / "schemas" / "competition-profile.schema.json").read_text(encoding="utf-8"))
        self.assertTrue({"effective_from", "effective_to"} <= set(schema["required"]))


if __name__ == "__main__":
    unittest.main()
