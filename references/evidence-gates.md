# 证据门禁与裁决规则

## 目录

1. 严重程度
2. 八道门禁
3. 分支比较矩阵
4. 国赛与美赛侧重点
5. 完成标准

## 严重程度

- `blocking`：足以使结论无效、无法复现、违规或无法提交；关闭前不得进入最终论文。
- `major`：可能改变模型选择、核心数值或主要结论；必须修复或在正文中充分限定。
- `minor`：不改变结论，但影响清晰度、表现或局部可信度；在提交前处理。

不要把数量或加权总分当作官方奖项预测。一个阻断项比许多轻微优点更重要。

## 八道门禁

### G0 规则与合规

核实当届官方网站、截止时间、匿名要求、文件格式、页数或大小限制、外部数据、引用和其他当届规定。按 [competition-profile.md](competition-profile.md) 把规则写入 `compliance/competition_profile.json`；每个官方来源保存工作区内快照、SHA-256、检查步骤和时间。不得按年份猜规则。

### G1 文献来源与真实性

完整执行 [citation-integrity-audit.md](citation-integrity-audit.md)。要求每条核心外部主张在 `citation_ledger.csv` 中映射到已核验来源、原文定位和本地审计 artifact/hash/check/timestamp；自动检查 DOI、BibTeX 和引用键，人工核对题录身份、原文支持、正式版本及撤稿/更正状态。文献不存在、标识符错配、原文不支持或证据断链即阻断。

### G2 数据可信度

要求 `data_provenance.csv` 覆盖每个原始与外部输入，文件哈希、来源、授权/条款、取得时间、字段和处理路径可追踪。原始附件必须保留。未登记文件、哈希变化、数据泄漏、口径混用或无法解释的大规模删除为阻断项。

### G3 分支完整性

正式建模前要求 Innovation Claim Engine 通过：至少一个晋级 claim 具有强基线、已证明的 baseline failure、直接作用于 failure 的最小改变、最近先例、falsification，以及复杂度需要时的改变开/关 ablation；Critic 阻断项已关闭。候选数量、axis、scout 和类比只产生探索告警。随后要求最终 solution 定义完整、代码可运行、结果登记到 `result_manifest.csv`。算法名、模型堆叠或字段非空但 artifact 断链均不通过。

### G4 统计与不确定性

要求关键假设接受检查，报告适合的区间或误差，结论在合理参数扰动下稳定。排名或政策结论对微小扰动翻转时，必须降级结论或重新设计。

### G5 独立与替代验证

至少用一个与主实现失效模式不同的验证锚点复核核心结论，例如解析特例、精确小实例、物理守恒、留出数据、改变开/关消融、替代求解器或独立重算。只有当替代模型确实检验关键假设时才增加模型分支；一个主模型加严格的独立验证可以通过。不得把同一实现换参数或多个分支共享同一套未经检验假设宣称为“交叉验证”。

### G6 独立复现

由未参与原实现的任务在干净输出目录运行。核心数字、表格和图形必须可重建，并把命令、复核人和证据写入 `reproduction_status.json`。隐藏的手工步骤、缺失依赖、随机结果漂移、结果文件与代码不一致或状态未通过均为阻断项。

### G7 论文与提交

要求摘要直接回答问题，符号单位一致，图表可读，引用可核验，关键数字可追踪，局限性真实，当届额外材料完整。运行 `finalize_submission.py`；论文必须从 `paper/main.tex` 直接构建，支撑包必须从显式清单生成并通过匿名/凭据扫描，G0—G7 全部有复核证据。`final_report.json` 不是 `pass` 即阻断。

赛事特定的首页、目录、纸张、页数、大小、附录、支撑包和匿名要求只从已核验 competition profile 执行；本参考文件不覆盖当届官方规则。

## 分支比较矩阵

在 `synthesis/evidence_matrix.csv` 为每个分支记录以下字段，不强制计算总分：

- `branch`
- `problem_fit`
- `assumption_risk`
- `data_support`
- `innovation_claim_ids`
- `innovation_claim_status`
- `baseline_gain`
- `diagnostic_quality`
- `uncertainty_stability`
- `reproducibility`
- `interpretability`
- `implementation_risk`
- `paper_communicability`
- `rule_compliance`
- `blocking_findings`
- `decision`
- `decision_evidence`

优先比较原始证据和阻断项。只有在指标定义与重要性来自题意时才使用权重；同时做权重敏感性分析。

## 国赛与美赛侧重点

### CUMCM/国赛

重视题意落地、合理假设、模型—结果闭环、中文表达、PDF 版式、单位和工程解释。不要把复杂算法本身当作创新，不按题号字母预设题型。比赛开始时重新核对当届提交规范。

### MCM/ICM/美赛

重视清晰叙事、可解释建议、Summary Sheet、数据与引用质量、图表信息密度和英文一致性。题目要求 Memo 或 Letter 时，把受众、语气和行动建议作为单独门禁。比赛开始时重新核对当届 Instructions 与额外材料要求。

## 完成标准

每个 gate 的 `evidence` 必须是包含 `artifact_path`、`sha256`、`command_or_check` 和 `checked_at` 的对象。仅当 G0—G7 均无未关闭的 `blocking`，所有 `major` 已修复或被正文明确限定，且最终文件经过人类队员复核后，才能报告“可提交”。“可提交”不等同于获奖保证。
