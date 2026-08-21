from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from validate_paper_presentation import validate_paper_presentation


class PaperVisualContractTests(unittest.TestCase):
    def base_question(self) -> dict[str, object]:
        return {
            "question_id": "Q1",
            "evidence_profile": "deterministic_numerical",
            "problem_summary": "计算运动链与边界的碰撞时刻",
            "assumptions": ["构件按题意视为平面刚体"],
            "core_model": "用有向矩形和分离轴判据描述碰撞",
            "derivation_summary": "由构件轨迹、投影区间和相交关系得到接触裕量",
            "algorithm_summary": "确定性扫描后对首次变号区间二分加密",
            "key_results": ["首次接触发生在给定时刻"],
            "comparison_summary": "与独立顶点边距计算一致",
            "validation_summary": "事件前后裕量异号",
            "sensitivity_and_limits": "结论适用于题面给定的刚体尺寸",
            "precision_policy": {
                "display_rule": "正文报告到 0.01 s",
                "justification": "更高位数小于尺寸扰动影响",
                "dominant_uncertainty": "构件尺寸",
            },
            "complexity_value": {
                "mode": "semantics_required",
                "added_complexity": "完整矩形边界",
                "structural_need": "中心线不能代表实体碰撞",
                "incremental_gain": None,
                "decision": "保留完整矩形判据",
            },
            "paper_section": "paper/sections/questions/q01.tex",
            "citations": [],
        }

    def write_workspace(self, root: Path, *, data_figure: bool = False) -> dict[str, object]:
        section = root / "paper" / "sections" / "questions" / "q01.tex"
        figure_dir = root / "paper" / "figures"
        section.parent.mkdir(parents=True)
        figure_dir.mkdir(parents=True)
        (root / "synthesis").mkdir(parents=True)
        (root / "paper" / "main.tex").write_text(
            "\\input{sections/questions/q01.tex}\n", encoding="utf-8"
        )
        question = self.base_question()
        if data_figure:
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\n"
                "\\subsection{速度峰值}\\label{claim:q1-data}\n"
                "如图~\\ref{fig:q1-data} 所示，局部峰值决定速度上限。\n"
                "\\begin{figure}\\centering\\includegraphics[width=0.84\\linewidth]{figures/q1-data.pdf}"
                "\\caption{全路径速度包络及控制峰值}\\label{fig:q1-data}\\end{figure}\n"
                "\\subsection{结果}\\label{sec:q1-answer}峰值已定位。\n"
                "\\subsection{验证}\\label{sec:q1-validation}局部加密结果稳定。\n",
                encoding="utf-8",
            )
            (figure_dir / "q1-data.pdf").write_bytes(b"%PDF-1.4\n")
            question["problem_summary"] = "计算运动链的全路径速度峰值"
            question["core_model"] = "用速度包络定位控制峰值"
            question["derivation_summary"] = "由链式速度递推得到各把手速度随路径位置的变化"
            question["presentation_plan"] = {
                "answer_form": "prose",
                "answer_anchor": "sec:q1-answer",
                "answer_takeaway": "局部峰值决定速度上限",
                "validation_form": "prose",
                "validation_anchor": "sec:q1-validation",
                "validation_takeaway": "局部加密结果稳定",
                "mechanism_visual": "not_applicable",
                "mechanism_visual_reason": "本图呈现定量结果，不承担空间几何解释",
                "mechanism_visual_must_show": [],
            }
            question["geometry_claims"] = []
            question["figures"] = [{
                "path": "paper/figures/q1-data.pdf",
                "role": "data",
                "supported_claim": "局部峰值而非均匀网格端点决定速度上限",
                "source_data": "全路径逐把手速度结果",
                "generator": "matplotlib",
                "paper_anchor": "fig:q1-data",
                "claim_anchor": "claim:q1-data",
                "final_width": "0.84\\linewidth",
                "minimum_label_pt": 7.5,
                "samples_per_pixel": 3.2,
                "overplot_handling": "按像素列保留最小值和最大值形成包络，局部峰值另行加密",
                "final_size_reviewed": True,
            }]
        else:
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\n"
                "\\subsection{矩形碰撞判据}\\label{claim:q1-geometry}\n"
                "\\begin{equation}G(t)=\\min_{i,j}g_{ij}(t)\\label{eq:q1-gap}\\end{equation}\n"
                "如图~\\ref{fig:q1-geometry} 所示，零投影间隙对应实体接触。\n"
                "\\begin{figure}\\resizebox{0.84\\linewidth}{!}{\\input{figures/q1-geometry.tex}}"
                "\\caption{有向矩形及其分离轴投影关系}\\label{fig:q1-geometry}\\end{figure}\n"
                "\\subsection{结果}\\label{sec:q1-answer}首次接触时刻已定位。\n"
                "\\subsection{验证}\\label{sec:q1-validation}事件前后裕量异号。\n",
                encoding="utf-8",
            )
            (figure_dir / "q1-geometry.tex").write_text("% reproducible TikZ source\n", encoding="utf-8")
            question["presentation_plan"] = {
                "answer_form": "prose",
                "answer_anchor": "sec:q1-answer",
                "answer_takeaway": "首次接触时刻已定位",
                "validation_form": "prose",
                "validation_anchor": "sec:q1-validation",
                "validation_takeaway": "事件前后裕量异号",
                "mechanism_visual": "required",
                "mechanism_visual_reason": "碰撞判据依赖矩形、分离轴和投影区间的几何关系",
                "mechanism_visual_must_show": ["两个有向矩形", "候选分离轴上的投影区间"],
            }
            question["geometry_claims"] = [{
                "claim_anchor": "claim:q1-geometry",
                "objects": ["有向矩形", "候选分离轴"],
                "relations": ["投影区间的零间隙对应首次实体接触"],
                "formula_anchor": "eq:q1-gap",
                "figure_anchor": "fig:q1-geometry",
                "not_needed_reason": None,
                "placement": "判据公式之后、数值结果之前",
                "ten_second_takeaway": "两个矩形在任一候选轴上仍分离即未碰撞，最小间隙为零时接触",
                "final_size_reviewed": True,
            }]
            question["figures"] = [{
                "path": "paper/figures/q1-geometry.tex",
                "role": "mechanism",
                "supported_claim": "分离轴上的零投影间隙对应实体接触",
                "source_data": "题面尺寸与计算得到的构件位置",
                "generator": "TikZ",
                "paper_anchor": "fig:q1-geometry",
                "final_width": "0.84\\linewidth",
                "minimum_label_pt": 7.0,
                "final_size_reviewed": True,
            }]
        (root / "synthesis" / "model_selection.json").write_text(
            json.dumps({
                "schema_version": 2,
                "status": "frozen",
                "questions": [{"question_id": "Q1", "evidence_profile": "deterministic_numerical"}],
            }),
            encoding="utf-8",
        )
        payload = {"schema_version": 4, "status": "ready", "questions": [question]}
        (root / "synthesis" / "paper_payload.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return payload

    def test_geometry_claim_closes_visual_debt_at_final_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = self.write_workspace(root)
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")
            payload["questions"][0]["geometry_claims"][0]["final_size_reviewed"] = False
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            errors = validate_paper_presentation(root)["errors"]
            self.assertTrue(any("ten-second readability at final LaTeX size" in item for item in errors))

    def test_geometry_claim_can_record_specific_no_figure_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = self.write_workspace(root)
            question = payload["questions"][0]
            question["presentation_plan"].update({
                "mechanism_visual": "not_applicable",
                "mechanism_visual_reason": "本判据只有两个投影区间，带符号公式已直接给出全部关系",
                "mechanism_visual_must_show": [],
            })
            claim = question["geometry_claims"][0]
            claim["figure_anchor"] = None
            claim["not_needed_reason"] = "公式紧邻对象定义，且没有遮挡、分支或尺度差需要额外示意"
            question["figures"] = []
            section = root / question["paper_section"]
            section.write_text(
                "\\section{问题一}\\label{sec:q1}\n"
                "\\subsection{矩形碰撞判据}\\label{claim:q1-geometry}\n"
                "\\begin{equation}G(t)=\\min_{i,j}g_{ij}(t)\\label{eq:q1-gap}\\end{equation}\n"
                "\\subsection{结果}\\label{sec:q1-answer}首次接触时刻已定位。\n"
                "\\subsection{验证}\\label{sec:q1-validation}事件前后裕量异号。\n",
                encoding="utf-8",
            )
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")

    def test_data_figure_matches_latex_width_and_preserves_overplotting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = self.write_workspace(root, data_figure=True)
            self.assertEqual(validate_paper_presentation(root)["status"], "pass")
            figure = payload["questions"][0]["figures"][0]
            figure["final_width"] = "0.92\\linewidth"
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertTrue(any("declared final_width" in item for item in validate_paper_presentation(root)["errors"]))
            figure["final_width"] = "0.84\\linewidth"
            figure["overplot_handling"] = "未处理"
            (root / "synthesis" / "paper_payload.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertTrue(any("samples per pixel" in item for item in validate_paper_presentation(root)["errors"]))

    def test_schema_declares_geometry_and_data_figure_contracts(self) -> None:
        schema = json.loads((SKILL / "schemas" / "paper-payload.schema.json").read_text(encoding="utf-8"))
        question = schema["properties"]["questions"]["items"]["properties"]
        self.assertIn("geometry_claims", question)
        figure = question["figures"]["items"]
        data_required = set(figure["allOf"][0]["then"]["required"])
        self.assertTrue({"claim_anchor", "final_width", "minimum_label_pt", "samples_per_pixel", "overplot_handling"} <= data_required)


if __name__ == "__main__":
    unittest.main()
