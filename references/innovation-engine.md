# Innovation Claim Engine：数学建模论文创新工程

## 核心定义

创新不是模型数量、算法名称或复杂度。把可晋级的创新主张写成：

`题目结构 → 强基线 → 已证实的基线失败 → 最小必要改变 → 增益/失效证据 → 最近先例与差异 → 论文落点`

最终可以只有一个传统主模型和一个强创新点。融合、集成或 hybrid 本身不获得创新信用；只有组件分别解决不同失败机制、存在明确数学接口且逐组件消融证明不可替代时，才把融合视为创新的一部分。不得声称世界首创或保证奖项。

这一工程定义是本 Skill 的方法论推断，不冒充赛事官方评分公式。CUMCM 的赛区与全国评阅规范都要求评阅者识别“突出创新点”，并未把创新限定为新模型架构；COMAP 的当届说明强调问题分析、模型动机、测试、误差/敏感性、结论与沟通，专项奖还分别关注创造性、数据使用、实用性、清晰度和创新建模。因此本 Engine 审核整条论文证据链，而不把算法数量当作官方创新指标：

- CUMCM 赛区评阅规范：<https://www.mcm.edu.cn/html_cn/node/011a3fefdb4951a8cb595400f44ec3df.html>
- CUMCM 全国奖项评阅规范：<https://www.mcm.edu.cn/html_cn/node/b1f48689659f0660e80a2d6279d7b37d.html>
- COMAP Contest Rules, Registration and Instructions：<https://www.contest.comap.com/undergraduate/contests/mcm/instructions.html>

## 探索目标，不是硬门禁

| mode | claim 目标 | innovation axis 目标 | scout 目标 | 类比目标 |
|---|---:|---:|---:|---:|
| `standard` | 6 | 4 | 3 | 1 |
| `championship` | 8 | 5 | 4 | 1 |

低于目标只产生 `warning: search breadth may be insufficient`。不要为了过门禁制造主张、类比、scout、模型分支或 safe/stretch 组合。跨领域类比只用于发现机会，不证明创新成立。

## Innovation axes

- `problem_formulation`：问题重构；
- `state_representation`：状态、变量、潜变量、无量纲量或图表示；
- `assumption_mechanism`：守恒、边界、滞后、拥堵、异质性等机制；
- `problem_decomposition`：时空、阶段或层次分解；
- `objective_constraint`：损失、风险、公平、鲁棒或可行约束；
- `parameter_inference`：辨识、校准、贝叶斯更新或误差传播；
- `solution_strategy`：利用题目结构的松弛、剪枝、降维、近似或动态规划；
- `data_use`：从现有数据提取新的有效信息或指标；
- `validation`：物理锚点、反事实、边界测试或精确小实例；
- `decision_explanation`：阈值、策略区域、风险图或可行动规则；
- `model_structure`：题目确实需要的新模型机制；
- `model_fusion`：仅在组件必要性、接口和消融均通过时使用。

## Wave 1 — Structure & Baseline

1. **Structure Mapper** 只抽取数学对象、数据生成机制、守恒/网络/时空/控制结构、可识别性、子问接口和验证锚点，不先报算法名。
2. **Strong Baseline Builder** 为每个关键子问建立最自然、最简单、可复现的经典基线，冻结输入、指标和切分。
3. **Baseline Failure Mapper** 用 artifact-backed 测试识别具体失败机制；“精度不够”“模型太简单”不算失败机制。

Failure Mapper 提示词：

```text
读取题面、结构图和冻结强基线。逐项测试基线假设，寻找守恒破坏、删失、不可识别、
尾部风险、动态失配、网络成本失真、初值敏感、泄漏或上游不确定性丢失等具体 failure。
每个 failure 保存 artifact_path、sha256、command/check 和 timestamp。
若没有材料性 failure，明确输出“当前无创新必要”，不要制造高级模型。
```

## Wave 2 — Innovation Discovery

让隔离的 scouts 从不同 innovation axis 寻找解决已验证 failure 的最小改动。每张 `claim card` 回答：

- 哪个题目结构导致哪个基线假设失败；
- failure 的可复核证据是什么；
- proposed change 如何直接作用于 failure；
- 数学表达和最简单替代方案是什么；
- 每层额外复杂度为什么必要；
- 如何证伪、消融，失败时退回什么基线；
- 预计写在论文哪个位置。

执行最小充分改变原则：较简单的机制已经消除 failure 时，禁止仅为“创新感”追加组件。只换优化器、调参器、backbone 或把 LSTM/XGBoost/GNN/GA 等串联，均按重复或性能工程处理。

Cross-domain Analogist 可以给出源领域、结构映射、失配点和否定测试；无可靠同构时允许输出零条类比。

## Wave 3 — Evidence

1. **Literature Auditor** 使用 `$citation-management`，核对原始来源、权威元数据、正式版本、撤稿/更正状态、最近先例和原文定位。搜索页和 AI 回答只能发现线索。
2. **Experimenter** 先做最便宜的 falsification，再按需做 ablation 和 robustness。实验必须冻结同口径基线、数据/fixture、命令、环境、种子、指标、结果 artifact 和 SHA-256。
3. 消融对象是“创新改变开/关”，不是只比较整套 Model A/Model B。
4. fusion/ensemble/hybrid 必须同时满足：组件对应不同 failure、数学接口明确、每个组件均有通过的消融；否则不给创新信用。

## Wave 4 — Paper Jury

Critic 先执行硬否决，再由 Jury 做 Pareto/lexicographic 裁决，不计算一个可被高复杂度补偿的总分。优先级：

`problem fit → evidence → necessity → novelty → robustness → parsimony → communication`

Jury 的 1–5 分只作诊断：问题贴合、证据强度、必要性、新颖性、稳健性、简洁性和表达清晰度。最终至少晋级一个证据充分的 `primary` claim，可有 supporting claims；不要求 safe/stretch，也不限制为 2–3 个模型。最终 solution 由 `synthesis/model_selection.json` 按每个核心小题保存拟合前理由、拟合后证据、选择理由和淘汰理由。

## 真正的阻断条件

任一晋级 claim 出现以下情况即阻断：

- 没有强基线或明确 baseline failure；
- failure 没有真实 artifact、哈希、检查步骤和时间；
- proposed change 与 failure 没有结构/因果联系；
- 没有 falsification test；需要复杂度或融合却没有增量消融；
- 最近先例、题录身份、原文支持或撤稿/更正状态未核实；
- 只是换名、堆叠或增加复杂度而无独立增益；
- blocking/major Critic finding 未关闭；
- 没有明确论文落点，或论文主张无法映射到结果与引用。

## 产物

- `innovation/structure_map.md`
- `innovation/baseline_failure_map.md`
- `innovation/opportunity_map.md`
- `innovation/claim_portfolio.csv`
- `innovation/novelty_audit.csv`
- `innovation/claim_experiments.csv`
- `innovation/critic_findings.csv`
- `innovation/selection.csv`
- `innovation/jury_rationale.md`
- `synthesis/innovation_claims.csv`

运行：

```text
python <skill>/scripts/validate_innovation_portfolio.py <workspace>
python <skill>/scripts/validate_paper_innovation.py <workspace>
```

第一个检查研究过程，第二个检查 `promoted claim → result_manifest → citation_ledger → LaTeX 章节/锚点`。两者通过只说明证据链完整，不证明理论原创或获奖。
