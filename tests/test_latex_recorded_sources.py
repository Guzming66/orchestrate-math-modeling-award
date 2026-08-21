from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from build_latex import audit_recorded_tex_sources, compile_paper, fallback_build


class LatexRecordedSourceTests(unittest.TestCase):
    @staticmethod
    def paper_fixture(root: Path) -> tuple[Path, Path]:
        paper = root / "paper"
        build = paper / "build"
        (paper / "sections").mkdir(parents=True)
        build.mkdir()
        (paper / "main.tex").write_text("\\input{sections/visible}\n", encoding="utf-8")
        (paper / "sections" / "visible.tex").write_text("visible\n", encoding="utf-8")
        (paper / "sections" / "hidden.tex").write_text("hidden\n", encoding="utf-8")
        return paper, build

    @staticmethod
    def write_recorder(paper: Path, build: Path, *, hidden: bool = False) -> None:
        inputs = [paper / "main.tex", paper / "sections" / "visible.tex"]
        if hidden:
            inputs.append(paper / "sections" / "hidden.tex")
        outside = paper.parent / "system-package.tex"
        outside.write_text("system\n", encoding="utf-8")
        lines = [f"INPUT {path}" for path in [*inputs, outside, paper / "figure.pdf"]]
        (build / "main.fls").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_matching_recorder_passes_and_ignores_external_tex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper, build = self.paper_fixture(Path(temporary))
            self.write_recorder(paper, build)
            report, errors, warnings = audit_recorded_tex_sources(paper, "main.tex", build, "submission")
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertEqual(report["static_tex_sources"], ["main.tex", "sections/visible.tex"])
            self.assertEqual(report["actual_tex_sources"], ["main.tex", "sections/visible.tex"])
            self.assertEqual(report["extra_tex_sources"], [])

    def test_unscanned_local_input_blocks_submission_and_warns_draft(self) -> None:
        for bypass in ("\\subfile{sections/hidden}", "\\import{sections/}{hidden.tex}"):
            with self.subTest(bypass=bypass), tempfile.TemporaryDirectory() as temporary:
                paper, build = self.paper_fixture(Path(temporary))
                with (paper / "main.tex").open("a", encoding="utf-8") as handle:
                    handle.write(bypass + "\n")
                self.write_recorder(paper, build, hidden=True)
                report, errors, warnings = audit_recorded_tex_sources(paper, "main.tex", build, "submission")
                self.assertEqual(warnings, [])
                self.assertTrue(any("outside the static source closure" in item for item in errors))
                self.assertEqual(report["extra_tex_sources"], ["sections/hidden.tex"])

                _, errors, warnings = audit_recorded_tex_sources(paper, "main.tex", build, "draft")
                self.assertEqual(errors, [])
                self.assertTrue(any("outside the static source closure" in item for item in warnings))

    def test_missing_recorder_blocks_submission_and_warns_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper, build = self.paper_fixture(Path(temporary))
            report, errors, warnings = audit_recorded_tex_sources(paper, "main.tex", build, "submission")
            self.assertFalse(report["recorder_present"])
            self.assertEqual(warnings, [])
            self.assertTrue(any("recorder file is missing" in item for item in errors))

            _, errors, warnings = audit_recorded_tex_sources(paper, "main.tex", build, "draft")
            self.assertEqual(errors, [])
            self.assertTrue(any("recorder file is missing" in item for item in warnings))

    def test_fallback_engine_runs_with_recorder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper, build = self.paper_fixture(Path(temporary))
            completed = subprocess.CompletedProcess([], 0, "")
            with patch("build_latex.run", return_value=completed) as mocked_run:
                result = fallback_build(paper, paper / "main.tex", "xelatex", build)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(mocked_run.call_args_list)
            self.assertTrue(all("-recorder" in call.args[0] for call in mocked_run.call_args_list))

    def test_latexmk_runs_with_recorder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper, build = self.paper_fixture(Path(temporary))
            completed = subprocess.CompletedProcess([], 0, "")
            with patch("build_latex.shutil.which", return_value="latexmk"), patch(
                "build_latex.run", return_value=completed
            ) as mocked_run:
                result = compile_paper(paper, paper / "main.tex", "xelatex", build)
            self.assertEqual(result.returncode, 0)
            self.assertIn("-recorder", mocked_run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
