# Contest Paper Presentation Engine

## 目录

1. 三层隔离
2. Paper Payload
3. 竞赛原生语言
4. 段落价值与篇幅
5. 数值精度预算
6. 算法与复杂度价值
7. 图表信息密度
8. 摘要和终审

## 三层隔离

保持三个单向层：

`Control Plane → Scientific Solution Plane → Contest Paper Plane`

- Control Plane 保存规则绑定、任务状态、哈希、复现命令、审查、模型裁决和内部风险。
- Scientific Solution Plane 保存假设、定义、推导、算法、参数、结果、比较、验证、不确定性、局限、图表和引用标识。
- Contest Paper Plane 只把经过压缩的科学内容写成评委可快速理解的 LaTeX。

内部继续严格；论文不暴露控制平面。论文手以 `synthesis/paper_payload.json` 为主要科学输入，只在核对事实时读取结果或引用台账，不得从 audit prose 复制句子。

## Paper Payload

每个小题在模型冻结后填写：

- `evidence_profile`
- `problem_summary`
- `assumptions`
- `core_model`
- `derivation_summary`
- `algorithm_summary`
- `key_results`
- `comparison_summary`
- `validation_summary`
- `sensitivity_and_limits`
- `precision_policy`
- `complexity_value`
- `paper_section`
- `figures`
- `citations`

字段是科学载荷，不是强制论文小节。`algorithm_summary` 对解析推导可留空；其他 Profile 记录实际求解或估计过程。`comparison_summary` 没有材料性比较时可留空，但必须由评审确认删去不会改变论证。`complexity_value.mode` 只用 `no_extra_complexity / semantics_required / incremental_change`：前两类允许 `incremental_gain=null`，不得为题意直接规定的边界、容量或守恒约束编造“增益”；只有保留可选增量组件时才必须填写可验证增益。不要求机械地在正文生成一张表。

Payload 禁止出现 `workflow_stage`、freeze、acceptance、review/claim status、artifact/hash、audit path、task board 或 reproduction command。证据身份仍由外部台账核验，不复制到 Payload。

## 竞赛原生语言

| 内部概念 | 论文表达 |
|---|---|
| strong baseline | 基准模型、简化模型 |
| baseline failure | 简化模型的具体局限 |
| faithful formulation | 按题意建立的完整/保真模型 |
| model/paper freeze | 不写 |
| downstream interface | 后续问题沿用上述判据/参数/模型 |
| artifact-backed evidence | 数值结果、对比实验或推导表明 |
| falsification | 验证实验、反例检查、边界测试 |
| audit/review finding | 检查、验证或具体修复内容 |
| materiality threshold | 精度要求、允许误差、会改变结论的范围 |
| no innovation claim | 不写 |
| hash/reproduction bookkeeping | 不写；按规则进入支撑材料 |

禁止否定性元话语，例如“本文不虚构置信区间”“本修正不作为创新”“已通过 Q1 验收”。若必须限定启发式结论，写“所得方案为多次独立搜索中的最佳可行方案”，并给搜索范围和验证，而不是解释内部审计立场。

## 段落价值与篇幅

正文段落至少承担一种职责：`MODEL / DERIVATION / ALGORITHM / RESULT / COMPARISON / VALIDATION / SENSITIVITY / LIMITATION / DECISION`。主要属于 `WORKFLOW / AUDIT / HASH / FREEZE / INTERNAL STATUS` 的段落不得进入正文。

优先篇幅顺序：

1. 题目特有结构和关键建模思想；
2. 数学定义、必要推导与约束；
3. 直接回答小题的结果及比较；
4. 能改变可信度的验证、敏感性和局限；
5. 足够复算的算法参数；
6. 其余内部数值和工程记录。

删除大段题面复述、算法验收流水账、重复结论、无意义复杂度公式和泛化优缺点套话。保留真正影响复算的搜索范围、种群规模、迭代上限、停止条件、网格步长和随机种子；放正文表格还是支撑材料由篇幅和 profile 决定。

