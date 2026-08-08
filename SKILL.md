---
name: orchestrate-math-modeling-award
description: "Orchestrate CUMCM/国赛 and MCM/ICM/美赛 with verified rules, an evidence-backed Innovation Claim Engine, reproducible modeling, direct-LaTeX writing, and fail-closed review. Use for contest decomposition, innovation/source/result audits, or final submission; not routine homework."
---

# 数学建模大奖总控

把本 Skill 作为主任务的裁判和总编。使用 `$mathmodel-skill` 管理一般比赛生命周期与状态；由本 Skill 管理官方来源、文献真实性、分支隔离、盲法验证、证据门禁、直接 LaTeX 和最终裁决。本 Skill 的门禁覆盖 `$mathmodel-skill` 中冲突的题号刻板路由与 Markdown/Pandoc 论文装配步骤。

## 按赛事加载资料

识别赛事后再加载相应资料，不要一次读完全部 references。

对于 CUMCM：

- Stage 0 完整读取 [competition-profile.md](references/competition-profile.md) 与 [cumcm-format-and-submission.md](references/cumcm-format-and-submission.md)，访问官方链接并生成当届 profile。
- Stage 1 完整读取 [cumcm-problem-atlas.md](references/cumcm-problem-atlas.md)，按题面信号而不是 A/B/C/D/E 字母选择题型和分支。
- Stage 8 完整读取 [cumcm-excellent-paper-benchmark.md](references/cumcm-excellent-paper-benchmark.md)、[citation-integrity-audit.md](references/citation-integrity-audit.md) 与 [latex-workflow.md](references/latex-workflow.md)。
- Stage 9 再读格式规范、文献真实性审计、[evidence-gates.md](references/evidence-gates.md) 与 [final-submission-controls.md](references/final-submission-controls.md)，不得依赖 Stage 0 的记忆。

对于 MCM/ICM，读取 [competition-profile.md](references/competition-profile.md)、[latex-workflow.md](references/latex-workflow.md)、[task-templates.md](references/task-templates.md) 和 [evidence-gates.md](references/evidence-gates.md)，并重新核对 COMAP 当届规则。

凡准备把外部文献写入论文，在首次落稿前完整读取 [citation-integrity-audit.md](references/citation-integrity-audit.md)。

凡进入 Stage 2–3 的创新方案搜索、跨领域迁移或模型选型，完整读取 [innovation-engine.md](references/innovation-engine.md)。

## 坚持底线

- 把当届官方网站视为规则唯一权威；缓存、往届论文、博客和本 Skill 都不能覆盖当届原文。
- 不虚构数据、文献、实验、评委意见、评分或获奖概率。明确区分官方事实、公开样本观察、计算结果、假设和推测。
- 搜索结果页、聚合摘要、AI 回答和二手转述只能用于发现线索，不能替代原始论文、官方报告、标准或数据文档。
- 把优秀论文用作结构与证据链标杆，不复制其文字、图表、模型命名、代码或当届赛题解法。
- 在分支冻结前保持独立。只共享原题、冻结后的共同数据、统一符号和输出契约，不共享其他分支结论。
- 让人类队员确认建模选择、代码结果、引用、当届明确要求的声明和最终提交。任何 Skill 自评分都不是官方评审分数。

## 启动隔离工作区

1. 识别赛事、年份、题号、截止时间、比赛阶段和现有文件。无法可靠判断时再询问用户。
2. 运行：

   `python scripts/init_competition_workspace.py <工作区> --competition CUMCM --year 2026 --problem A --branches 1 --innovation-mode <fast|standard|championship>`

3. 运行 `python scripts/preflight.py <工作区> --competition <CUMCM|MCM|ICM>`；版本或 CLI 契约不兼容时先修复。Profile 未核验时可以做明确标注为 unverified 的题面结构与基线草探，但不得启动证据晋级、论文主张或最终模型裁决。
4. 将原题和原始附件放入 `inputs/original/`，保留原件和哈希，不覆盖、不重命名原件。
5. 在 `shared/problem_contract.md` 冻结目标、约束、数据字典、评价指标、子问依赖、允许的外部数据和交付要求。
6. 在 `shared/problem_route.md` 记录强基线；只有确有验证价值时才增加模型分支，分支数量不是创新指标。
7. 调用 `$mathmodel-skill` 建立比赛阶段与决策日志，但使用本 Skill 的题面信号路由和 LaTeX 门禁。
8. 完成并验证 `compliance/competition_profile.json`；不得用年份推断规则。

