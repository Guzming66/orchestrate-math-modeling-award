#!/usr/bin/env python3
"""Validate the sanitized scientific payload and contest-paper presentation firewall."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_latex import INTERNAL_PAPER_PATTERNS, strip_tex_comments
from latex_sources import loaded_tex_sources


FORBIDDEN_KEYS = {
    "artifact_path",
    "sha256",
    "workflow_stage",
    "review_status",
    "claim_status",
    "acceptance_status",
    "audit_path",
    "reproduction_command",
    "task_board",
    "decision_log",
    "freeze_status",
    "command_or_check",
    "verification_command",
    "checked_at",
    "reviewer",
    "finding_id",
    "review_type",
    "severity",
    "task_id",
    "internal_rationale",
}
META_LANGUAGE = tuple(
    (re.compile(pattern, re.IGNORECASE), message)
    for pattern, message in INTERNAL_PAPER_PATTERNS
)
FIGURE_ROLES = {"mechanism", "data", "diagnostic", "decision"}
ROOT_KEYS = {"schema_version", "status", "questions", "notes"}
QUESTION_KEYS = {
    "question_id", "evidence_profile", "problem_summary", "assumptions", "core_model",
    "derivation_summary", "algorithm_summary", "key_results", "comparison_summary",
    "validation_summary", "sensitivity_and_limits", "precision_policy", "complexity_value",
    "presentation_plan", "geometry_claims", "paper_section", "figures", "citations",
}
PRECISION_KEYS = {"display_rule", "justification", "dominant_uncertainty"}
COMPLEXITY_KEYS = {"mode", "added_complexity", "structural_need", "incremental_gain", "decision"}
PRESENTATION_KEYS = {
    "answer_form", "answer_anchor", "answer_takeaway",
    "validation_form", "validation_anchor", "validation_takeaway", "mechanism_visual",
    "mechanism_visual_reason", "mechanism_visual_must_show",
}
FIGURE_KEYS = {"path", "role", "supported_claim", "source_data", "generator", "paper_anchor"}
FIGURE_KEYS |= {
    "claim_anchor", "final_width", "minimum_label_pt", "samples_per_pixel",
    "overplot_handling", "final_size_reviewed",
}
GEOMETRY_CLAIM_KEYS = {
    "claim_anchor", "objects", "relations", "formula_anchor", "figure_anchor",
    "not_needed_reason", "placement", "ten_second_takeaway", "final_size_reviewed",
}
COMPLEXITY_MODES = {"no_extra_complexity", "semantics_required", "incremental_change"}
EVIDENCE_FORMS = {"prose", "equation", "table", "figure"}
MECHANISM_VISUAL_MODES = {"required", "not_applicable"}
GEOMETRY_SIGNAL = re.compile(
    r"空间几何|几何关系|三维空间|方位角|视线|视锥|遮蔽|可见(?:性|区域)|投影|碰撞|相交|坐标系|轨迹"
    r"|line[ -]of[ -]sight|spatial geometry|visibility|occlusion|projection|collision"
    r"|intersection|coordinate system|trajectory",
    re.IGNORECASE,
)


def load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def latex_label_exists(source_text: str, label: str) -> bool:
    return bool(label) and re.search(r"\\label\s*\{\s*" + re.escape(label) + r"\s*\}", source_text) is not None


def latex_reference_exists(source_text: str, label: str) -> bool:
    return bool(label) and re.search(
        r"\\(?:ref|eqref|autoref|cref|Cref)\s*\{\s*" + re.escape(label) + r"\s*\}",
        source_text,
    ) is not None


def figure_caption(source_text: str, label: str) -> str | None:
    body = figure_body(source_text, label)
    if body is not None:
        caption = re.search(r"\\caption(?:\[[^{}]*\])?\{([^{}]+)\}", body, re.DOTALL)
        return re.sub(r"\s+", " ", caption.group(1)).strip() if caption else None
    return None


def figure_body(source_text: str, label: str) -> str | None:
    for match in re.finditer(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", source_text, re.DOTALL):
        if latex_label_exists(match.group(1), label):
            return match.group(1)
    return None


def latex_figure_widths(source_text: str, label: str) -> set[str]:
    body = figure_body(source_text, label)
    if body is None:
        return set()
    widths = set()
    for options in re.findall(r"\\includegraphics\s*\[([^]]*)\]", body, re.DOTALL):
        match = re.search(r"(?:^|,)\s*width\s*=\s*([^,]+)", options)
        if match:
            widths.add(re.sub(r"\s+", "", match.group(1)))
    widths.update(
        re.sub(r"\s+", "", value)
        for value in re.findall(r"\\resizebox\s*\{([^{}]+)\}\s*\{[^{}]*\}", body)
    )
    return widths


def latex_formula_label_exists(source_text: str, label: str) -> bool:
    environments = "equation|align|gather|multline|flalign|alignat"
    return any(
        latex_label_exists(match.group(1), label)
        for match in re.finditer(
            rf"\\begin\{{(?:{environments})\*?\}}(.*?)\\end\{{(?:{environments})\*?\}}",
            source_text,
            re.DOTALL,
        )
    )


def reject_unknown(mapping: dict[str, object], allowed: set[str], location: str, errors: list[str]) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        errors.append(f"{location}: unknown paper-payload keys: {', '.join(sorted(unknown))}")


def walk_payload(value: object, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in FORBIDDEN_KEYS or (normalized_key == "status" and location != "paper_payload"):
                errors.append(f"{location}: forbidden control-plane key in paper payload: {key}")
            walk_payload(nested, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            walk_payload(nested, f"{location}[{index}]", errors)
    elif isinstance(value, str):
        for pattern, message in META_LANGUAGE:
            if pattern.search(value):
                errors.append(f"{location}: {message} leaked into paper payload")


def validate_paper_presentation(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    payload = load(workspace / "synthesis" / "paper_payload.json")
    selection = load(workspace / "synthesis" / "model_selection.json")
    errors: list[str] = []
    warnings: list[str] = []
    paper_root = workspace / "paper"
    loaded_sources = loaded_tex_sources(paper_root)
    paper_source_text = "\n".join(
        strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))
        for path in loaded_sources
    ) if paper_root.is_dir() else ""

    if payload.get("schema_version") != 4:
        errors.append("paper_payload.json schema_version must be 4")
    if payload.get("status") != "ready":
        errors.append("paper payload is not ready")
    ready = payload.get("status") == "ready"
    if selection.get("schema_version") != 2 or selection.get("status") != "frozen":
        errors.append("paper payload requires frozen model_selection.json schema v2")
    reject_unknown(payload, ROOT_KEYS, "paper_payload", errors)
    walk_payload(payload, "paper_payload", errors)

    expected_profiles: dict[str, str] = {}
    selection_questions = selection.get("questions")
    if isinstance(selection_questions, list):
        for item in selection_questions:
            if isinstance(item, dict):
                question_id = str(item.get("question_id", "")).strip()
                if question_id:
                    expected_profiles[question_id] = str(item.get("evidence_profile", "")).strip().lower()

    questions = payload.get("questions")
    if not isinstance(questions, list):
        errors.append("paper_payload.json questions is not an array")
        questions = []
    seen: set[str] = set()
    figure_count = 0
    for index, item in enumerate(questions, start=1):
        label = f"payload[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} is invalid")
            continue
        question_id = str(item.get("question_id", "")).strip()
        if not question_id or question_id in seen:
            errors.append(f"{label}: question_id is empty or duplicated")
            continue
        seen.add(question_id)
        label = question_id
        reject_unknown(item, QUESTION_KEYS, label, errors)
        profile = str(item.get("evidence_profile", "")).strip().lower()
        if expected_profiles.get(question_id) != profile or not profile:
            errors.append(f"{label}: evidence_profile does not match model_selection.json")

        precision = item.get("precision_policy")
        if isinstance(precision, dict):
            reject_unknown(precision, PRECISION_KEYS, f"{label}.precision_policy", errors)
        complexity = item.get("complexity_value")
        if isinstance(complexity, dict):
            reject_unknown(complexity, COMPLEXITY_KEYS, f"{label}.complexity_value", errors)
        presentation = item.get("presentation_plan")
        if isinstance(presentation, dict):
            reject_unknown(presentation, PRESENTATION_KEYS, f"{label}.presentation_plan", errors)
        figures = item.get("figures", [])
        if isinstance(figures, list):
            for figure_index, figure in enumerate(figures, start=1):
                if isinstance(figure, dict):
                    reject_unknown(figure, FIGURE_KEYS, f"{label}/figure[{figure_index}]", errors)
        geometry_claims = item.get("geometry_claims", [])
        if isinstance(geometry_claims, list):
            for claim_index, claim in enumerate(geometry_claims, start=1):
                if isinstance(claim, dict):
                    reject_unknown(claim, GEOMETRY_CLAIM_KEYS, f"{label}/geometry_claim[{claim_index}]", errors)
        if not ready:
            continue

        for field in (
            "problem_summary",
            "core_model",
            "derivation_summary",
            "validation_summary",
            "sensitivity_and_limits",
            "paper_section",
        ):
            if not nonempty(item.get(field)):
                errors.append(f"{label}: {field} is empty")
        if profile != "analytical" and not nonempty(item.get("algorithm_summary")):
            errors.append(f"{label}: algorithm_summary is empty for {profile or 'unknown'} profile")
        if not nonempty(item.get("comparison_summary")):
            warnings.append(f"{label}: comparison_summary is empty; acceptable only when no comparison changes the argument")
        key_results = item.get("key_results")
        if not isinstance(key_results, list) or not key_results or not all(nonempty(value) for value in key_results):
            errors.append(f"{label}: key_results must contain at least one result sentence")
        assumptions = item.get("assumptions")
        if not isinstance(assumptions, list):
            errors.append(f"{label}: assumptions is not an array")

        if not isinstance(precision, dict):
            errors.append(f"{label}: precision_policy is missing")
        else:
            for field in ("display_rule", "justification", "dominant_uncertainty"):
                if not nonempty(precision.get(field)):
                    errors.append(f"{label}: precision_policy.{field} is empty")

        if not isinstance(complexity, dict):
            errors.append(f"{label}: complexity_value is missing")
        else:
            mode = str(complexity.get("mode", "")).strip().lower()
            if mode not in COMPLEXITY_MODES:
                errors.append(f"{label}: complexity_value.mode is invalid")
            for field in ("added_complexity", "structural_need", "decision"):
                if not nonempty(complexity.get(field)):
                    errors.append(f"{label}: complexity_value.{field} is empty")
            gain = complexity.get("incremental_gain")
            if mode == "incremental_change" and not nonempty(gain):
                errors.append(f"{label}: complexity_value.incremental_gain is required for incremental_change")
            elif mode in {"no_extra_complexity", "semantics_required"} and gain is not None and not isinstance(gain, str):
                errors.append(f"{label}: complexity_value.incremental_gain must be text or null")

        visual_mode = ""
        section_visible = ""
        section_rel = str(item.get("paper_section", "")).replace("\\", "/").strip()
        section = (workspace / section_rel).resolve()
        try:
            section.relative_to(workspace / "paper" / "sections")
        except ValueError:
            errors.append(f"{label}: paper_section must stay under paper/sections")
        else:
            if not section.is_file():
                errors.append(f"{label}: paper_section is missing")
            else:
                section_visible = strip_tex_comments(section.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(presentation, dict):
            errors.append(f"{label}: presentation_plan is missing")
        else:
            answer_form = str(presentation.get("answer_form", "")).strip().lower()
            answer_anchor = str(presentation.get("answer_anchor", "")).strip()
            validation_form = str(presentation.get("validation_form", "")).strip().lower()
            validation_anchor = str(presentation.get("validation_anchor", "")).strip()
            visual_mode = str(presentation.get("mechanism_visual", "")).strip().lower()
            if answer_form not in EVIDENCE_FORMS:
                errors.append(f"{label}: presentation_plan.answer_form is invalid")
            if not nonempty(presentation.get("answer_takeaway")):
                errors.append(f"{label}: presentation_plan.answer_takeaway is empty")
            if not answer_anchor:
                errors.append(f"{label}: presentation_plan.answer_anchor is empty")
            elif not latex_label_exists(section_visible, answer_anchor):
                errors.append(f"{label}: answer_anchor is not present in its own question section: {answer_anchor}")
            if validation_form not in EVIDENCE_FORMS:
                errors.append(f"{label}: presentation_plan.validation_form is invalid")
            if not nonempty(presentation.get("validation_takeaway")):
                errors.append(f"{label}: presentation_plan.validation_takeaway is empty")
            if not validation_anchor:
                errors.append(f"{label}: presentation_plan.validation_anchor is empty")
            elif not latex_label_exists(section_visible, validation_anchor):
                errors.append(f"{label}: validation_anchor is not present in its own question section: {validation_anchor}")
            if visual_mode not in MECHANISM_VISUAL_MODES:
                errors.append(f"{label}: presentation_plan.mechanism_visual is invalid")
            if not nonempty(presentation.get("mechanism_visual_reason")):
                errors.append(f"{label}: presentation_plan.mechanism_visual_reason is empty")
            must_show = presentation.get("mechanism_visual_must_show")
            if not isinstance(must_show, list) or not all(nonempty(value) for value in must_show):
                errors.append(f"{label}: presentation_plan.mechanism_visual_must_show is invalid")
                must_show = []
            if visual_mode == "required" and len(must_show) < 2:
                errors.append(f"{label}: a required mechanism visual must name at least two objects or relations to show")
            if visual_mode == "not_applicable" and must_show:
                errors.append(f"{label}: mechanism_visual_must_show must be empty when the visual is not applicable")

        geometry_text = " ".join(
            str(item.get(field, "")) for field in ("problem_summary", "core_model", "derivation_summary")
        )
        geometry_detected = bool(GEOMETRY_SIGNAL.search(geometry_text))

        if not isinstance(figures, list):
            errors.append(f"{label}: figures is not an array")
            figures = []
        mechanism_figure_count = 0
        figure_roles_by_anchor: dict[str, str] = {}
        supported_claims: set[str] = set()
        for figure_index, figure in enumerate(figures, start=1):
            figure_label = f"{label}/figure[{figure_index}]"
            if not isinstance(figure, dict):
                errors.append(f"{figure_label} is invalid")
                continue
            for field in ("path", "role", "supported_claim", "source_data", "generator", "paper_anchor"):
                if not nonempty(figure.get(field)):
                    errors.append(f"{figure_label}: {field} is empty")
            role = str(figure.get("role", "")).strip().lower()
            if role not in FIGURE_ROLES:
                errors.append(f"{figure_label}: invalid evidence role")
            elif role == "mechanism":
                mechanism_figure_count += 1
            claim = re.sub(r"\s+", "", str(figure.get("supported_claim", "")))
            if claim:
                if claim in supported_claims:
                    warnings.append(f"{label}: multiple figures repeat the same supported claim; merge or differentiate them")
                supported_claims.add(claim)
            if re.search(r"效果(?:较为)?良好|精度(?:较)?高|显著(?:提高|提升)|充分证明|鲁棒性强", claim):
                errors.append(f"{figure_label}: supported_claim is promotional or unmeasured")
            generator = str(figure.get("generator", "")).strip().lower()
            if re.search(r"powerpoint|photoshop|截图|手工(?:绘|修)|manual edit", generator):
                errors.append(f"{figure_label}: figure generator is not reproducible")
            if role == "mechanism" and "scipilot" in generator:
                errors.append(f"{figure_label}: SciPilot is for source-backed quantitative figures, not mechanism diagrams")
            paper_anchor = str(figure.get("paper_anchor", "")).strip()
            if paper_anchor:
                figure_roles_by_anchor[paper_anchor] = role
            if paper_anchor and not latex_label_exists(paper_source_text, paper_anchor):
                errors.append(f"{figure_label}: paper_anchor is not present in paper LaTeX: {paper_anchor}")
            elif paper_anchor:
                caption = figure_caption(paper_source_text, paper_anchor)
                if caption is None:
                    errors.append(f"{figure_label}: registered figure has no paper caption")
                elif re.fullmatch(r".{0,8}(?:结果|示意|关系|曲线|分析)图", caption):
                    warnings.append(f"{figure_label}: caption is generic; name the object, condition, or comparison")
                if not latex_reference_exists(paper_source_text, paper_anchor):
                    errors.append(f"{figure_label}: registered figure is never cited with a LaTeX reference")
            figure_rel = str(figure.get("path", "")).replace("\\", "/").strip()
            figure_path = (workspace / figure_rel).resolve()
            try:
                figure_path.relative_to(workspace / "paper" / "figures")
            except ValueError:
                errors.append(f"{figure_label}: path must stay under paper/figures")
            else:
                if not figure_path.is_file():
                    errors.append(f"{figure_label}: figure file is missing")
            final_width = str(figure.get("final_width", "")).strip()
            actual_widths = latex_figure_widths(paper_source_text, paper_anchor)
            if not final_width:
                errors.append(f"{figure_label}: figure final_width is empty")
            elif re.sub(r"\s+", "", final_width) not in actual_widths:
                errors.append(
                    f"{figure_label}: declared final_width is not used by its LaTeX figure: {final_width}"
                )
            minimum_label_pt = figure.get("minimum_label_pt")
            if isinstance(minimum_label_pt, bool) or not isinstance(minimum_label_pt, (int, float)):
                errors.append(f"{figure_label}: minimum_label_pt must be numeric")
            elif minimum_label_pt < 6:
                errors.append(f"{figure_label}: minimum_label_pt must be at least 6 at final LaTeX size")
            if figure.get("final_size_reviewed") is not True:
                errors.append(f"{figure_label}: figure was not reviewed at its final LaTeX size")
            if role in {"data", "diagnostic", "decision"}:
                claim_anchor = str(figure.get("claim_anchor", "")).strip()
                if not claim_anchor:
                    errors.append(f"{figure_label}: quantitative figure claim_anchor is empty")
                elif claim_anchor == paper_anchor:
                    errors.append(f"{figure_label}: quantitative figure claim_anchor must identify the supported paper claim, not the figure itself")
                elif not latex_label_exists(section_visible, claim_anchor):
                    errors.append(f"{figure_label}: quantitative figure claim_anchor is not present in its own question section: {claim_anchor}")
                samples_per_pixel = figure.get("samples_per_pixel")
                if samples_per_pixel is not None and (
                    isinstance(samples_per_pixel, bool) or not isinstance(samples_per_pixel, (int, float)) or samples_per_pixel < 0
                ):
                    errors.append(f"{figure_label}: samples_per_pixel must be a non-negative number or null")
                handling = str(figure.get("overplot_handling", "")).strip()
                if not handling:
                    errors.append(f"{figure_label}: overplot_handling is empty")
                elif isinstance(samples_per_pixel, (int, float)) and not isinstance(samples_per_pixel, bool) and samples_per_pixel > 2:
                    if re.fullmatch(r"(?:none|no|not needed|无需|无|未处理|不处理)[。.]?", handling, re.IGNORECASE):
                        errors.append(f"{figure_label}: more than two samples per pixel requires an overplot-preserving treatment")
            figure_count += 1
        if visual_mode == "required" and mechanism_figure_count == 0:
            errors.append(f"{label}: required mechanism visual is not registered in figures")

        if not isinstance(geometry_claims, list):
            errors.append(f"{label}: geometry_claims is not an array")
            geometry_claims = []
        if (geometry_detected or visual_mode == "required") and not geometry_claims:
            errors.append(f"{label}: geometry reasoning must be mapped to at least one geometry claim")
        seen_claim_anchors: set[str] = set()
        for claim_index, claim in enumerate(geometry_claims, start=1):
            claim_label = f"{label}/geometry_claim[{claim_index}]"
            if not isinstance(claim, dict):
                errors.append(f"{claim_label} is invalid")
                continue
            claim_anchor = str(claim.get("claim_anchor", "")).strip()
            formula_anchor = str(claim.get("formula_anchor", "")).strip()
            figure_anchor_value = claim.get("figure_anchor")
            figure_anchor = str(figure_anchor_value).strip() if isinstance(figure_anchor_value, str) else ""
            reason = claim.get("not_needed_reason")
            objects = claim.get("objects")
            relations = claim.get("relations")
            if not claim_anchor or claim_anchor in seen_claim_anchors:
                errors.append(f"{claim_label}: claim_anchor is empty or duplicated")
            else:
                seen_claim_anchors.add(claim_anchor)
                if not latex_label_exists(section_visible, claim_anchor):
                    errors.append(f"{claim_label}: claim_anchor is not present in its own question section: {claim_anchor}")
            if not formula_anchor or not latex_formula_label_exists(section_visible, formula_anchor):
                errors.append(f"{claim_label}: formula_anchor is not a labeled equation in its own question section: {formula_anchor}")
            if claim_anchor and formula_anchor and claim_anchor == formula_anchor:
                errors.append(f"{claim_label}: claim_anchor and formula_anchor must be distinct")
            if not isinstance(objects, list) or len(objects) < 2 or not all(nonempty(value) for value in objects):
                errors.append(f"{claim_label}: objects must name at least two geometric objects")
            if not isinstance(relations, list) or not relations or not all(nonempty(value) for value in relations):
                errors.append(f"{claim_label}: relations must name at least one geometric relation")
            if bool(figure_anchor) == nonempty(reason):
                errors.append(f"{claim_label}: provide exactly one of figure_anchor or not_needed_reason")
            elif figure_anchor and figure_roles_by_anchor.get(figure_anchor) != "mechanism":
                errors.append(f"{claim_label}: figure_anchor must reference a registered mechanism figure: {figure_anchor}")
            high_visual_load = (
                visual_mode == "required"
                or isinstance(objects, list) and len(objects) >= 3
                or isinstance(relations, list) and len(relations) >= 2
            )
            if high_visual_load and not figure_anchor:
                errors.append(
                    f"{claim_label}: high-load geometry must be discharged by a registered mechanism figure"
                )
            if not nonempty(claim.get("placement")):
                errors.append(f"{claim_label}: placement is empty")
            if not nonempty(claim.get("ten_second_takeaway")):
                errors.append(f"{claim_label}: ten_second_takeaway is empty")
            if claim.get("final_size_reviewed") is not True:
                errors.append(f"{claim_label}: claim was not reviewed for ten-second readability at final LaTeX size")

    if set(expected_profiles) != seen:
        missing = set(expected_profiles) - seen
        extra = seen - set(expected_profiles)
        if missing:
            errors.append(f"paper payload is missing questions: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"paper payload contains unknown questions: {', '.join(sorted(extra))}")

    for path in loaded_sources:
        if "sections" not in path.relative_to(paper_root).parts:
            continue
        visible = strip_tex_comments(path.read_text(encoding="utf-8", errors="replace"))
        for pattern, message in META_LANGUAGE:
            if pattern.search(visible):
                errors.append(f"{message} leaked into final paper: {path.relative_to(workspace)}")

    report = {
        "status": "pass" if not errors else "block",
        "question_count": len(questions),
        "figure_count": figure_count,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    report_path = workspace / "audits" / "presentation" / "paper_presentation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the contest-paper presentation firewall.")
    parser.add_argument("workspace")
    args = parser.parse_args()
    report = validate_paper_presentation(Path(args.workspace).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
