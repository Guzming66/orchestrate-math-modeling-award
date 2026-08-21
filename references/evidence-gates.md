# 证据门禁

v15 不维护重复的 G0—G7 人工总表。每类判断由最接近证据的 validator 负责，Scientific Review Engine 统一收集需要人类判断的发现，finalizer 汇总真实产物并亲自执行隔离复现与最终页面渲染。

## 硬阻断

- Competition Profile 未核验、规则无官方 source binding、locator 或 hash 不匹配；
- 原题逐问契约没有连接真实原题文件、定位与 hash，或其小问顺序和模型/论文不一致；
- 跨问依赖缺少冻结结果 fingerprint，或上游结果变化后下游接口已过期；
- 原始/外部输入没有 provenance，或数据版本、口径、授权无法追踪；
- 某个核心小题没有 Evidence Profile、基准模型、拟合前理由、Profile 对应检查、选择理由或淘汰理由；
- first/earliest/global minimum/global maximum/optimal/full-domain safety 等强主张没有完整证书、定义域、覆盖/候选划分、端点/非光滑/内部检查、排除论证或真实 artifact；
- Review Router 缺失，统计审查被错误跳过，数学定义—代码实现检查没有真实证据，或某个 review pass 没有本问论文锚点、具体检查、实际证伪/边界攻击、outcome 与 artifact；
- promoted innovation claim 没有合法 reasoning path；Path A 缺少题意保真证据，或 Path B 缺少 baseline failure 与最小改变；
- 核心数字没有结果台账、单位、命令、输入、环境、随机种子或 hash；
- Finalizer 不能在隔离副本从已删除的结果路径重新生成全部核心结果并匹配 hash；
- 引用身份错误、原文不支持、正式版本/更正撤稿状态未检查；
- 独立审查仍有 unresolved critical/open major，或 accepted major 缺少责任人、影响范围、后备方案或超过 policy；
- 摘要、正文或结论出现无法映射到结果/文献/innovation claim 的强主张；
- `paper_payload.json` 与冻结小题不一致，或 Payload/正文泄漏 freeze、验收、hash、audit/review status、claim status 等内部元语言；
- 每问没有把最强验证映射到正文真实 `validation_anchor`，或只声称复算/证书/稳健而不给评委可核验的比较、误差或边界；
- 材料性几何主张没有逐条绑定本问主张锚点、对象、关系、带标签公式与机制图/具体免图理由，或高视觉负荷主张缺图、未在最终尺寸完成十秒可读性复核；
- 任一登记图没有与 LaTeX 一致的实际宽度、最终最小字号与最终尺寸复核；或 `data / diagnostic / decision` 量化图没有绑定本问主张、样本/像素与过绘保真处理，或高密度图未采取保结构处理；
- CUMCM 冻结的小题没有与含实质内容的 LaTeX 小题章节一一对应，或仍含占位符/仅有标题；
- 独立小问 PDF 由裸 LaTeX 引擎生成、缺少通过的专属 build report，或缺少任务—模型—结果—验证职责、验证锚点、比较性可见证据，或末页存在大面积无意留白；
- profile 要求的产物缺失、归档路径错误、匿名/凭据扫描失败；
- LaTeX 构建、页数/纸张/大小或最终 hash 检查失败。
- 最终 PDF 任一页面未完成字体、符号、裁切、图表、页码与匿名性复核，`page_layout_metrics` 未覆盖/不匹配，稀疏页面没有有效 disposition 与具体说明，或复核后 PDF、页面像素、自动布局指标发生变化。

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

严重度只使用 `critical / major / minor / suggestion`。Critical 和 major finding 必须有 artifact-backed evidence。Open major 一律阻断；`standard` 可由团队在 `max_accepted_major` 中允许极少量有责任人、影响范围和后备方案的 accepted major，`championship` 默认阈值为 0。Critical 不得以 accepted risk 放行。

该文件使用 schema v3。Coverage 的 `pass` 本身也是需要证据的判断：必须连接本问锚点、具体检查、能真实攻击结论的证伪/边界尝试、`no_material_issue / finding_recorded` outcome 及 artifact。Validator 只检查记录、锚点与 artifact 身份，不替代审查者对攻击是否有力的判断。

不使用总分预测奖项。阻断项优先于加权总分；简单、证据充分的方案可以击败复杂方案。