## 数值精度预算

先比较：

`numerical solver error`、`parameter/input uncertainty`、`model-form uncertainty`、`required answer precision`。

正文只报告足以支持显示精度的求解误差。若求解器差异为 `10^-12`，而参数口径改变结果约 `10^-2`，正文写“加密计算和交叉求解的差异远小于 0.01，满足结果保留两位小数的精度要求”；机器精度保留在内部。

禁止以无意义小数制造可靠感。先对不确定性取合理有效数字，再把结果舍入到同一数量级。

## 算法与复杂度价值

复杂度分析只有在解释可计算性、规模上限或方法选择时进入正文。不得用一个抽象 `O(·)` 替代真实算法配置。

对每层额外复杂度记录：

- 解决的具体结构或 failure；
- 相对简化策略的增量结果；
- 计算/数据/解释成本；
- 是否经改变开关消融或分阶段策略比较支持。

评委应能从一张短表或一句话看出“增加这一层究竟改善了什么”。如果没有独立增益，删除该层或选择更简单方案。

## 图表信息密度

先按图的数学对象分流：有源数据的折线、散点、分布、比较、误差、不确定性、热力图、诊断图和多面板结果图优先调用 `$scipilot-figure-skill`；机理、几何、流程、网络和算法示意图不交给 SciPilot，使用可复现 TikZ/Graphviz/原生代码。`$data-analytics:visualize-data` 可用于交互探索、通用设计和第二视角 QA，但不替代 SciPilot 的数据剖析与成图闭环。SciPilot 不可用时，按同一契约直接使用 Matplotlib/Seaborn。

每图先写图表契约：分析问题、主要证据职责、源数据、编码、单位/区间、最终尺寸、输出路径和灰度区分。证据职责仅用 `mechanism / data / diagnostic / decision`。

量化图依次执行：确认本图要证明的论文主张 → `profile_data.py` 剖析字段、样本量、缺失、分布、异常和分组 → 给出首选图及理由并拦截误导性图型 → 按论文最终栏宽渲染 → `visual_qa.py` 检查缺字、裁切和刻度重叠 → 读取 PNG 预览检查图例遮盖、面板对齐、灰度区分和数据完整性 → 修正并重渲，最多三轮仍失败则拆图或重选图型 → 通过后运行 `export_figure.py` 与 `check_figure.py --strict` 导出 PDF/必要的 PNG。先用布局工具解决边界，再以 `tight=False` 导出正式 PDF，避免 `bbox_inches='tight'` 改变声明的最终物理尺寸；紧边界 PNG 只作预览。每轮从绘图源代码修改，不在预览图上手工修图。

检查关键结构是否在图中可见。若全局尺度把关键变化压成一条线，使用局部放大、inset、相对坐标或删除；不要保留“看起来完整但读不出结论”的图。图表与表格不重复同一信息：图用于结构、趋势和比较，表用于精确查数。

优先矢量 PDF；栅格内容用高分辨率 PNG。误差棒、带状区间、箱线和显著性标记必须在题注写清 SD/SEM/CI/IQR、样本量、检验及校正。最终判断必须在实际 LaTeX 栏宽和渲染 PDF 中完成，检查字体、图例、裁切、灰度和题注；单独打开原图通过不等于论文版面通过。

## 摘要和终审

摘要按“问题 → 核心模型/方法职责 → 关键结果 → 最强验证或边界”覆盖每问。优先呈现题目特有思想和关键数值，不罗列内部验证器、随机种子、模型候选或否定性声明。

论文冻结前运行：

```text
python <skill>/scripts/validate_paper_presentation.py <workspace>
```

该验证器检查 Payload 与冻结小题一致、Payload 不含控制平面字段、论文章节存在、图表文件存在，并扫描典型审计/冻结/哈希元语言。它不能替代评委式人工阅读；最终仍执行摘要 30 秒盲审和逐页 PDF 检查。
