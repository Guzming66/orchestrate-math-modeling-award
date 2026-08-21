from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from validate_paper_integrity import validate_paper_integrity
from validate_pdf_visual_review import validate_full_paper_page_fill
from validate_review_findings import validate_review_findings


STAMP = "2026-08-08T00:00:00+00:00"


class IntegrityReviewGateTests(unittest.TestCase):
    def artifact(self, root: Path, name: str, content: str) -> dict[str, str]:
        path = root / "audits" / "review" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "artifact_path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "command_or_check": f"inspect {name} against the paper claim",
            "checked_at": STAMP,
        }

    def test_paper_integrity_blocks_repeated_cjk_and_control_plane_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            section = root / "paper" / "sections" / "questions" / "q01.tex"
            section.parent.mkdir(parents=True)
            section.write_text(
                "\\section{问题一}\n龙尾后把手把手的速度列于表中。本小问已经通过总控验收。\n",
                encoding="utf-8",
            )
            report = validate_paper_integrity(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("把手把手" in item for item in report["errors"]))
            self.assertTrue(any("control-plane" in item for item in report["errors"]))

            section.write_text(
                "\\section{问题一}\n龙尾后把手的速度由弦长约束微分得到。\n",
                encoding="utf-8",
            )
            self.assertEqual(validate_paper_integrity(root)["status"], "pass")

    def test_required_review_coverage_is_anchored_specific_and_artifact_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "synthesis").mkdir()
            paper = root / "paper" / "sections" / "questions"
            paper.mkdir(parents=True)
            (paper / "q01.tex").write_text("\\section{问题一}\\label{sec:q1-result}\n结果。\n", encoding="utf-8")
            (paper / "q02.tex").write_text("\\section{问题二}\\label{sec:q2-result}\n结果。\n", encoding="utf-8")
            reviews = {
                "scientific": {"status": "required", "rationale": "route"},
                "statistical": {"status": "not_applicable", "rationale": "route"},
            }
            (root / "synthesis" / "review_route.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "routed",
                        "questions": [
                            {"question_id": "Q1", "reviews": reviews},
                            {"question_id": "Q2", "reviews": reviews},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            common_rationale = "逐项核对守恒约束、边界条件和结论适用范围"
            coverage = [
                {
                    "question_id": "Q1",
                    "review_type": "scientific",
                    "status": "pass",
                    "rationale": common_rationale,
                    "paper_anchor": "sec:q1-result",
                    "concrete_check": "将守恒残差和边界端点逐项代回第一问的直接结论",
                    "falsification_or_boundary_attack": "把边界参数移到可行域两侧并尝试推翻第一问结论",
                    "outcome": "no_material_issue",
                    **self.artifact(root, "q1-scientific.txt", "Q1 boundary attack passed\n"),
                },
                {
                    "question_id": "Q2",
                    "review_type": "scientific",
                    "status": "pass",
                    "rationale": common_rationale,
                    "paper_anchor": "sec:q2-result",
                    "concrete_check": "将事件前后符号和控制对象逐项对照第二问直接答案",
                    "falsification_or_boundary_attack": "搜索更早的局部极小并尝试推翻首次事件结论",
                    "outcome": "no_material_issue",
                    **self.artifact(root, "q2-scientific.txt", "Q2 earlier-event search passed\n"),
                },
                {
                    "question_id": "Q1",
                    "review_type": "statistical",
                    "status": "not_applicable",
                    "rationale": "第一问为确定性解析递推，不含抽样、估计或随机输出",
                },
                {
                    "question_id": "Q2",
                    "review_type": "statistical",
                    "status": "not_applicable",
                    "rationale": "第二问为确定性事件搜索，不包含概率或分布主张",
                },
            ]
            document = {
                "schema_version": 3,
                "status": "reviewed",
                "policy": {"max_accepted_major": 0},
                "coverage": coverage,
                "findings": [],
            }
            review_path = root / "audits" / "review_findings.json"
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            report = validate_review_findings(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("copied coverage rationale" in item for item in report["errors"]))

            coverage[1]["rationale"] = "第二问专门核对首次接触定义、事件顺序和时间边界"
            review_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(validate_review_findings(root)["status"], "pass")

            del coverage[0]["paper_anchor"]
            review_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            report = validate_review_findings(root)
            self.assertEqual(report["status"], "block")
            self.assertTrue(any("paper_anchor is empty" in item for item in report["errors"]))

    def test_full_paper_page_fill_requires_complete_audit_but_defers_sparse_page_judgment(self) -> None:
        digest = "a" * 64
        report = {
            "artifact_class": "full_paper",
            "mode": "submission",
            "sha256": digest,
            "page_text_fill": [],
        }
        errors, fills = validate_full_paper_page_fill(report, 2, digest)
        self.assertEqual(fills, [])
        self.assertTrue(any("empty" in item for item in errors))

        report["page_text_fill"] = [0.85, 0.4]
        self.assertEqual(validate_full_paper_page_fill(report, 2, digest), ([], [0.85, 0.4]))

        report["page_text_fill"] = [0.85, 0.7]
        self.assertEqual(validate_full_paper_page_fill(report, 2, digest), ([], [0.85, 0.7]))


if __name__ == "__main__":
    unittest.main()
