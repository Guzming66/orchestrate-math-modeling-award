---
name: orchestrate-math-modeling
description: "Evidence-driven orchestration for CUMCM/国赛 and MCM/ICM/美赛. Use when a contest problem must be decomposed, modeled, validated, written directly in LaTeX, and audited against current official rules. Coordinates adaptive question-level evidence, innovation claims, sources, reproducibility, contest-paper presentation, independent review, and final submission. Does not predict or guarantee awards."
---

# 数学建模竞赛总控

本 Skill 是裁决与集成层，不是“自动获奖器”。目标是让规则、模型选择、创新主张、科学结论和提交文件都有可追溯证据，并让最简单的充分方案可以胜出。

## 六个核心系统

1. Competition Rule Engine：只执行当届官方来源支持的 Competition Profile v2。
2. Model Selection Engine：按每个核心小题选择 Evidence Profile，记录基准模型、候选、拟合前理由、类型自适应证据、最终选择和淘汰理由。
3. Innovation Claim Engine：允许“题意保真建模”和“基线失败后的最小改变”两条路径；模型数量和复杂度不产生创新信用。
4. Scientific Review Engine：按小题路由科学、实现、统计、不确定性和主张审查，统一写入 `audits/review_findings.json`。
5. Contest Paper Presentation Engine：用 `paper_payload.json` 隔离控制平面与论文正文，控制语言、篇幅、精度和图表信息密度。
6. Submission Finalizer：只执行已经结构化的规则与验证状态，直编 LaTeX、核对哈希、匿名性和要求的提交产物。

历史赛题 benchmark 是离线评估工具，不参与赛中终审，也不输出获奖率。

## 分阶段推进

工作区 `workflow_stage` 依次使用：

`rule_verification → exploration → model_freeze → paper_freeze → submission`

- 规则核验：允许题意解析和标明 `unverified` 的草探，不允许冻结正式结论。
- 探索：先完成强基线，再只为真实 failure 增加候选或创新改动。
- 模型冻结：每个核心小题的 `model_selection.json` 通过后才合并结果。
- 论文冻结：`paper_payload.json`、LaTeX 正文、结果、引用、创新表达和 Presentation Firewall 已经通过。
- 提交：独立审查关闭后，才把 manifest 的阶段改为 `submission` 并运行 finalizer。

不要自动跨阶段。阶段改变是团队决策，记录到 `logs/decision_log.jsonl`。

## 启动工作区

1. 确认赛事、届次、题号、截止时间、原题与附件。
2. 运行：

   `python scripts/init_competition_workspace.py <workspace> --competition CUMCM --year 2026 --problem A --branches 1 --innovation-mode <standard|championship>`

3. 运行 `python scripts/preflight.py <workspace>`。
4. 原题与原始附件放入 `inputs/original/`，保留原文件和哈希。
5. 冻结 `shared/problem_contract.md`：逐小题写目标、输入、输出、约束、评价标准、依赖和统一接口。
6. 当已有 v8–v11 工作区时运行 `python scripts/migrate_workspace.py <workspace>`；迁移保留旧文件，并把论文载荷升级为 v12 的本问直接答案、本问验证与机理图契约。

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
2. 按 [adaptive-review-and-evidence.md](references/adaptive-review-and-evidence.md) 选择 `analytical / deterministic_numerical / optimization / statistical / simulation / machine_learning` Evidence Profile。
3. 先建立 `strong_baseline_id`；候选数量不设硬指标。
4. 在拟合前写 `pre_fit_rationale`，防止看完结果再编理由。
5. 用真实 artifact 完成该 Profile 的 `verification_checks`；不得为了填统计或 robustness 字段制造不适用分析。
6. 写明 `selected_model_id`、`selection_rationale`、复杂度代价和每个未选模型的淘汰理由。
7. 运行 `python scripts/validate_model_selection.py <workspace>`。

