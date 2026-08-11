# 证据门禁

v11 不维护重复的 G0—G7 人工总表。每类判断由最接近证据的 validator 负责，Scientific Review Engine 统一收集需要人类判断的发现，finalizer 只汇总验证状态与真实产物。

## 硬阻断

- Competition Profile 未核验、规则无官方 source binding、locator 或 hash 不匹配；
- 原始/外部输入没有 provenance，或数据版本、口径、授权无法追踪；
- 某个核心小题没有 Evidence Profile、基准模型、拟合前理由、Profile 对应检查、选择理由或淘汰理由；
- Review Router 缺失，统计审查被错误跳过，或数学定义—代码实现检查没有真实证据；
- promoted innovation claim 没有合法 reasoning path；Path A 缺少题意保真证据，或 Path B 缺少 baseline failure 与最小改变；
- 核心数字没有结果台账、单位、命令、输入、环境、随机种子或 hash；
- 核心结果不能在干净环境独立复现；
- 引用身份错误、原文不支持、正式版本/更正撤稿状态未检查；
- 独立审查仍有 unresolved critical，或 open major 超过 policy；
- 摘要、正文或结论出现无法映射到结果/文献/innovation claim 的强主张；
- `paper_payload.json` 与冻结小题不一致，或 Payload/正文泄漏 freeze、验收、hash、audit/review status、claim status 等内部元语言；
- 每问没有把最强验证映射到正文真实 `validation_anchor`，或只声称复算/证书/稳健而不给评委可核验的比较、误差或边界；
- 依赖几何、轨迹、视线或可见性推理的小题没有登记并呈现 `mechanism` 直观图；
- CUMCM 冻结的小题没有与含实质内容的 LaTeX 小题章节一一对应，或仍含占位符/仅有标题；
- 独立小问 PDF 由裸 LaTeX 引擎生成、缺少通过的专属 build report，或缺少任务—模型—结果—验证职责、验证锚点、比较性可见证据，或末页存在大面积无意留白；
- profile 要求的产物缺失、归档路径错误、匿名/凭据扫描失败；
- LaTeX 构建、页数/纸张/大小或最终 hash 检查失败。

## 只告警

- 候选模型、创新 claim、scout、innovation axis 或跨领域类比数量较少；
- 只评估强基线，但证据表明没有必要增加候选；
- minor/suggestion finding 尚未关闭；
- 非阻断排版警告或 benchmark 覆盖不足。

告警必须可见，但不得为了消除告警制造模型、创新或实验。

## Scientific Review Engine

`audits/review_findings.json` 按小题覆盖五类审查：

- `scientific`：问题表述、机制、假设、边界、因果与外推；
- `implementation`：数学定义、代码边界、消元、离散和事件搜索一致性；
- `statistical`：仅按 Review Router 检查数据泄漏、抽样、估计、诊断、区间和比较；
- `uncertainty`：求解器、参数、模型形式、测量与随机不确定性；
- `claims`：摘要、正文、图表和结论是否超过证据。

严重度只使用 `critical / major / minor / suggestion`。Critical 和 major finding 必须有 artifact-backed evidence。`standard` 可由团队在 policy 中允许极少量已明确风险的 open major；`championship` 默认阈值为 0。Critical 不得以 accepted risk 放行。

不使用总分预测奖项。阻断项优先于加权总分；简单、证据充分的方案可以击败复杂方案。
