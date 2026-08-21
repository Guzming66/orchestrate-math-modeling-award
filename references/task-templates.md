# 独立任务契约

## 目录

1. 所有任务的共同规则
2. 国赛规则审计
3. 文献真实性审计
4. 题面信号路由
5. Innovation Claim Engine 独立任务
6. 独立建模分支
7. 数据审计
8. 自适应审查路由
9. 强全域主张证书
10. 统计审计
11. 不确定性与量纲审计
12. 独立复现
13. 展示论文标杆审计
14. 红队评委
15. 摘要 30 秒盲审
16. 论文总编
17. 科研制图审计
18. LaTeX 与提交包审计

## 所有任务的共同规则

- 只读取 `inputs/original/`、`shared/` 和任务明确允许的目录。
- 只写分配给自己的目录，不修改其他任务或最终论文目录。
- 区分原题事实、外部证据、计算结果、假设和猜测。
- 记录运行环境、依赖版本、随机种子、输入版本和生成命令。
- 开始和完成任务时更新 `shared/task_board.csv`；`blocking` 只写 `true` 或 `false`，保留 workflow v15 的核心 task IDs，模型任务 ID 可按分支动态命名；完成状态必须附交付物路径和证据。
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

先逐字对照题面填写 `shared/problem_contract.json`：为原题文件登记 SHA-256，为每个 `Qn` 记录题面定位、任务动词、必须交付的答案/文件、输入、结构化上游依赖、约束/精度和核验说明。`problem_contract.md` 只作阅读辅助。再输出 `shared/problem_route.md`：数学对象、任务动词、约束结构、数据机制、可验证锚点、赛程风险和一个强基线。只在能检验关键假设或降低风险时增加替代路线，并说明必要性；路线数量不是创新指标。

## Innovation Claim Engine 独立任务

完整读取 [innovation-engine.md](innovation-engine.md)，按 Wave 1–4 分配 Structure Mapper、Strong Baseline Builder、Baseline Failure Mapper、axis scouts、可选 Cross-domain Analogist、Literature Auditor、Experimenter、Critic 和 Jury。每个任务只写负责的 artifact；冻结前不读取其他 scout 或主任务偏好。

所有晋级 claim 必须先声明路径：`Problem Semantics → Faithful Formulation → Verification → Simplified Benchmark`，或 `Structure → Baseline Failure → Minimal Change → Gain`；两条路径都要连接最近先例、差异和论文落点。Literature Auditor 使用 `$citation-management`；Experimenter 保存 semantic-fidelity/falsification、改变开/关 ablation、命令、种子、artifact 和哈希；Critic/Jury 不得由主张作者兼任。候选数、axis、scout、类比和 safe/stretch 不作硬门禁。

Innovation discovery/evidence/Critic/Jury 不得作为普通模型分支的强制前置任务。若没有足以晋级的 claim，记录“无晋级主张”即可；只有实际晋级的 claim 才要求完整支路闭合。

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

## 自适应审查路由

任务说明：完整读取 `adaptive-review-and-evidence.md`，按每个小题的 Evidence Profile 填写 `synthesis/review_route.json`。Scientific、implementation、uncertainty 和 claims 始终 required；statistics 只在随机数据、抽样、估计、预测、分布主张、机器学习或随机模拟中 required。确定性题标记 not_applicable 时只写内部理由，不为论文生成“不适用”段落。

每问完成 implementation-assumption check：逐项核对数学定义与代码的定义域、端点、消元、离散、边界搜索、约束实现、停止准则和算法参数。保存真实 artifact 与哈希。审查结束后按 schema v3 填写 coverage：每个 pass 必须绑定本问论文锚点、具体检查、实际证伪/边界攻击、`no_material_issue / finding_recorded` outcome 和 artifact-backed evidence；不得复制跨问题的泛化通过理由。

## 强全域主张证书

任务说明：完整读取 `execution-integrity.md`，只核对 first/earliest/global minimum/global maximum/optimal/full-domain safety 或等价强主张的覆盖责任，不替作者假装完成数学证明。