## 按题面信号路由国赛题目

不要把 A 固定为连续、B 固定为评价、C 固定为数据。近年官方题目跨越机理动力学、逆问题、统计判别、组合优化、图网络、视频姿态和风险决策，题号只表示题号。

先建立题面特征卡：

- 输入模态与规模：表格、时序、空间、图、图像/视频、文本或无数据；
- 输出任务：估计、预测、分类、评价、优化、仿真、控制、路径或机制解释；
- 约束结构：连续/离散、确定/随机、静态/动态、单/多目标、是否强物理约束；
- 可验证证据：守恒、已知解、留出数据、小规模精确解、替代求解器、现场常识或专家边界；
- 风险：不可识别、数据泄漏、量纲错误、求解超时、外推和上游误差传播。

先建立一个强基线。只有当替代模型能检验关键假设、解释矛盾或降低失败风险时才增加分支；不要为数量只替换优化器或调参。

## 运行 Innovation Claim Engine

完成题面结构图后、正式建模前，完整执行 [innovation-engine.md](references/innovation-engine.md)：

1. 建立题面结构图和最简单的强基线。
2. 用 artifact-backed 测试证明基线在哪里、为什么失败；没有材料性失败时不制造创新。
3. 从多个 innovation axis 寻找针对 failure 的最小充分改变；类比和多 scout 只是探索工具，数量不足只告警。
4. 使用 `$citation-management` 核对最近先例，以 falsification、创新开/关 ablation 和稳健性证明改变有效。
5. fusion/ensemble/hybrid 只有在组件对应不同 failure、接口明确且逐组件消融通过时才可能成为创新。
6. Critic 先硬否决，Jury 再按 problem fit、evidence、necessity、novelty、robustness、parsimony、communication 排序；允许一个简单主方案胜出。
7. 运行 `validate_innovation_portfolio.py`；写论文后再运行 `validate_paper_innovation.py`。两者都通过才允许宣称创新链完整。

不要硬编码订阅价格或固定模型名；高计算模式只用于结构裁决、强红队和 Jury，并以同题评测决定价值。

## 使用隔离科学环境

运行统计、量纲、不确定性或文献脚本时，优先使用当前比赛工作区的独立 `.venv`；如果不存在就先创建。不要向基础 Anaconda 或系统 Python 环境追加依赖。仅在题目确实需要时安装额外包，并记录解释器路径、Python 版本、包版本与理由。

## 将 LaTeX 设为唯一论文真源

完整读取 [latex-workflow.md](references/latex-workflow.md)：

- 国赛使用 XeLaTeX，美赛使用 pdfLaTeX；通过 `latexmk` 直接编译 `paper/main.tex`。
- 不把 Markdown、Word、HTML 或 Notebook 导出物转换成最终论文，不调用 Pandoc 或 `render_paper.py` 组装正文。
- 只允许论文总编修改 `paper/main.tex`、`paper/generated/metadata.tex` 和 `paper/references.bib`；其他写作任务各自拥有一个 `.tex` 章节。
- 把程序生成的数值宏和表格写入 `paper/generated/*.tex`，图片写入 `paper/figures/`；正文只引用，不手抄结果。
- 每次有意义的修改后运行 `python scripts/build_latex.py <工作区>/paper --competition <CUMCM|MCM|ICM> --mode draft`。
- 草稿阶段继续使用 `build_latex.py`；最终只运行 `python scripts/finalize_submission.py <工作区>`。它统一执行全部门禁、提交模式构建、匿名扫描和支撑包生成。
- 调用本 Skill 或 Codex 即属于使用 AI 工具。声明位置、详情 PDF 和支撑材料要求只从已核验 competition profile 执行；任何赛事都不得选择“未使用 AI”或隐瞒实际使用。

## 拆分独立任务

