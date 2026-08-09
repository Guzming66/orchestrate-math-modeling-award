# 独立任务契约

## 目录

1. 所有任务的共同规则
2. 国赛规则审计
3. 文献真实性审计
4. 题面信号路由
5. Innovation Claim Engine 独立任务
6. 独立建模分支
7. 数据审计
8. 统计审计
9. 不确定性与量纲审计
10. 独立复现
11. 展示论文标杆审计
12. 红队评委
13. 摘要 30 秒盲审
14. 论文总编
15. LaTeX 与提交包审计

## 所有任务的共同规则

- 只读取 `inputs/original/`、`shared/` 和任务明确允许的目录。
- 只写分配给自己的目录，不修改其他任务或最终论文目录。
- 区分原题事实、外部证据、计算结果、假设和猜测。
- 记录运行环境、依赖版本、随机种子、输入版本和生成命令。
- 开始和完成任务时更新 `shared/task_board.csv`；完成状态必须附交付物路径和证据。
- 不伪造数据、文献、实验、评委意见或获奖概率。
- 不把搜索结果页、聚合摘要、AI 回答或未打开的二手转述作为论文证据。
- 遇到无法验证的信息时标为未知，不用合理化叙述掩盖。
- 不把 Markdown 或 Word 作为最终论文源，不用 Pandoc 转换正文。
- 不向独立任务透露其他分支、主任务偏好或展示论文的具体解法。

## 国赛规则审计

任务说明：只核对当届规则，不参与选题或模型判断。

从全国组委会入口重新核对当届参赛规则、论文格式、报名和参赛须知、赛区补充要求及题面更正。保存官方页面/PDF 快照，记录 URL、访问时间、检查步骤和哈希，填写 versioned competition profile。规则未核实即列为阻断项；不得按年份继承要求。

Profile 未核验时，允许 Structure Mapper 和 Strong Baseline Builder 做明确标注为 `unverified exploratory` 的草探；`innovation-evidence`、claim promotion、正式模型裁决和论文主张必须依赖 `profile-audit` 完成。

## 文献真实性审计

任务说明：使用 `$citation-management` 和 `citation-integrity-audit.md`，不修改模型或为正文措辞辩护。

遍历 `paper/references.bib` 与所有 `.tex` 章节。自动检查 BibTeX、重复项、DOI 和引用键；逐条核对权威题录、正式版本及撤稿/更正状态。对每个核心主张打开原文，记录证据定位、适用范围和支持强度到 `audits/citations/citation_ledger.csv`。文献身份与论点支持必须分别裁决；“文献真实但不支持这句话”仍是阻断项。

## 题面信号路由

任务说明：只读取官方题面和原始附件，不看其他分支。不得按 A/B/C/D/E 字母预设题型。

输出 `shared/problem_route.md`：数学对象、任务动词、约束结构、数据机制、可验证锚点、赛程风险和一个强基线。只在能检验关键假设或降低风险时增加替代路线，并说明必要性；路线数量不是创新指标。

## Innovation Claim Engine 独立任务

完整读取 [innovation-engine.md](innovation-engine.md)，按 Wave 1–4 分配 Structure Mapper、Strong Baseline Builder、Baseline Failure Mapper、axis scouts、可选 Cross-domain Analogist、Literature Auditor、Experimenter、Critic 和 Jury。每个任务只写负责的 artifact；冻结前不读取其他 scout 或主任务偏好。

所有晋级 claim 必须形成 `Structure → Baseline Failure → Minimal Change → Gain → Nearest Precedent/Difference`。Literature Auditor 使用 `$citation-management`；Experimenter 保存 falsification、改变开/关 ablation、命令、种子、artifact 和哈希；Critic/Jury 不得由主张作者兼任。候选数、axis、scout、类比和 safe/stretch 不作硬门禁。

## 独立建模分支

任务说明：独立解决指定子问题。不要读取其他分支的目录或结论，不接受主任务的预设模型。

交付要求：

1. 用自己的话重述问题和评价目标。
2. 列出假设，并说明每项假设如何影响结论。
3. 从一个强基线开始；只有证据需要时才增加主模型组件或替代模型。
4. 给出变量、单位、目标、约束、算法和复杂度。
5. 提供可运行代码、固定随机种子和结果生成步骤。
6. 执行适合该路线的验证、诊断和敏感性分析。
7. 报告失败情形、适用边界和最可能被评委质疑之处。
8. 输出 `branch_summary.md`、`assumptions.csv`、`model_spec.md`、`code/`、`results/` 与 `figures/`。

## 数据审计

任务说明：不评价模型优劣，只检查数据是否值得使用。