不得用无依据的加权总分、TOPSIS 或“最高单项精度”替代结构判断。若复杂模型没有解决新的 failure，选择强基线。

## 验证创新主张

进入探索阶段时完整读取 [innovation-engine.md](references/innovation-engine.md)。核心链条是：

选择一条真实推理路径：

- A：`Problem Semantics → Faithful Formulation → Verification → Simplified Benchmark → Paper Claim`
- B：`Problem Structure → Strong Baseline → Baseline Failure → Minimal Change → Evidence → Nearest Precedent → Paper Claim`

先填写 `innovation/semantic_fidelity_map.md`，再决定采用 A、B 或不提出创新主张；不得默认所有题都属于 B。

- Innovation axis 可以是问题表述、变量表示、机制、分解、目标/约束、推断、求解、数据、验证、决策解释或模型结构。
- fusion/ensemble/hybrid 本身没有创新信用；只有组件针对不同 failure、数学接口明确且逐组件消融通过时才可能成立。
- 候选数、scout 数、跨领域类比和探索宽度只产生 warning。
- 题意已直接规定完整数学对象时，优先按 A 建立保真模型，不得先制造错误简化再叙述成“修复”；新增复杂度仍必须按 B 证明必要性。
- 没有材料性基线失败或可核验的题意保真差异时，可以不提出 innovation claim；不得制造“创新”。
- 创新发现、证据、Critic 和 Jury 是条件式支路，不是模型分支的前置条件；只有要晋级 claim 时才必须闭合整条支路。零 claim 不阻断正常建模，但正文不得使用创新措辞。
- 运行 `validate_innovation_portfolio.py`，写入论文后再运行 `validate_paper_innovation.py`。

## 自适应独立审查

模型冻结后完整读取 [adaptive-review-and-evidence.md](references/adaptive-review-and-evidence.md)，填写并验证 `synthesis/review_route.json`：

- `$scientific-critical-thinking` 始终检查问题表述、假设、机制、边界、因果与外推；
- implementation review 始终检查数学定义、代码实现、变量边界、消元、离散与事件搜索是否一致；
- `$uncertainty-and-units` 始终区分求解器误差、参数敏感性、模型形式、测量与随机不确定性；
- `$statistical-analysis` 只在抽样、估计、预测、分布主张、机器学习或随机模拟需要时调用；确定性分析/几何/优化可内部标记 `not_applicable`，不得因此生成论文解释段；
- claims review 始终检查摘要、正文、图表和结论是否超过结果与文献证据。

运行 `validate_review_route.py`。各问完成后把覆盖与发现写入 schema v2 `audits/review_findings.json`；严重度仅用 `critical / major / minor / suggestion`。critical 和 major 必须有 `artifact_path + sha256 + command_or_check + checked_at`；未关闭 critical 阻断，open major 数不得超过 policy。运行 `validate_review_findings.py`。

## 来源、结果与复现

- 添加或修改文献时必须调用 `$citation-management`，完整执行 [citation-integrity-audit.md](references/citation-integrity-audit.md)。搜索摘要只用于发现，不代替原文。
- `audits/data/data_provenance.csv` 覆盖所有原始与外部输入。
- `synthesis/result_manifest.csv` 覆盖摘要、结论和关键图表中的核心数字，并追踪到输入、命令、环境、单位、随机种子和文件哈希。
- `audits/reproduction/reproduction_status.json` 记录干净重跑命令、独立复核人和证据。
- 不虚构数据、文献、实验、评委意见、评分或获奖概率；明确区分官方事实、计算结果、假设和推测。

## 竞赛论文表达防火墙

写论文前完整读取 [paper-presentation-engine.md](references/paper-presentation-engine.md)。Control Plane、Scientific Solution Plane 和 Contest Paper Plane 单向隔离：