当用户要求拆题、并行任务或交叉验证时，完整读取 [task-templates.md](references/task-templates.md)，先填写 `shared/task_board.csv` 的依赖、负责人、截止/冻结时间、后备方案、交付物和证据，再委派彼此独立且边界明确的任务。运行 `python scripts/validate_task_board.py <工作区>` 检查未知依赖、环和越序完成；并行写同一文件时停止并重新分配所有权。

要求每个实际创建的建模分支至少交付：题意解释与假设；数学定义、目标与约束；强基线；可运行代码、环境和随机种子；结果生成路径；适配风险的验证与稳健性证据；失败边界；一页内分支摘要。

不要向独立分支泄露预期答案、其他分支结果、优秀论文的具体解法或主任务偏好。

## 执行证据门禁

裁决前完整读取 [evidence-gates.md](references/evidence-gates.md)，把每道门禁的复核人、时间、证据和未关闭问题写入 `audits/gate_status.json`，再依次执行：

1. 规则与提交合规；
2. 文献来源、元数据真实性与论点支持；
3. 数据质量；
4. 分支模型完整性；
5. 统计、量纲与不确定性；
6. 独立验证；有必要时才增加异质模型或替代求解器；
7. 独立复现；
8. 论文、LaTeX、附件和提交。

新增或修改文献时必须调用 `$citation-management`；其他环节需要时调用 `data-analytics:analyze-data-quality`、`$statistical-analysis`、`$uncertainty-and-units` 与 `$scientific-critical-thinking`。把发现标为 `blocking`、`major` 或 `minor`，保存到对应 `audits/` 目录。

## 交叉验证与裁决

冻结分支后再交换结果。在 `synthesis/evidence_matrix.csv` 比较题目贴合度、假设风险、数据支持、相对基线收益、诊断、稳健性、复现性、可解释性、实现风险、论文可表达性和合规风险。

不以多数投票替代证据，不平均不兼容模型。定位矛盾来自数据版本、假设、目标函数、随机性、实现或适用范围。优先选择通过全部阻断门禁、证据链短且可复现的方案；复杂模型只有在稳定、可解释且带来实质收益时胜出。

## 合并论文与交付

- 只从通过门禁的产物写正文，追踪每个核心数字到输入、代码版本和生成步骤。
- 把每个原始/外部输入登记到 `data_provenance.csv`，把每个摘要或结论中的核心数字登记到 `result_manifest.csv`；文件哈希不匹配时不得合并。
- 摘要逐问写“方法 + 可追溯结果 + 验证/边界”，但不机械模仿展示论文段落。
- 统一符号、单位、有效数字、图例和表格口径；明确假设、验证、敏感性、优缺点与适用边界。
- 只合并 `audits/citations/citation_ledger.csv` 中身份、元数据和论点支持均已通过的引用；核心主张保留页码、章节、公式、表格或图号等原文定位。
- 当 verified competition profile 要求时，论文附录列出支撑材料文件并包含完整可运行源程序；支撑压缩包再包含同一版本代码、外部数据和必要中间结果。
- 按当届官方规则完成明确要求的声明或额外材料。

## 统一终审

完整读取 [final-submission-controls.md](references/final-submission-controls.md)。最终只运行：

`python scripts/finalize_submission.py <工作区>`

该命令必须重新快照环境、校验任务依赖、核对官方来源、文献台账、输入与结果哈希、复现状态、证据矩阵和八道门禁，直接编译 LaTeX，并在 profile 要求时从显式清单生成支撑 ZIP、扫描身份/凭据并输出论文与压缩包哈希。只有 `audits/submission/final_report.json` 为 `pass` 时才允许报告“可提交”。

## 使用 Ponytail 的边界

不要在模型选择、验证设计、稳健性或论文证据链阶段调用 Ponytail。仅在方案通过复现后用它清理重复代码或不必要依赖；不得删除基线、诊断、日志、随机种子或审计步骤。

## 停止条件

出现以下任一情况时不得宣称可提交：competition profile 未核验或 source artifact/hash 失配；Innovation Claim Engine 或论文创新审计未通过；创新最近先例未核实；入围 claim 没有 baseline failure、最小改变、证伪/消融或论文落点；任务依赖未关闭；输入、结果或 gate evidence 未登记或哈希不符；核心结果无法独立复现；统计/单位/分支冲突未解释；引用身份或原文支持不成立；匿名、支撑包、LaTeX、逐页检查或最终报告未通过。