检查来源、授权、时间范围、抽样机制、字段含义、单位、重复、缺失、异常、类别失衡、数据泄漏、训练测试污染和外部数据与原题口径差异。逐文件更新 `audits/data/data_provenance.csv` 的来源、条款和 SHA-256；输出修复建议和修复前后影响，不静默删除数据。

## 统计审计

任务说明：使用 `$statistical-analysis` 审核指定分支，不为原作者辩护。

检查样本量、独立性、分布或残差假设、变量选择、共线性、多重比较、效应量、置信/可信区间、交叉验证设计、过拟合和结论措辞。区分统计显著与实际意义。

## 不确定性与量纲审计

任务说明：使用 `$uncertainty-and-units` 审核所有关键输入和输出。

检查量纲闭合、单位换算、测量误差、参数区间、情景边界、误差传播和结果排序的稳定性。优先报告会改变结论方向或排名的不确定性。

## 独立复现

任务说明：假定代码可能存在问题，从干净输出目录重新运行，不修改原代码来“帮助通过”。

运行 `snapshot_environment.py`，从干净目录核对 `result_manifest.csv` 中每个核心表格、图片和摘要数字。执行至少两次随机性检查；把命令、复核人、证据和状态写入 `reproduction_status.json`。将无法运行、数值不一致、隐藏输入和人工中间步骤列为阻断项。

## 展示论文标杆审计

任务说明：使用去题目化结构卡，不评价待审模型是否“像某篇论文”。

按 `cumcm-excellent-paper-benchmark.md` 检查待审稿的证据职责：摘要结果地图、问题依赖、逐问闭环、基线、验证、图表职责、创新必要性、局限和复现。只输出可迁移的结构差距及最小修复，不复制展示论文的句子、图表或模型。

## 红队评委

任务说明：使用 `$scientific-critical-thinking`，以严格评委视角寻找足以降低奖级的问题。

优先攻击题意偏差、不可识别参数、循环论证、因果过度、外推失效、验证泄漏、伪精确、缺少基线和“结论先行”。每项批评必须引用具体产物并给出可验证的修复条件。

## 摘要 30 秒盲审

任务说明：只看最终摘要页和一张问题关系图，不读正文或主任务评价。

在 30 秒阅读目标下写出：任务、逐问方法、三个最重要的数值结论、可信证据和最大边界。无法从页面直接回答的项目标为 `major`；数字与冻结结果不一致、无单位或无法追踪标为 `blocking`。不通过增加算法名和形容词修复。

## 论文总编

任务说明：只使用通过门禁的结果，不重新计算或发明数字。

建立论点—证据—代码—图表追踪表并填写 `synthesis/innovation_claims.csv`；每个 promoted claim 映射到 baseline failure、数学改变、结果 ID、引用键、LaTeX 章节和锚点。只合并通过文献门禁的引用；保留会改变结论的假设、验证、敏感性、局限和当届声明。按实际小题分别写入 `paper/sections/questions/qNN.tex`，不创建大段题面复述、候选路线回顾、内部审计说明、泛化优缺点清单或重复结论。CUMCM 写作完整读取 `cumcm-paper-writing-and-figures.md`。每次合并后直接编译 LaTeX。

## 科研制图审计

任务说明：如已安装则使用 `$scientific-visualization`；否则按 `cumcm-paper-writing-and-figures.md` 直接审计，不改变数据或模型结果。

逐图记录论点职责、源数据、变换、脚本、随机种子、单位、区间定义、输出路径和哈希。检查坐标尺度、缺失值、平滑/归一化、颜色冗余、灰度可辨性、最终栏宽字体、裁切和矢量导出。删除装饰性 3D、重复表格、没有正文引用或不能支持论点的图。只把通过审计的 PDF/PNG 放入 `paper/figures/`。

## LaTeX 与提交包审计

任务说明：不修改论证，只检查 LaTeX 工程和最终 PDF。

从 `paper/main.tex` 运行直接构建，核对文献审计报告、编译报告、未定义引用、重复标签、缺失字体或字符、占位符、超宽公式/表格、浮动体位置，以及 competition profile 指定的页数、纸张、大小、匿名和 PDF 元数据。把 PDF 全部页面渲染为图片，重点检查摘要页、密集公式页、宽表、图组、参考文献和附录。

按已核验 profile 检查电子论文与支撑材料；填写匿名词表和显式支撑清单，运行 `finalize_submission.py`。只有模型选择、创新主张、科学审查、论文、profile 要求的支撑包、所有哈希和匿名/凭据扫描同时通过才允许放行。
