# 自适应证据与审查路由

## 目录

1. 先选 Evidence Profile
2. 各 Profile 的最低证据
3. Review Router
4. 数学定义—代码实现检查
5. 论文输出边界

## 先选 Evidence Profile

每个核心小题在拟合或大规模计算前选择一个主 `evidence_profile`。Profile 描述“结论靠什么成立”，不是题号、算法名或模型复杂度。

| profile | 典型任务 | 核心证据 |
|---|---|---|
| `analytical` | 解析推导、几何定理、闭式关系 | 推导、边界、特殊情形 |
| `deterministic_numerical` | 求根、积分、ODE/PDE 数值解、离散几何 | 收敛、离散加密、交叉求解 |
| `optimization` | 规划、启发式搜索、最优控制、调度 | 可行性、边界、最优性/搜索充分性、敏感性 |
| `statistical` | 抽样、回归、时间序列、统计推断 | 假设、拟合诊断、区间、样本外验证 |
| `simulation` | 随机模拟、Agent/排队/蒙特卡洛系统 | 校准、收敛、随机不确定性、情景验证 |
| `machine_learning` | 监督/无监督学习、表征与预测 | 泄漏、样本外、校准/误差、稳健性 |

一个小题若包含两类证据，以决定主要结论的 Profile 为主，把另一类检查写入 `verification_checks` 的附加项或拆成明确子结论。不要为了填字段把确定性几何问题改写成统计问题。

## 各 Profile 的最低证据

`synthesis/model_selection.json` 使用 schema v2。每个 baseline 和最终模型的 `post_fit_evidence` 保存：

- `result_summary`：直接回答本问的结果；
- `verification_checks`：本 Profile 的检查及 `pass/not_applicable`；
- `artifact_path + sha256 + command_or_check + checked_at`：内部证据。

draft 可用 `planned_verification_checks` 或 `status=pending` 表达尚未执行的检查；validator 在 draft 只检查问题结构、Profile、候选和强基线，不会把未选择的候选误报为“已淘汰”。一旦状态改为 `frozen`，检查只能是 `pass/not_applicable`，且基线和入选方案必须有真实 artifact。

`not_applicable` 只在内部保存具体理由。不得在论文中列举一串不适用的统计方法或写“本文不虚构置信区间”。

Profile 只决定检查责任，不规定正文篇幅。内部可以保存求根到机器精度的差异；若输入、模型或参数只支持两位小数，论文只报告足以证明显示精度可靠的数值误差。

## Review Router

模型冻结后填写 `synthesis/review_route.json`：

- `scientific`：始终 required；
- `implementation`：始终 required；
- `claims`：始终 required；
- `uncertainty`：始终 required，但只把材料性来源写进论文；
- `statistical`：`statistical/simulation/machine_learning` 必须 required；`analytical/deterministic_numerical/optimization` 可根据数据、随机性和主张标记 required 或 not_applicable。

路由草稿中的 `implementation_assumption_check.status` 可为 `pending`；只有实际完成并附证据后才能把根状态改为 `routed`。finalizer 不接受 pending。

不按题号或“使用了 Python”判断是否需要统计。出现抽样、估计、预测、分布主张、机器学习、随机模拟或概率区间时，统计审查不得路由为 not_applicable。

`uncertainty_focus` 从以下来源选择：

- `numerical_solver`：离散、容差、收敛与求解器误差；
- `parameter_sensitivity`：参数口径或取值变化；
- `model_form`：简化假设与结构近似；
- `measurement`：测量和数据误差；
- `stochastic`：随机模拟或分布不确定性。

正文优先报告会改变结论、排序、策略或显示精度的来源。其余保留在审计台账。

## 数学定义—代码实现检查

每问必须完成 `implementation_assumption_check`，专门寻找代码暗中使用但正文没有证明、说明或验证的性质：

1. 定义域、变量上下界和端点是否与代码一致；
2. 连续对象改为网格、边界或有限样本时，是否给出理论理由或独立验证；
3. 消元、对称性、单调性、凸性和可分解性是否真的成立；
4. 约束是在算法中强制满足，还是只在结果后检查；
5. 事件、极值、根和可行域是否可能被离散步长漏掉；
6. 目标函数、罚函数、停止准则和最终报告指标是否同义；
7. 代码参数、随机种子、搜索区间与论文算法参数表是否一致。

能严格证明时给证明；不能证明时给明确近似及能攻击该近似的数值测试。大量随机点没有自动替代理论说明，但可以作为边界性或离散化假设的经验支持，并应准确限定结论。

## 论文输出边界

`audits/review_findings.json` schema v2 按小题覆盖 `scientific / implementation / statistical / uncertainty / claims`。统计 not_applicable 的理由、review 状态、证据哈希和检查命令都留在内部。

论文只呈现：采用了什么数学假设、验证了什么关键性质、观察到什么误差或边界，以及这些结果如何影响答案。不要呈现 Review Router、Evidence Profile、门禁或“某审查不适用”。
