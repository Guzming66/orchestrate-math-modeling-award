---
name: orchestrate-math-modeling
description: "Evidence-driven orchestration for CUMCM/国赛 and MCM/ICM/美赛. Use when a contest problem must be decomposed, modeled, validated, written directly in LaTeX, and audited against current official rules. Coordinates question-level model selection, innovation claims, sources, reproducibility, independent scientific review, and final submission. Does not predict or guarantee awards."
---

# 数学建模竞赛总控

本 Skill 是裁决与集成层，不是“自动获奖器”。目标是让规则、模型选择、创新主张、科学结论和提交文件都有可追溯证据，并让最简单的充分方案可以胜出。

## 五个核心系统

1. Competition Rule Engine：只执行当届官方来源支持的 Competition Profile v2。
2. Model Selection Engine：按每个核心小题记录强基线、候选、拟合前理由、拟合后证据、最终选择和淘汰理由。
3. Innovation Claim Engine：从已证明的基线失败出发，验证最小必要改变；模型数量和复杂度不产生创新信用。
4. Scientific Review Engine：独立检查科学有效性、统计有效性和论文主张，统一写入 `audits/review_findings.json`。
5. Submission Finalizer：只执行已经结构化的规则与验证状态，直编 LaTeX、核对哈希、匿名性和要求的提交产物。

历史赛题 benchmark 是离线评估工具，不参与赛中终审，也不输出获奖率。

## 分阶段推进

工作区 `workflow_stage` 依次使用：

`rule_verification → exploration → model_freeze → paper_freeze → submission`

- 规则核验：允许题意解析和标明 `unverified` 的草探，不允许冻结正式结论。
- 探索：先完成强基线，再只为真实 failure 增加候选或创新改动。
- 模型冻结：每个核心小题的 `model_selection.json` 通过后才合并结果。
- 论文冻结：LaTeX 正文、结果、引用和创新表达已经映射。
- 提交：独立审查关闭后，才把 manifest 的阶段改为 `submission` 并运行 finalizer。

不要自动跨阶段。阶段改变是团队决策，记录到 `logs/decision_log.jsonl`。

## 启动工作区

1. 确认赛事、届次、题号、截止时间、原题与附件。
2. 运行：

   `python scripts/init_competition_workspace.py <workspace> --competition CUMCM --year 2026 --problem A --branches 1 --innovation-mode <standard|championship>`

3. 运行 `python scripts/preflight.py <workspace>`。
4. 原题与原始附件放入 `inputs/original/`，保留原文件和哈希。
5. 冻结 `shared/problem_contract.md`：逐小题写目标、输入、输出、约束、评价标准、依赖和统一接口。
6. 当已有 v8 工作区时运行 `python scripts/migrate_workspace.py <workspace>`；迁移会保留旧文件，但重置规则与审查信任。

`standard` 是默认模式；`championship` 只提高独立审查和稳健性要求，不强迫增加模型、Agent 或计算量。

## Competition Profile v2

进入规则核验时完整读取 [competition-profile.md](references/competition-profile.md)。

- 每个可执行 requirement 必须通过 `rule_bindings` 指向 `source_id + locator + evidence_sha256`。
- 官方网页或 PDF 的本地快照、哈希、核验方法和时间必须存在。
- `build` 决定 LaTeX 引擎与主文件；finalizer 不根据赛事名或年份猜测。
- AI 声明、详情文件、支撑包、页数、纸张和文件名都只从 verified profile 执行。
- 官方来源变化、哈希失配或 profile 未核验时停止冻结与提交。

## 按小题选模型

对每个核心小题填写 `synthesis/model_selection.json`：

1. 写清 `problem_structure`，包括目标、数据、约束和验证锚点。
2. 先建立 `strong_baseline_id`；候选数量不设硬指标。
3. 在拟合前写 `pre_fit_rationale`，防止看完结果再编理由。
4. 用真实 artifact 记录指标、诊断和稳健性；基线与入选方案都必须有证据。
5. 写明 `selected_model_id`、`selection_rationale`、复杂度代价和每个未选模型的淘汰理由。
6. 运行 `python scripts/validate_model_selection.py <workspace>`。

不得用无依据的加权总分、TOPSIS 或“最高单项精度”替代结构判断。若复杂模型没有解决新的 failure，选择强基线。

## 验证创新主张