- 模型冻结后生成 schema v3 `synthesis/paper_payload.json`；论文手以它为主要科学输入，只在核对事实时读取结果或引用台账。
- Payload 和正文不得出现 workflow stage、freeze/验收、hash、audit/review status、claim status、downstream interface、reproduction bookkeeping 或“不虚构置信区间/不提出创新”等否定性元话语。
- 把内部概念翻译为竞赛原生语言：strong baseline → 基准/简化模型；baseline failure → 简化模型的具体局限；artifact-backed evidence → 数值/实验/推导结果。
- 每段必须贡献于模型、推导、算法、结果、比较、验证、敏感性、局限或决策；内部状态段默认删除。
- 每问先形成“主张—最短充分证据—最佳载体”表，再写正文；不按页数、图数或表数扩写，模型、结果或验证标题下没有实际内容时不得放行。
- 正文数值精度由输入、参数、模型形式和显示需求决定，不展示远小于材料性不确定性的求解器位数。
- 每问填写 `presentation_plan`：用 `answer_form / answer_anchor / answer_takeaway` 登记最短直接答案，用 `validation_form / validation_anchor / validation_takeaway` 登记最强验证；两个锚点都必须位于本问 `qNN.tex`，不得借用附录、全局章节或另一问的标签。不得只写“已独立复算/已有证书”而不给评委可核验的比较、误差或边界。
- 当问题依赖空间几何、视线、遮蔽、可见性、投影、碰撞、坐标系或轨迹关系时，至少登记一幅 `role=mechanism` 的直观图，列出必须同时出现的对象与关系。几何图使用可复现 TikZ、Matplotlib 3D、Graphviz 或原生代码，不交给 SciPilot；非几何问题可写明 `not_applicable` 理由。
- 每幅登记图必须具有信息性题注、可复现图源、明确支持的论文主张，并在正文用 `\ref`/`\autoref`/`\cref` 编号引用；PowerPoint、截图、手工 P 图或让 SciPilot 生成机理示意图均不放行。尺度差异明显的几何问题优先用“全局场景 + 局部判据”双面板。
- 运行 `python scripts/validate_paper_presentation.py <workspace>`。

内部审计继续保留全部精度、命令和哈希；防火墙只约束论文表达，不降低证据标准。

## LaTeX 唯一真源

写论文前完整读取 [latex-workflow.md](references/latex-workflow.md)；CUMCM 中文论文同时完整读取 [cumcm-paper-writing-and-figures.md](references/cumcm-paper-writing-and-figures.md) 与其证据底稿 [cumcm-corpus-evidence-2022-2025.md](references/cumcm-corpus-evidence-2022-2025.md)。需要核对逐篇差异时读取 [cumcm-paper-style-cards-2022-2025.csv](references/cumcm-paper-style-cards-2022-2025.csv) 与 [cumcm-paper-deep-reading-2022-2025.md](references/cumcm-paper-deep-reading-2022-2025.md)；全页视觉结论以 [cumcm-full-visual-review-summary-2022-2025.json](references/cumcm-full-visual-review-summary-2022-2025.json) 为边界。只迁移信息职责，不复制句子、模型、数值或版式。

- 最终论文只维护 `paper/main.tex`、分章节 `.tex`、`paper/generated/*.tex`、`paper/figures/` 和 `paper/references.bib`。
- 不经 Word、Markdown、HTML、Notebook、Pandoc 或其他格式转换生成最终正文。
- 不把题面复述、候选池、Agent 分工、内部评分、artifact 路径、哈希、调试过程或泛化优缺点套话写入最终论文；这些内容留在审计与复现台账。
- 先逐项核对题面小问契约，再按实际小题建立独立 `.tex` 文件；`Qn` 必须对应 `qNN.tex`。每问就地完成“任务与依赖—模型—结果—验证/边界—后续问题沿用的判据或参数”，并核对题目要求的表格与结果文件；只在跨问风险确实存在时单列全局稳健性章节。正文必须脱离代码/数据附录仍能独立回答全部小问。
- 草稿构建使用 profile 中的 engine：

  `python scripts/build_latex.py <workspace>/paper --engine xelatex --mode draft`

  草稿构建始终标记为 `review_only`；存在占位符时必须向队员报告警告，不得把 `main.pdf` 称为最终稿。只有 submission-mode 构建和统一 Finalizer 全部通过后才可称为提交候选。

