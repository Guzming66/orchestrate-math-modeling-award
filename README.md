# 数学建模竞赛总控 Skill

面向 CUMCM 国赛与 MCM/ICM 美赛的证据驱动总控。它协调逐问建模、创新主张、引用核验、复现、独立审查、LaTeX 写作和最终提交；不预测或保证奖项。

## v15 的八个核心系统

1. Rule Engine：只执行带有效生效起点、官方来源与哈希的已核验赛事规则档案；结束时间可空，但不得早于起点。
2. Model Selection Engine：按小题选择 Evidence Profile，以强基线和可复核证据决定方案。
3. Innovation Claim Engine：支持“忠实问题表述”和“基线失败—最小改变”两条创新路径。
4. Scientific Review Engine：按题型路由科学、实现、统计、不确定性和主张审查；schema v3 要求每个通过结论都有论文锚点、具体检查、证伪/边界攻击和真实证据。
5. Contest Paper Presentation Engine：用 schema v4 Paper Payload 隔离内部控制语言，逐条清偿几何主张的可视化债务，对所有图执行最终栏宽与标签字号门禁，并对量化图追加样本/像素和过绘保真检查。
6. Submission Finalizer：编译、渲染、交叉核对并按已核验规则执行 fail-closed 终审。
7. Paper Integrity Engine：检查论文接缝、公式—代码—结果追踪、AI 使用双向覆盖，并对本地优秀论文与固定模板执行可解释的相似度预检。
8. Execution Integrity Engine：把原题逐问契约绑定到源文件哈希，为首次/最早/全局极值/最优/全域安全等强主张建立 artifact-backed 证书，冻结跨问结果快照，实际执行隔离复现，并让最终 PDF 的逐页复核随页面或布局指标变化自动失效。

工作流采用五个阶段：`rule_verification → exploration → model_freeze → paper_freeze → submission`。默认使用 `standard`；`championship` 加强独立审查与稳健性，但不强制增加模型、统计段落或计算量。

## 配套 Skills

必需：`mathmodel-skill`、`citation-management`。

按题目路由：`statistical-analysis`、`uncertainty-and-units`、`scientific-critical-thinking`。数据驱动的论文图优先使用 `scipilot-figure-skill` 完成数据剖析、选图、出版级绘制和视觉自检闭环；`data-analytics:visualize-data` 只是可选的通用设计、交互探索和第二视角 QA，不计入七个核心 Skills。流程图、机理图与网络示意图仍使用 TikZ/Graphviz/原生代码。这七个核心 Skills 可以覆盖完整建模与论文流程，但仍需要参赛队员判断题意、核实当届规则、检查代码和数据、审阅引用、确认 AI 披露并完成正式提交。

## 安装

将本目录复制到 `$CODEX_HOME/skills/orchestrate-math-modeling`，或从 GitHub 仓库安装。安装后详细执行规则见 `SKILL.md`。仓库地址：<https://github.com/Guzming66/orchestrate-math-modeling>

## 快速开始

```text
使用 $orchestrate-math-modeling 为这道国赛题建立总控工作区。先核验当届官方规则并按小题冻结问题契约；为每问选择 Evidence Profile，建立最简单的充分方案，并在题意保真路径、基线失败最小改动或无创新主张之间作证据化裁决。完成实现一致性、适用的统计/不确定性审查后，只从 Paper Payload 写 LaTeX 论文并执行终审。
```

## 评估层级

- E0：schema、迁移、门禁、Presentation Firewall 和 LaTeX/PDF 自动测试。
- E1：历史赛题固定输入，对比有效创新主张、假创新率、复杂度、复现率、审查路由准确率、实现漏洞检出率和论文表达。
- E2：不知道版本信息的独立评阅者盲评论文质量。
- E3：多届真实赛事外部结果；只作观察，不能把获奖归因于本 Skill。

基准分数不等于获奖概率，也不作为自动回归阈值。

当前公开实现结论只到 E0。写作规范另由用户本地 2022–2025 年 47 篇/2379 页优秀论文语料作描述性结构校准，方法、逐篇去原文证据卡和全页视觉复核边界见 `references/cumcm-corpus-evidence-2022-2025.md`；原论文与 OCR 全文不随仓库分发。该语料校准不等同于 E1 解题演练。

本轮由生成稿与国赛展示论文差距触发的设计判断、整改映射和验收边界见 [`references/v15-paper-gap-remediation.md`](references/v15-paper-gap-remediation.md)。

## 设计底线

- 创新不是模型数量或算法复杂度；融合本身没有创新信用。
- 搜索宽度只告警，不阻断；简单而充分的方案可以胜出。
- 规则、文献、数据、结果和重大审查发现必须由真实产物支持。
- “首次、全局、最优、全域安全”等措辞先在模型冻结后形成结果级草案，再在论文与隔离复现完成后逐出现位置绑定；证书必须声明定义域、覆盖/候选划分、端点与非光滑/内部检查和排除论证，验证器只核对证书与证据身份，不自动证明数学真值。
- 跨问结果不能靠文字“沿用”；上游数值、命令或文件变化后，下游必须重新验收。
- 复现由终审器在隔离副本实际执行；最终 PDF 每页必须通过渲染哈希和自动布局指标绑定的视觉检查，大面积下方留白必须有明确、可复核的版面处置。
- 几何图债务按主张而不是按小题结清；所有图必须在实际 LaTeX 尺寸检查可读性，量化图还要检查过绘信息损失。
- 内部证据保持完整，最终论文不暴露任务、冻结、哈希或审计元语言。
- 最终论文以 LaTeX 为唯一真源，不做 Word/Markdown 格式转换。
- `final_report.json=pass` 只表示框架定义的技术门禁通过，不代表官方接受或获奖保证。
