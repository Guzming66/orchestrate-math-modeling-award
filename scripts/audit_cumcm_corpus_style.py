#!/usr/bin/env python3
"""Build auditable per-paper language, structure, and visual-role cards."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


PAGE_ONE = re.compile(r"===== PAGE 1 =====\s*(.*?)(?===== PAGE 2 =====|\Z)", re.DOTALL)
ABSTRACT = re.compile(r"摘要\s*(.*?)(?:关\s*键\s*词|关键词|Key\s*words?)", re.DOTALL | re.IGNORECASE)
QUESTION_MARKER = re.compile(r"针对\s*(?:问(?:题)?|題|向題|回題)?\s*[一二三四五六七八九十1-9]")
NUMERIC_RESULT = re.compile(r"(?:求得|得到|为|达到|降低|提高|误差|准确率|时长).{0,24}\d")
VALIDATION = re.compile(r"验证|检验|误差|敏感(?:性|度)|稳健|鲁棒|对照|比较|复算|收敛|置信")
VAGUE_PRAISE = re.compile(r"效果(?:较为)?良好|精度(?:较)?高|大大提高|显著提升|充分证明|具有.{0,8}(?:鲁棒|稳健|普适|适用)性")
SEQUENCE = re.compile(r"首先|其次|然后|之后|最后")
DIRECT_RESULT = re.compile(r"求得|得到|计算得|结果表明|最终|最大值|最小值|最优(?:值|方案|策略)|可得")
UNIT_RESULT = re.compile(r"\d+(?:[.．]\d+)?\s*(?:%|％|秒|s\b|米|m\b|元|吨|个|次|℃|度|dB|kg|kW|MW)", re.IGNORECASE)
FIRST_PERSON = re.compile(r"本文|本研究|我们")
HEADING_NAMES = re.compile(
    r"摘要|问题(?:重述|分析)|模型(?:假设|建立|求解|检验|验证|评价|评估|推广)|符号(?:说明|约定)"
    r"|数据(?:处理|分析)|结果(?:分析|讨论)?|灵敏度分析|敏感性分析|误差分析|稳健性分析|参考文献|附录"
)
HEADING_PREFIX = re.compile(r"^(?:第?[一二三四五六七八九十\d]+[、.]|\d+(?:[.．]\d+){0,3}\s*)")
CAPTION = re.compile(r"(?:^|\s)(图|表)\s*([0-9]+(?:[-－.．]\s*[0-9]+)?)\s*[:：]?\s*(.{0,60})")
QUESTION_NUMBERS = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
VALIDATION_TERMS = {
    "comparison": re.compile(r"对比|比较|基准|基线|交叉求解|独立复算"),
    "error": re.compile(r"误差|残差|偏差|置信区间"),
    "sensitivity": re.compile(r"灵敏度|敏感性|扰动"),
    "robustness": re.compile(r"稳健|鲁棒|边界测试|极端情形"),
    "convergence": re.compile(r"收敛|步长|网格加密|迭代次数"),
    "ablation": re.compile(r"消融|去除|开关实验"),
}
CAPTION_ROLE_TERMS = {
    "mechanism": re.compile(r"示意|几何|轨迹|关系|流程|框架|网络|坐标|视线|路径|运动|位置|受力|结构"),
    "data": re.compile(r"分布|散点|热力|箱线|相关|原始|数据|频数|直方|聚类"),
    "diagnostic": re.compile(r"拟合|残差|误差|敏感|鲁棒|收敛|对比|比较|验证|置信"),
    "decision": re.compile(r"结果|最优|方案|策略|预测|排名|调度|种植|投放|评价|效率|趋势"),
}

ROLE_LABELS = {
    "data_or_structure": "data",
    "mechanism_or_workflow": "mechanism",
    "diagnostic_or_comparison": "diagnostic",
    "result_or_decision": "decision",
}


def truth(value: str) -> bool:
    return value.strip().lower() == "true"


def integer(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_abstract(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    page_match = PAGE_ONE.search(text)
    page = page_match.group(1) if page_match else text[:8000]
    abstract_match = ABSTRACT.search(page)
    return re.sub(r"\s+", "", abstract_match.group(1) if abstract_match else page)


def read_pages(folder: Path) -> list[str]:
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        combined = (folder / "combined.txt").read_text(encoding="utf-8", errors="replace")
        parts = re.split(r"===== PAGE \d+ =====\s*", combined)
        pages = [part for part in parts[1:] if part.strip()]
        if not pages:
            raise RuntimeError(f"no page markers in fallback OCR text: {folder}")
        return pages
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pages = [
        (folder / "pages" / f"{number:04d}.txt").read_text(encoding="utf-8", errors="replace")
        for number in range(1, int(meta["page_count"]) + 1)
    ]
    if len(pages) != int(meta["page_count"]):
        raise RuntimeError(f"incomplete OCR pages: {folder}")
    return pages


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract_headings(pages: list[str], main_end: int) -> list[dict[str, object]]:
    headings: list[dict[str, object]] = []
    seen: set[str] = set()
    for page_number, text in enumerate(pages[:main_end], 1):
        for line in text.splitlines():
            clean = re.sub(r"\s+", " ", line).strip(" ·•—-_")
            dense = compact(clean)
            if not 2 <= len(dense) <= 42 or len(re.findall(r"[\u3400-\u9fff]", dense)) < 2:
                continue
            named = bool(HEADING_NAMES.search(dense) or re.match(r"^(?:问|问题)[一二三四五六1-6]", dense))
            prefixed_heading = bool(
                HEADING_PREFIX.match(dense)
                and re.search(r"问题|模型|数据|结果|分析|求解|假设|符号|算法|方法|灵敏|敏感|稳健|误差|检验|验证|评价|推广|参考文献|附录", dense)
            )
            if not (named or prefixed_heading):
                continue
            if re.search(r"[=∑∫]|https?://|import\s|\d{4}[-/.]\d{1,2}", clean, re.IGNORECASE):
                continue
            key = re.sub(r"[\s:：，。、.．]", "", clean)
            if key in seen:
                continue
            seen.add(key)
            headings.append({"page": page_number, "title": clean})
    return headings[:100]


def extract_captions(pages: list[str], main_end: int) -> list[dict[str, object]]:
    captions: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for page_number, text in enumerate(pages[:main_end], 1):
        for line in text.splitlines():
            clean = re.sub(r"\s+", " ", line).strip()
            for match in CAPTION.finditer(clean):
                kind, number, title = match.groups()
                number = compact(number)
                title = title.strip(" ·•—-_;；")
                key = kind, number
                if key in seen:
                    continue
                seen.add(key)
                roles = [role for role, pattern in CAPTION_ROLE_TERMS.items() if pattern.search(title)]
                captions.append(
                    {
                        "page": page_number,
                        "kind": kind,
                        "number": number,
                        "title": title[:60],
                        "roles": roles or ["unclassified"],
                    }
                )
    return captions


def question_starts(
    row: dict[str, str], pages: list[str], main_end: int
) -> dict[int, tuple[int, int, int, str]]:
    """Locate the main solution heading for each question, not prompt restatements."""
    expected = integer(row.get("expected_question_count", "0"))
    candidates: dict[int, list[tuple[int, int, int, str]]] = {number: [] for number in range(1, expected + 1)}
    offset = 0
    page_offsets: list[int] = []
    for text in pages[:main_end]:
        page_offsets.append(offset)
        offset += len(text) + 1
    for number in range(1, expected + 1):
        zh = QUESTION_NUMBERS[number]
        pattern = re.compile(rf"(?:问[题題]?|間题|间题|向题|題)(?:{number}|{zh})(?:的)?")
        for page_number, text in enumerate(pages[:main_end], 1):
            local_offset = 0
            for line_number, line in enumerate(text.splitlines(keepends=True), 1):
                clean = re.sub(r"\s+", " ", line).strip(" ·•—-_:：；")
                dense = compact(clean)
                heading_like = bool(HEADING_PREFIX.match(dense)) or len(dense) <= 28
                if 2 <= len(dense) <= 52 and heading_like and pattern.search(dense):
                    if re.search(r"问题(?:重述|要求|提出)|题目要求|需要我们|要求我们", dense):
                        local_offset += len(line)
                        continue
                    score = 0
                    score += 3 if HEADING_PREFIX.match(dense) else 0
                    score += 20 if re.search(r"模型.*(?:建立|求解)|(?:建立|求解).*模型", dense) else 0
                    score += 12 if "求解" in dense else 0
                    score += 10 if "结果" in dense else 0
                    score += 8 if "模型" in dense else 0
                    score += 3 if "分析" in dense else 0
                    if score:
                        candidates[number].append(
                            (score, page_offsets[page_number - 1] + local_offset, page_number, clean)
                        )
                local_offset += len(line)
    starts: dict[int, tuple[int, int, int, str]] = {}
    previous_offset = -1
    for number in range(1, expected + 1):
        eligible = [item for item in candidates[number] if item[1] > previous_offset]
        if not eligible:
            continue
        score, absolute, page_number, heading = sorted(eligible, key=lambda item: (-item[0], item[1]))[0]
        starts[number] = (absolute, page_number, score, heading)
        previous_offset = absolute
    return starts


def question_profiles(
    row: dict[str, str], pages: list[str], main_end: int, captions: list[dict[str, object]]
) -> list[dict[str, object]]:
    starts = question_starts(row, pages, main_end)
    expected = integer(row.get("expected_question_count", "0"))
    profiles: list[dict[str, object]] = []
    full_text = "\n".join(pages[:main_end])
    page_offsets: list[int] = []
    offset = 0
    for page in pages[:main_end]:
        page_offsets.append(offset)
        offset += len(page) + 1
    ordered = sorted((item[0], number) for number, item in starts.items())
    for number in range(1, expected + 1):
        start_info = starts.get(number)
        if start_info is None:
            profiles.append({"question": f"Q{number}", "boundary": "not_detected"})
            continue
        start, start_page, score, heading = start_info
        later = [absolute for absolute, other in ordered if absolute > start and other != number]
        end = min(later) if later else len(full_text)
        text = full_text[start:end]
        end_page = max(index + 1 for index, page_offset in enumerate(page_offsets) if page_offset < end)
        validation = {name: len(pattern.findall(text)) for name, pattern in VALIDATION_TERMS.items()}
        local_caption_matches = list(CAPTION.finditer(text))
        profiles.append(
            {
                "question": f"Q{number}",
                "boundary": f"p{start_page}-p{end_page}",
                "start_heading": heading,
                "heading_confidence_score": score,
                "boundary_confidence": "high" if score >= 20 else "medium" if score >= 8 else "low",
                "chars": len(compact(text)),
                "direct_result_signals": len(DIRECT_RESULT.findall(text)),
                "unit_result_signals": len(UNIT_RESULT.findall(text)),
                "validation": {key: value for key, value in validation.items() if value},
                "figures": sum(match.group(1) == "图" for match in local_caption_matches),
                "tables": sum(match.group(1) == "表" for match in local_caption_matches),
            }
        )
    return profiles


def front_matter(row: dict[str, str]) -> list[str]:
    mapping = {
        "problem_restatement_section": "题面重述",
        "problem_analysis_section": "问题分析",
        "assumptions_section": "模型假设",
        "notation_section": "符号说明",
    }
    return [label for key, label in mapping.items() if truth(row.get(key, ""))]


def abstract_profile(row: dict[str, str], abstract: str) -> str:
    mapped = truth(row.get("abstract_question_mapping_signal", ""))
    numeric = truth(row.get("abstract_numeric_result_signal", ""))
    validation = truth(row.get("abstract_validation_signal", ""))
    if mapped and numeric and validation:
        base = "逐问给出方法、定量答案和验证信号"
    elif mapped and numeric:
        base = "逐问给出方法和定量答案，验证信号较弱"
    elif mapped:
        base = "逐问说明方法，但定量答案不足"
    else:
        base = "未稳定形成逐问答案地图"
    return (
        f"{base}；摘要约{len(abstract)}字，逐问标记{len(QUESTION_MARKER.findall(abstract))}处，"
        f"定量结果句信号{len(NUMERIC_RESULT.findall(abstract))}处"
    )


def structure_profile(row: dict[str, str], front: list[str]) -> str:
    alignment = row.get("question_alignment", "not_detected")
    closure = row.get("per_question_closure_review", "not_detected")
    if alignment == "complete":
        base = "小问标题对齐完整"
    elif alignment == "partial":
        base = "小问标题仅部分对齐"
    else:
        base = "未稳定检出小问标题对齐"
    validation = {
        "broad_signals": "验证分布较广",
        "partial_signals": "验证分布不均",
        "sparse_signals": "验证信号稀疏",
    }.get(row.get("validation_signal_breadth", ""), "验证宽度未定")
    prefix = "、".join(front) if front else "无独立前置章"
    return f"{base}；{validation}；前置章={prefix}；闭环信号={closure}"


def visual_profile(row: dict[str, str]) -> tuple[str, list[str]]:
    roles = [ROLE_LABELS.get(item, item) for item in row.get("figure_table_roles_review", "").split("|") if item]
    figures = integer(row.get("figure_caption_count_main", "0"))
    tables = integer(row.get("table_caption_count_main", "0"))
    role_text = "/".join(roles) if roles else "caption-role-undetected"
    return f"正文图{figures}、表{tables}；证据角色={role_text}", roles


def transferable_move(row: dict[str, str], roles: list[str]) -> str:
    title = row.get("title", "")
    figures = integer(row.get("figure_caption_count_main", "0"))
    tables = integer(row.get("table_caption_count_main", "0"))
    if "mechanism" in roles and re.search(r"几何|定位|角度|轨迹|运动|路径|遮蔽|中板|波浪", title):
        return "在关键公式前用同符号机理/几何图交代对象、方向和判据"
    if "diagnostic" in roles:
        return "把对照、误差或敏感性放在相应结果之后形成局部闭环"
    if "data" in roles and figures >= 10:
        return "用有共同尺度的多面板图展示分组、分布或时序结构"
    if tables > figures:
        return "用紧凑表承载精确方案与参数，正文只解释决定性差异"
    if truth(row.get("abstract_question_mapping_signal", "")):
        return "摘要按小问压缩为任务—方法职责—定量答案"
    return "保留题目特有推导和结果，避免复制固定章节模板"


def caution(row: dict[str, str], abstract: str, front: list[str]) -> str:
    notes: list[str] = []
    if len(front) >= 3:
        notes.append("前置章较重，不应机械照搬")
    if row.get("validation_signal_breadth") == "sparse_signals":
        notes.append("验证稀疏是样本文本特征，不是推荐写法")
    if integer(row.get("figure_caption_count_main", "0")) == 0:
        notes.append("少图不等于无需图，仍应按论证角色判断")
    if integer(row.get("figure_caption_count_main", "0")) >= 25:
        notes.append("图多不产生质量信用，应删除重复图")
    vague = len(VAGUE_PRAISE.findall(abstract))
    if vague:
        notes.append(f"摘要含{vague}处强形容/宣传信号，改写为指标或边界")
    sequence = len(SEQUENCE.findall(abstract))
    if sequence >= 6:
        notes.append("摘要过程连接词偏多，优先写结果关系")
    if not notes:
        notes.append("只迁移信息职责，不复制模型名、句子或版式")
    return "；".join(notes)


def build_cards(cards_path: Path, ocr_root: Path) -> list[dict[str, object]]:
    with cards_path.open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    result: list[dict[str, object]] = []
    for row in source:
        year = row["year"]
        paper_id = row["paper_id"]
        text_path = ocr_root / year / paper_id / "combined.txt"
        if not text_path.is_file():
            raise FileNotFoundError(text_path)
        pages = read_pages(text_path.parent)
        main_end = min(integer(row.get("main_body_end_page", "0")) or len(pages), len(pages))
        body_text = "\n".join(pages[:main_end])
        headings = extract_headings(pages, main_end)
        captions = extract_captions(pages, main_end)
        questions = question_profiles(row, pages, main_end, captions)
        caption_roles: Counter[str] = Counter(
            role for item in captions for role in item["roles"] if role != "unclassified"
        )
        language_signals = {
            "first_person": len(FIRST_PERSON.findall(body_text)),
            "direct_result": len(DIRECT_RESULT.findall(body_text)),
            "unit_result": len(UNIT_RESULT.findall(body_text)),
            "validation": {name: len(pattern.findall(body_text)) for name, pattern in VALIDATION_TERMS.items()},
            "vague_praise": len(VAGUE_PRAISE.findall(body_text)),
            "sequence_words": len(SEQUENCE.findall(body_text)),
        }
        abstract = read_abstract(text_path)
        front = front_matter(row)
        visual, roles = visual_profile(row)
        result.append(
            {
                "year": year,
                "paper_id": paper_id,
                "problem": row.get("problem", ""),
                "title": row.get("title", ""),
                "source_sha256_prefix": row.get("source_sha256", "")[:16],
                "pdf_pages": len(pages),
                "main_body_end_page": main_end,
                "main_body_char_count": len(compact(body_text)),
                "abstract_profile": abstract_profile(row, abstract),
                "structure_profile": structure_profile(row, front),
                "visual_profile": visual,
                "heading_sequence_json": json.dumps(headings, ensure_ascii=False),
                "question_evidence_json": json.dumps(questions, ensure_ascii=False),
                "caption_inventory_json": json.dumps(captions, ensure_ascii=False),
                "caption_role_counts_json": json.dumps(dict(sorted(caption_roles.items())), ensure_ascii=False),
                "generic_caption_count": sum(not str(item["title"]).strip() for item in captions),
                "language_signals_json": json.dumps(language_signals, ensure_ascii=False),
                "transferable_move": transferable_move(row, roles),
                "do_not_copy": caution(row, abstract, front),
                "evidence_scope": "all-page OCR/text audit; visual conclusions require the separately reviewed full-page atlas; exact formulas/numbers require source PDF",
            }
        )
    return result


def write_cards(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    role_counts: Counter[str] = Counter()
    figure_counts: list[int] = []
    table_counts: list[int] = []
    heavy_front_matter = 0
    for row in rows:
        visual = str(row["visual_profile"])
        figures, tables = (int(value) for value in re.findall(r"(?:正文图|表)(\d+)", visual))
        figure_counts.append(figures)
        table_counts.append(tables)
        roles = visual.split("证据角色=", 1)[1].split("/")
        role_counts.update(role for role in roles if role != "caption-role-undetected")
        structure = str(row["structure_profile"])
        front = structure.split("前置章=", 1)[1].split("；", 1)[0]
        if front != "无独立前置章" and len(front.split("、")) >= 3:
            heavy_front_matter += 1
    figure_counts.sort()
    table_counts.sort()
    middle = len(rows) // 2
    return {
        "paper_count": len(rows),
        "year_counts": dict(sorted(Counter(str(row["year"]) for row in rows).items())),
        "figure_caption_range": [figure_counts[0], figure_counts[middle], figure_counts[-1]],
        "table_caption_range": [table_counts[0], table_counts[middle], table_counts[-1]],
        "paper_role_counts": dict(sorted(role_counts.items())),
        "papers_with_three_or_more_front_matter_sections": heavy_front_matter,
        "total_pdf_pages": sum(int(row["pdf_pages"]) for row in rows),
        "total_main_body_pages": sum(int(row["main_body_end_page"]) for row in rows),
        "question_profiles": sum(
            len(json.loads(str(row["question_evidence_json"]))) for row in rows
        ),
        "full_text_audit_status": "complete",
        "visual_review_status": "not represented by this report",
        "evidence_boundary": "descriptive corpus audit; no award-causality inference",
    }


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_deep_report(path: Path, rows: list[dict[str, object]]) -> None:
    """Write one compact, evidence-linked section for every source paper."""
    lines = [
        "# CUMCM 优秀论文逐篇全文审读卡（2022–2025）",
        "",
        "> 证据边界：本报告逐页读取 47 篇论文的 OCR/文本，并按正文边界分析章节、小问候选段、结果、验证与题注。OCR 标题和小问边界只用于审读导航，不能替代对题面与原 PDF 的语义核对。它不复制论文表述，不把高频写法解释为获奖因果；公式与精确数值仍须回看原 PDF。全页视觉审读另有图谱与复核记录。",
        "",
    ]
    for row in rows:
        headings = json.loads(str(row["heading_sequence_json"]))
        questions = json.loads(str(row["question_evidence_json"]))
        captions = json.loads(str(row["caption_inventory_json"]))
        language = json.loads(str(row["language_signals_json"]))
        heading_text = " → ".join(f"p{item['page']} {item['title']}" for item in headings[:20]) or "未稳定检出"
        question_text = "；".join(
            f"{item['question']} 候选边界={item['boundary']}（置信={item.get('boundary_confidence', 'not_detected')}），正文约{item.get('chars', 0)}字，"
            f"结果信号{item.get('direct_result_signals', 0)}、带单位结果{item.get('unit_result_signals', 0)}、"
            f"图{item.get('figures', 0)}/表{item.get('tables', 0)}、验证={compact_json(item.get('validation', {}))}"
            for item in questions
        )
        caption_samples = "；".join(
            f"p{item['page']} {item['kind']}{item['number']} {item['title']} [{'/'.join(item['roles'])}]"
            for item in captions[:16]
        ) or "未稳定检出题注"
        lines.extend(
            [
                f"## {row['year']} {row['paper_id']}｜{row['title']}",
                "",
                f"- 范围：PDF {row['pdf_pages']} 页；正文边界 p1–{row['main_body_end_page']}；正文约 {row['main_body_char_count']} 个非空白字符；源文件哈希前缀 `{row['source_sha256_prefix']}`。",
                f"- 摘要：{row['abstract_profile']}。",
                f"- 章节与闭环：{row['structure_profile']}。",
                f"- OCR 章节候选（前 20 个）：{heading_text}。",
                f"- 逐问候选证据（须与题面语义复核）：{question_text or '未建立逐问边界'}。",
                f"- 图表：{row['visual_profile']}；全文题注角色计数={row['caption_role_counts_json']}；空泛题注{row['generic_caption_count']}个。",
                f"- 题注样本（最多 16 个）：{caption_samples}。",
                f"- 全文语言信号：{compact_json(language)}。",
                f"- 可迁移做法：{row['transferable_move']}。",
                f"- 不应照搬：{row['do_not_copy']}。",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--ocr-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--deep-output", type=Path)
    args = parser.parse_args()
    rows = build_cards(args.cards, args.ocr_root)
    if not rows:
        raise SystemExit("no paper cards found")
    write_cards(args.output, rows)
    report = summarize(rows)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.deep_output:
        write_deep_report(args.deep_output, rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