- 独立小问 PDF 也必须走同一构建器：

  `python scripts/build_latex.py <branch>/paper --engine xelatex --main qNN_standalone.tex --mode submission`

  禁止把裸 `xelatex` 产物交给队员。独立稿只有 `build_report_qNN_standalone.json` 为 `pass`、`handoff_eligible=true` 且哈希匹配时才可称为“小问交付候选”；它永远不是赛事提交候选。构建器会检查竞赛语言、任务—模型—结果—验证职责、验证锚点、比较性验证的可见表/图和末页大面积空白。不要用页数或套话填充；缺少的是推导、比较、验证或边界时，补对应证据。

- 程序生成数字与表格，正文只引用，禁止手抄关键结果。

## 总控任务与配套 Skills

使用 `$mathmodel-skill` 管理十阶段比赛生命周期和决策日志；本 Skill 覆盖其中冲突的规则执行、模型选择、证据审计和 LaTeX 终审。

- `$citation-management`：文献身份、元数据、原文支持与 BibTeX。
- `$statistical-analysis`：只按 Review Router 处理确有随机数据、估计、预测或分布主张的小题。
- `$uncertainty-and-units`：单位、量纲、误差传播与量级检查。
- `$scientific-critical-thinking`：独立科学审查与主张边界。
- `$scipilot-figure-skill`：优先处理有源数据的量化科研图。先确定论证目标并剖析数据，再选图、按最终尺寸绘制、运行程序自检与 AI 读图闭环，最后导出矢量 PDF；它不处理示意图、流程图或架构图。若其目录含 `.venv/Scripts/python.exe`，所有 SciPilot 脚本统一使用该解释器，避免污染或误用全局 Python。
- `$data-analytics:visualize-data`：用于图表契约、交互探索、通用可视化设计和第二视角 QA；不能替代 SciPilot 的数据剖析与成图闭环。
- 机理、几何、流程、网络或算法示意图使用可复现 TikZ/Graphviz/原生代码；不得为了调用 SciPilot 把概念图伪装成数据图。SciPilot 不可用时，按同一证据与成图契约直接使用 Matplotlib/Seaborn。

拆成小题任务或独立验证任务时完整读取 [task-templates.md](references/task-templates.md)。每个任务只写自己的目录；共享符号、数据版本和接口由总控冻结。不要把预期答案、其他分支结论或优秀论文具体解法泄露给独立验证任务。

## 统一终审

提交前完整读取 [final-submission-controls.md](references/final-submission-controls.md)，将 `workflow_stage` 明确改为 `submission`，然后只运行：

`python scripts/finalize_submission.py <workspace>`

硬阻断仅限会使结论、复现、表达、合规或提交失效的问题：未核验规则、缺少 provenance、核心结果不可复现、Evidence Profile/Review Router 不完整、数学定义与实现不一致、模型选择无理由、创新或论文强主张无证据、题面小问与 `qNN.tex` 错配、本问没有直接答案或最强验证锚点、几何推理缺少机理图、Paper Payload/表达防火墙失败、占位符或仅标题章节、未关闭 critical/超阈值 major、哈希失配、profile 要求的产物缺失、匿名/凭据问题或 LaTeX 构建失败。探索宽度、模型数量和复杂度不属于硬门禁。

只有 `audits/submission/final_report.json` 为 `pass` 才能报告“技术上可提交”。这不等同于赛事合规的最终法律判断，也不保证任何奖项；由队员复核并完成正式上传。