进入探索阶段时完整读取 [innovation-engine.md](references/innovation-engine.md)。核心链条是：

`Problem Structure → Strong Baseline → Baseline Failure → Minimal Change → Evidence → Nearest Precedent → Paper Claim`

- Innovation axis 可以是问题表述、变量表示、机制、分解、目标/约束、推断、求解、数据、验证、决策解释或模型结构。
- fusion/ensemble/hybrid 本身没有创新信用；只有组件针对不同 failure、数学接口明确且逐组件消融通过时才可能成立。
- 候选数、scout 数、跨领域类比和探索宽度只产生 warning。
- 没有材料性基线失败时，可以不提出创新 claim；不得制造“创新”。
- 运行 `validate_innovation_portfolio.py`，写入论文后再运行 `validate_paper_innovation.py`。

## 独立科学审查

在论文冻结前调用 `$scientific-critical-thinking`、`$statistical-analysis` 和 `$uncertainty-and-units`，分别检查：

- scientific：问题表述、假设、机制、边界、因果解释和外推范围；
- statistical：数据泄漏、抽样、估计、区间、诊断、比较公平性和不确定性；
- claims：摘要、正文、图表和结论是否超出结果与文献证据。

统一写入 `audits/review_findings.json`，严重度仅用 `critical / major / minor / suggestion`。critical 和 major 必须有 `artifact_path + sha256 + command_or_check + checked_at`；未关闭 critical 阻断，open major 数不得超过工作区 policy。运行 `validate_review_findings.py`。

## 来源、结果与复现

- 添加或修改文献时必须调用 `$citation-management`，完整执行 [citation-integrity-audit.md](references/citation-integrity-audit.md)。搜索摘要只用于发现，不代替原文。
- `audits/data/data_provenance.csv` 覆盖所有原始与外部输入。
- `synthesis/result_manifest.csv` 覆盖摘要、结论和关键图表中的核心数字，并追踪到输入、命令、环境、单位、随机种子和文件哈希。
- `audits/reproduction/reproduction_status.json` 记录干净重跑命令、独立复核人和证据。
- 不虚构数据、文献、实验、评委意见、评分或获奖概率；明确区分官方事实、计算结果、假设和推测。

## LaTeX 唯一真源

写论文前完整读取 [latex-workflow.md](references/latex-workflow.md)。

- 最终论文只维护 `paper/main.tex`、分章节 `.tex`、`paper/generated/*.tex`、`paper/figures/` 和 `paper/references.bib`。
- 不经 Word、Markdown、HTML、Notebook、Pandoc 或其他格式转换生成最终正文。
- 草稿构建使用 profile 中的 engine：

  `python scripts/build_latex.py <workspace>/paper --engine xelatex --mode draft`

- 程序生成数字与表格，正文只引用，禁止手抄关键结果。

## 总控任务与配套 Skills

使用 `$mathmodel-skill` 管理十阶段比赛生命周期和决策日志；本 Skill 覆盖其中冲突的规则执行、模型选择、证据审计和 LaTeX 终审。

- `$citation-management`：文献身份、元数据、原文支持与 BibTeX。
- `$statistical-analysis`：统计设计、诊断、效应与区间。
- `$uncertainty-and-units`：单位、量纲、误差传播与量级检查。
- `$scientific-critical-thinking`：独立科学审查与主张边界。

拆成小题任务或独立验证任务时完整读取 [task-templates.md](references/task-templates.md)。每个任务只写自己的目录；共享符号、数据版本和接口由总控冻结。不要把预期答案、其他分支结论或优秀论文具体解法泄露给独立验证任务。

## 统一终审

提交前完整读取 [final-submission-controls.md](references/final-submission-controls.md)，将 `workflow_stage` 明确改为 `submission`，然后只运行：

`python scripts/finalize_submission.py <workspace>`

硬阻断仅限会使结论、复现、合规或提交失效的问题：未核验规则、缺少 provenance、核心结果不可复现、模型选择无理由、创新或论文强主张无证据、未关闭 critical/超阈值 major、哈希失配、profile 要求的产物缺失、匿名/凭据问题或 LaTeX 构建失败。探索宽度、模型数量和复杂度不属于硬门禁。

只有 `audits/submission/final_report.json` 为 `pass` 才能报告“技术上可提交”。这不等同于赛事合规的最终法律判断，也不保证任何奖项；由队员复核并完成正式上传。