模型冻结时人工扫描冻结结果，为拟写入论文的每条强主张建立结果级草案与覆盖证据；论文成文后再人工核对 `paper/main.tex` 实际载入的摘要、正文和结论，为每次出现位置完成唯一、局部的措辞绑定。validator 另用有限正则哨兵扫描已加载论文 TeX 的常见强措辞，但不扫描结果 artifact，也不保证覆盖所有等价表达；人工主张清单才是范围权威，主动登记的主张不会仅因未命中词表而失败。只有人工核对冻结结果和终稿已载入来源，且正则哨兵也无命中时，才可在 `synthesis/global_claim_certificates.json` 写具体 `not_applicable` 理由。对每条保留主张，登记完整定义域、候选划分或覆盖策略、端点/非光滑点/内部点检查、排除论证、适用限制，以及每次检查所引用的 artifact 路径、SHA-256、命令和时间。独立尝试寻找遗漏的事件点、拼接点、内部极值、未搜索区域或更早/更优反例。证据不足时要求缩小定义域或弱化措辞；validator 通过只表示证书和证据身份完整，不能写成“已自动证明全局最优”。

## 统计审计

任务说明：仅当 Review Router 标记 required 时使用 `$statistical-analysis` 审核指定分支，不为原作者辩护。

检查样本量、独立性、分布或残差假设、变量选择、共线性、多重比较、效应量、置信/可信区间、交叉验证设计、过拟合和结论措辞。区分统计显著与实际意义。

## 不确定性与量纲审计

任务说明：使用 `$uncertainty-and-units` 审核所有关键输入和输出。

检查量纲闭合、单位换算、求解器误差、测量误差、模型形式、参数区间、情景边界、误差传播和结果排序的稳定性。优先报告会改变结论方向、排名或正文显示精度的不确定性；非材料性机器精度只留在内部。

## 独立复现

任务说明：假定代码可能存在问题，从干净输出目录重新运行，不修改原代码来“帮助通过”。

运行 `snapshot_environment.py`；为 `result_manifest.csv` 的每条结果填写所属小问。把无 shell 的 argv、工作区内入口文件及其 SHA-256、工作目录、只覆盖输出的清理路径、全部预期结果哈希、复核人和时间写入 schema v2 `reproduction_status.json`，状态改为 ready。由 `finalize_submission.py` 在隔离副本删除旧结果后实际重跑。对随机算法另执行至少两次随机性检查；将无法运行、数值不一致、隐藏输入和人工中间步骤列为阻断项。

## 展示论文标杆审计

任务说明：使用去题目化结构卡，不评价待审模型是否“像某篇论文”。

按 `cumcm-excellent-paper-benchmark.md` 检查待审稿的证据职责：摘要结果地图、问题依赖、逐问闭环、基线、验证、图表职责、创新必要性、局限和复现。只输出可迁移的结构差距及最小修复，不复制展示论文的句子、图表或模型。

## 红队评委

任务说明：使用 `$scientific-critical-thinking`，以严格评委视角寻找足以降低奖级的问题。

优先攻击题意偏差、数学定义与代码实现错位、不可识别参数、循环论证、因果过度、外推失效、验证泄漏、伪精确、缺少基准比较和“结论先行”。每项批评必须引用具体产物并给出可验证的修复条件。

## 摘要 30 秒盲审

任务说明：只看最终摘要页和一张问题关系图，不读正文或主任务评价。

在 30 秒阅读目标下写出：任务、逐问方法、三个最重要的数值结论、可信证据和最大边界。无法从页面直接回答的项目标为 `major`；数字与冻结结果不一致、无单位或无法追踪标为 `blocking`。不通过增加算法名和形容词修复。

## 论文总编

任务说明：只使用通过门禁的结果，不重新计算或发明数字。开始前另完整读取 `execution-integrity.md`；小问范围、顺序和依赖以结构化原题契约为准。

先完整读取 `paper-presentation-engine.md`，从通过模型门禁的结果生成 schema v4 `synthesis/paper_payload.json`。论文手以该 Payload 为主要科学输入，不从 audit prose 复制句子。先逐项对照原题核验小问契约和依赖，`Qn` 必须映射到 `qNN.tex`，不能按 OCR 标题或文件顺序猜测。每问先写“主张—最短充分证据—最佳载体”表，再填写 `presentation_plan`：用 `answer_form / answer_anchor / answer_takeaway` 登记本问最短直接答案，用 `validation_form / validation_anchor / validation_takeaway` 登记本问最强验证；两个锚点都必须位于对应 `qNN.tex`。对每条材料性几何主张填写 `geometry_claims`，绑定独立正文锚点、对象、关系、公式及机制图/具体免图理由；高视觉负荷不能免图，所有主张在最终尺寸复核十秒可读性。对每幅登记图记录实际 LaTeX 宽度、最终最小字号和最终尺寸复核；量化图另登记本问 claim anchor、样本/像素及过绘保真处理。建立论点—证据—代码—图表追踪表并填写 `synthesis/innovation_claims.csv`；每个 promoted claim 按其 reasoning path 映射到 semantic requirement 或 baseline failure、数学改变、结果 ID、引用键、LaTeX 章节和锚点。只合并通过文献门禁的引用；保留会改变结论的假设、验证、敏感性、局限和当届声明。按实际小题分别写入 `paper/sections/questions/qNN.tex`，并在 `paper/generated/question_sections.tex` 按 `model_selection.json` 的同一顺序逐一载入；正文必须不依赖代码/数据附录即可回答全部小问。不创建大段题面复述、候选路线回顾、内部审计说明、泛化优缺点清单、空标题或重复结论。CUMCM 写作完整读取 `cumcm-paper-writing-and-figures.md`。每次合并后直接编译 LaTeX；draft 报告为 `review_only`，不得称为最终稿。若逐问交付 `qNN_standalone.pdf`，必须用 `build_latex.py --main qNN_standalone.tex --mode submission`，并随交付核对 `question_handoff_candidate`、`handoff_eligible=true` 和 PDF 哈希；裸 `xelatex` 产物不得交付。

