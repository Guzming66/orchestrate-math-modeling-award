# 数学建模竞赛总控 Skill

面向 CUMCM 国赛与 MCM/ICM 美赛的证据驱动总控。它协调逐问建模、创新主张、引用核验、复现、独立审查、LaTeX 写作和最终提交；不预测或保证奖项。

## v10 的六个核心系统

1. Rule Engine：只执行带生效时间、官方来源与哈希的赛事规则档案。
2. Model Selection Engine：按小题选择 Evidence Profile，以强基线和可复核证据决定方案。
3. Innovation Claim Engine：支持“忠实问题表述”和“基线失败—最小改变”两条创新路径。
4. Scientific Review Engine：按题型路由科学、实现、统计、不确定性和主张审查。
5. Contest Paper Presentation Engine：用 Paper Payload 隔离内部控制语言，管理正文、图表、精度与篇幅。
6. Submission Finalizer：编译、渲染、交叉核对并按已核验规则执行 fail-closed 终审。

工作流采用五个阶段：`rule_verification → exploration → model_freeze → paper_freeze → submission`。默认使用 `standard`；`championship` 加强独立审查与稳健性，但不强制增加模型、统计段落或计算量。

## 配套 Skills

必需：`mathmodel-skill`、`citation-management`。

按题目路由：`statistical-analysis`、`uncertainty-and-units`、`scientific-critical-thinking`。数据驱动的论文图优先使用 `scipilot-figure-skill` 完成数据剖析、选图、出版级绘制和视觉自检闭环；`data-analytics:visualize-data` 负责通用设计、交互探索和第二视角 QA。流程图、机理图与网络示意图仍使用 TikZ/Graphviz/原生代码。八个 Skill 合作可以覆盖完整建模与论文流程，但仍需要参赛队员判断题意、核实当届规则、检查代码和数据、审阅引用、确认 AI 披露并完成正式提交。

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

当前公开实现结论只到 E0。写作规范另由用户本地 2022–2025 年 47 篇/2379 页优秀论文语料作描述性结构校准，方法与聚合计数见 `references/cumcm-corpus-evidence-2022-2025.md`；原论文、OCR 文本和逐篇卡不随仓库分发。该语料校准不等同于 E1 解题演练。

## 设计底线

- 创新不是模型数量或算法复杂度；融合本身没有创新信用。
- 搜索宽度只告警，不阻断；简单而充分的方案可以胜出。
- 规则、文献、数据、结果和重大审查发现必须由真实产物支持。
- 内部证据保持完整，最终论文不暴露任务、冻结、哈希或审计元语言。
- 最终论文以 LaTeX 为唯一真源，不做 Word/Markdown 格式转换。
- `final_report.json=pass` 只表示框架定义的技术门禁通过，不代表官方接受或获奖保证。
