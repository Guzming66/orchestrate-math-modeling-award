from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from validate_global_claim_certificates import validate_global_claim_certificates


STAMP = "2026-08-21T00:00:00+00:00"


class GlobalClaimCertificateTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, object]:
        (root / "synthesis").mkdir(parents=True)
        (root / "paper" / "sections").mkdir(parents=True)
        (root / "audits" / "evidence").mkdir(parents=True)
        (root / "synthesis" / "model_selection.json").write_text(
            json.dumps({"questions": [{"question_id": "Q5"}]}), encoding="utf-8"
        )
        (root / "paper" / "sections" / "q05.tex").write_text(
            "\\section{问题五}\\label{sec:q5-global-max}\n全域最大速度放大因子为 $M$。\n",
            encoding="utf-8",
        )
        (root / "paper" / "main.tex").write_text(
            "\\input{sections/q05.tex}\n", encoding="utf-8"
        )
        artifact = root / "audits" / "evidence" / "q5-global-search.json"
        artifact.write_text('{"checked_candidates": 42}\n', encoding="utf-8")
        evidence = {
            "evidence_id": "E-Q5-SEARCH",
            "artifact_path": "audits/evidence/q5-global-search.json",
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "command_or_check": "event-partition replay and candidate comparison",
            "checked_at": STAMP,
            "supports": "Endpoint, join-event, and interior candidates were evaluated.",
        }
        check = {
            "status": "pass",
            "summary": "The registered candidate class was evaluated.",
            "evidence_ids": ["E-Q5-SEARCH"],
        }
        return {
            "schema_version": 1,
            "status": "complete",
            "claims": [
                {
                    "claim_id": "GC-Q5-MAX",
                    "question_id": "Q5",
                    "claim_type": "global_maximum",
                    "claim_text": "全域最大速度放大因子为 M",
                    "status": "supported",
                    "locations": [
                        {
                            "source_path": "paper/sections/q05.tex",
                            "locator": "sec:q5-global-max",
                        }
                    ],
                    "domain": {
                        "variables": ["s_0", "handle_index"],
                        "bounds_or_set": "s_0 in [0,S_tail], handle_index in {0,...,223}",
                        "inclusions_exclusions": "Includes both path endpoints and every path join.",
                    },
                    "coverage": {
                        "strategy": "event_partition",
                        "candidate_partition_or_coverage": "Split at every handle crossing of A, J, and B.",
                        "completeness_argument": "Each remaining interval is smooth and searched for stationary points.",
                    },
                    "checks": {
                        "endpoints": dict(check),
                        "nonsmooth": dict(check),
                        "interior": dict(check),
                    },
                    "exclusion_argument": "Every admissible point is an endpoint, join event, or interior point of one partition.",
                    "scope_limitations": "Applies only to the fixed path and rigid-link assumptions.",
                    "evidence": [evidence],
                }
            ],
        }

    def test_complete_artifact_backed_certificate_passes_without_claiming_a_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document), encoding="utf-8"
            )
            report = validate_global_claim_certificates(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertIn("does not prove", report["validation_scope"])

    def test_missing_locator_bad_hash_and_unknown_evidence_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            claim = document["claims"][0]
            claim["locations"][0]["locator"] = "missing-label"
            claim["evidence"][0]["sha256"] = "0" * 64
            claim["checks"]["interior"]["evidence_ids"] = ["MISSING"]
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document), encoding="utf-8"
            )
            report = validate_global_claim_certificates(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("locator is not present" in error for error in report["errors"]))
            self.assertTrue(any("sha256 does not match" in error for error in report["errors"]))
            self.assertTrue(any("unknown evidence_ids" in error for error in report["errors"]))

    def test_not_applicable_requires_an_explicit_rationale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "synthesis").mkdir()
            path = root / "synthesis" / "global_claim_certificates.json"
            path.write_text(
                json.dumps({"schema_version": 1, "status": "not_applicable", "claims": []}),
                encoding="utf-8",
            )
            self.assertEqual(validate_global_claim_certificates(root)["status"], "block")
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "not_applicable",
                        "no_strong_claims_rationale": "No first-event, global, optimal, or full-domain claim is made.",
                        "claims": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(validate_global_claim_certificates(root)["status"], "pass")

    def test_every_strong_claim_occurrence_needs_a_local_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            source = root / "paper" / "sections" / "q05.tex"
            source.write_text(
                source.read_text(encoding="utf-8")
                + "\\subsection{接触事件}\\label{sec:q5-first-contact}\n首次接触发生在 $t_*$。\n",
                encoding="utf-8",
            )
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            report = validate_global_claim_certificates(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("not mapped at these occurrences" in error for error in report["errors"]))
            self.assertEqual(len(report["detected_strong_claim_occurrences"]), 2)
            self.assertEqual(sum(bool(item["mapped"]) for item in report["detected_strong_claim_occurrences"]), 1)

    def test_claim_text_must_match_the_source_near_its_locator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            document["claims"][0]["claim_text"] = "全域最小速度放大因子为 M"
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            errors = validate_global_claim_certificates(root)["errors"]
            self.assertTrue(any("claim_text is not present near locator" in error for error in errors))

    def test_manually_registered_equivalent_wording_does_not_depend_on_the_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            claim_text = "该配置支配所声明参数域内的全部可行候选"
            (root / "paper" / "sections" / "q05.tex").write_text(
                f"\\section{{问题五}}\\label{{sec:q5-global-max}}\n{claim_text}。\n",
                encoding="utf-8",
            )
            document["claims"][0]["claim_text"] = claim_text
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            report = validate_global_claim_certificates(root)
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertEqual(report["detected_strong_claim_occurrences"], [])
            self.assertIn("human inventory", report["detection_scope"])

    def test_common_strong_claim_wording_is_caught_without_broad_method_false_positives(self) -> None:
        strong_phrases = (
            "最优解为方案 A",
            "绝对最大值出现在端点",
            "绝对最小值为 0",
            "全局最优解为方案 B",
            "The global optimal solution is plan C.",
            "The absolute maximum occurs at the endpoint.",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "synthesis").mkdir()
            (root / "paper").mkdir()
            path = root / "synthesis" / "global_claim_certificates.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "not_applicable",
                        "no_strong_claims_rationale": "Human inventory recorded no strong claims.",
                        "claims": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "paper" / "main.tex").write_text("\n".join(strong_phrases), encoding="utf-8")
            report = validate_global_claim_certificates(root)
            self.assertEqual(report["status"], "block")
            self.assertEqual(len(report["detected_strong_claim_occurrences"]), len(strong_phrases))

            (root / "paper" / "main.tex").write_text(
                "本节介绍最优化算法与一个局部最大值。\n",
                encoding="utf-8",
            )
            self.assertEqual(validate_global_claim_certificates(root)["status"], "pass")

    def test_result_location_can_supplement_the_required_paper_occurrence_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            result = root / "results" / "q5-summary.json"
            result.parent.mkdir()
            result.write_text(
                '{"claim_locator":"GC-Q5-MAX","claim":"全域最大速度放大因子为 M"}\n',
                encoding="utf-8",
            )
            document["claims"][0]["locations"].append(
                {"source_path": "results/q5-summary.json", "locator": "GC-Q5-MAX"}
            )
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(validate_global_claim_certificates(root)["status"], "pass")

    def test_discrete_candidate_enumeration_allows_all_three_checks_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            claim = document["claims"][0]
            claim["coverage"] = {
                "strategy": "candidate_enumeration",
                "candidate_partition_or_coverage": "Enumerate every member of the finite admissible set.",
                "completeness_argument": "The candidate table is the full domain, not a sample.",
            }
            claim["checks"] = {
                check_type: {
                    "status": "not_applicable",
                    "summary": "The domain is a finite candidate set with no continuous boundary class.",
                    "evidence_ids": [],
                }
                for check_type in ("endpoints", "nonsmooth", "interior")
            }
            (root / "synthesis" / "global_claim_certificates.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(validate_global_claim_certificates(root)["status"], "pass")

    def test_event_and_continuous_strategies_require_their_routed_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.fixture(root)
            claim = document["claims"][0]
            claim["checks"]["nonsmooth"] = {
                "status": "not_applicable",
                "summary": "No join event was checked.",
                "evidence_ids": [],
            }
            path = root / "synthesis" / "global_claim_certificates.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            errors = validate_global_claim_certificates(root)["errors"]
            self.assertTrue(any("event_partition coverage requires passing checks: nonsmooth" in error for error in errors))

            claim["coverage"]["strategy"] = "bounded_global_search"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(validate_global_claim_certificates(root)["status"], "pass")

            claim["checks"]["interior"] = {
                "status": "not_applicable",
                "summary": "Interior candidates were not checked.",
                "evidence_ids": [],
            }
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            errors = validate_global_claim_certificates(root)["errors"]
            self.assertTrue(any("bounded_global_search coverage requires passing checks: interior" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