## 科研制图审计

任务说明：有源数据的量化图如已安装则优先使用 `$scipilot-figure-skill`，并可用 `$data-analytics:visualize-data` 做交互探索或第二视角 QA；概念、流程、机理、几何与网络图不调用 SciPilot。任何绘图任务都不得改变数据或模型结果。

逐图记录论点职责、源数据、变换、脚本、解释器/库版本、随机种子、单位、区间定义、输出路径、论文锚点和哈希。所有图都登记与实际 LaTeX 一致的宽度、最终最小标签字号（不得低于 6 pt）和最终尺寸复核。量化图执行 `论证目标 → profile_data.py → 图型选择与避坑 → 最终尺寸渲染 → visual_qa.py → AI 读取 PNG → 回改重渲 → export_figure.py → check_figure.py --strict → LaTeX 实页复核`，另登记样本/像素估计与过绘保真处理；每像素超过 2 个样本时不得用“无需处理”过门禁。机理/几何图改用 TikZ、Matplotlib 3D、Graphviz 或原生代码，并按每条 geometry claim 检查关键对象、点/线/面、方向、坐标约定、公式映射和判据是否能在 10 秒内读懂；结果曲线不能代替空间关系图。尺度跨度大时生成“全局场景 + 局部判据”双面板。每幅图使用信息性题注，并在首次解释处用 `\ref`/`\autoref`/`\cref` 编号引用。检查坐标尺度、缺失值、平滑/归一化、误差含义、颜色冗余、灰度可辨性、最终栏宽字体、裁切和矢量导出；`check_figure.py` 对字体嵌入只给 warning 时再用 `pdffonts` 核对 `emb=yes`。全局尺度压缩关键结构时改用局部放大、inset 或相对坐标。删除装饰性 3D、重复表格、没有正文引用或不能支持论点的图。只把通过审计的 PDF/必要 PNG 放入 `paper/figures/`。

## LaTeX 与提交包审计

任务说明：不修改论证，只检查 LaTeX 工程和最终 PDF。

先运行 `validate_paper_presentation.py` 和 `validate_paper_question_coverage.py`，确认 Payload 与冻结小题一致、`Qn → qNN.tex` 映射正确、每问在本问文件内同时有直接答案和最强验证锚点、正文没有内部元语言且每问恰有一个已载入的非空 LaTeX 文件。独立小问稿还要核对专属 build report，确认竞赛语言、四项实质职责、验证锚点、比较证据和末页密度均通过。再从 `paper/main.tex` 运行直接构建，核对文献审计报告、编译报告、未定义引用、重复标签、缺失字体或字符、占位符、超宽公式/表格、浮动体位置，以及 competition profile 指定的页数、纸张、大小、匿名和 PDF 元数据。把 PDF 全部页面渲染为图片，重点检查摘要页、密集公式页、宽表、图组、参考文献和附录；确认正文脱离附录仍完整回答全部小问。

按已核验 profile 检查电子论文与支撑材料；填写匿名词表和显式支撑清单，运行 `finalize_submission.py`。第一次通过上游门禁后逐页审核它生成的 `final_pdf_pages`，确认 `page_layout_metrics` 覆盖并匹配每页；下方空白比例超过 45% 的页面必须修复，或仅在确属结尾材料/有意结构时填写相应 disposition 和具体 notes。填写 schema v2 `final_pdf_visual_review.json` 再重跑；PDF、页面图像或自动指标变化会自动撤销相应复核。只有模型选择、强全域主张证书、创新主张、隔离复现、科学审查、论文、profile 要求的支撑包、所有哈希和匿名/凭据扫描同时通过才允许放行。
