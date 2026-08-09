# 证据门禁

v9 不再维护重复的 G0—G7 人工总表。每类判断由最接近证据的 validator 负责，Scientific Review Engine 统一收集需要人类判断的发现，finalizer 只汇总验证状态与真实产物。

## 硬阻断

- Competition Profile 未核验、规则无官方 source binding、locator 或 hash 不匹配；
- 原始/外部输入没有 provenance，或数据版本、口径、授权无法追踪；
- 某个核心小题没有强基线、拟合前理由、拟合后证据、选择理由或淘汰理由；
- promoted innovation claim 没有 baseline failure、最小改变、最近先例、证伪/必要消融或论文落点；
- 核心数字没有结果台账、单位、命令、输入、环境、随机种子或 hash；
- 核心结果不能在干净环境独立复现；
- 引用身份错误、原文不支持、正式版本/更正撤稿状态未检查；
- 独立审查仍有 unresolved critical，或 open major 超过 policy；
- 摘要、正文或结论出现无法映射到结果/文献/innovation claim 的强主张；
- profile 要求的产物缺失、归档路径错误、匿名/凭据扫描失败；
- LaTeX 构建、页数/纸张/大小或最终 hash 检查失败。

## 只告警

- 候选模型、创新 claim、scout、innovation axis 或跨领域类比数量较少；
- 只评估强基线，但证据表明没有必要增加候选；
- minor/suggestion finding 尚未关闭；
- 非阻断排版警告或 benchmark 覆盖不足。

告警必须可见，但不得为了消除告警制造模型、创新或实验。

## Scientific Review Engine

`audits/review_findings.json` 覆盖三类审查：

- `scientific`：问题表述、机制、假设、边界、因果与外推；
- `statistical`：数据泄漏、抽样、估计、诊断、区间、比较公平性和不确定性；
- `claims`：摘要、正文、图表和结论是否超过证据。

严重度只使用 `critical / major / minor / suggestion`。Critical 和 major finding 必须有 artifact-backed evidence。`standard` 可由团队在 policy 中允许极少量已明确风险的 open major；`championship` 默认阈值为 0。Critical 不得以 accepted risk 放行。

不使用总分预测奖项。阻断项优先于加权总分；简单、证据充分的方案可以击败复杂方案。
