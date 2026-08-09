# 数学建模竞赛总控 Skill

`orchestrate-math-modeling` 是面向 CUMCM/国赛和 MCM/ICM/美赛的证据驱动总控框架。它不承诺奖项，重点是让团队能够说明：为什么选这个模型、创新在哪里、结论凭什么成立、论文与提交规则是否真正通过。

## v9 的五个核心系统

- Competition Rule Engine：Profile v2 把每个硬规则绑定到当届官方来源、原文定位和本地快照哈希。
- Model Selection Engine：按小题记录强基线、候选、拟合前理由、拟合后证据、最终选择和淘汰理由；简单模型可以胜出。
- Innovation Claim Engine：只为已证明的 baseline failure 提出最小必要改变，并用先例、证伪、消融和论文落点支持。
- Scientific Review Engine：统一进行科学、统计和主张审查，critical/major 必须有真实证据产物。
- Submission Finalizer：不猜赛事规则，只执行 verified profile、验证状态、文件与哈希，直接构建 LaTeX。

工作流采用五个阶段：`rule_verification → exploration → model_freeze → paper_freeze → submission`。默认使用 `standard`；`championship` 加强独立审查与稳健性，但不强制增加模型或计算量。

## 配套 Skills

必需：`mathmodel-skill`、`citation-management`。

强烈建议：`statistical-analysis`、`uncertainty-and-units`、`scientific-critical-thinking`。

科研制图可选：`scientific-visualization`。推荐核验来源为 [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/scientific-visualization)；未安装时总控仍按内置的 CUMCM 图表规范工作，不把它设为硬依赖。

这六个 Skill 可以覆盖完整建模与论文流程，但仍需要参赛队员做题意判断、核实当届官方规则、检查代码和数据、审阅引用、确认 AI 披露并完成正式提交。

## 快速开始

```text
使用 $orchestrate-math-modeling 为这道国赛题建立总控工作区。先冻结三个小题的统一问题契约，再核验当届官方规则并生成带 source locator 和 hash 的 Competition Profile v2。每个小题先做强基线，只在真实失败证据支持时增加候选或创新改动；模型冻结后进行独立科学、统计和主张审查。论文只使用 LaTeX。
```

安装后 Skill 的详细执行规则见 `SKILL.md`。仓库地址：<https://github.com/Guzming66/orchestrate-math-modeling>

## 证据等级

- E0：实现通过本仓库自动化测试。当前覆盖 Profile v2 溯源、模型选择、创新最小性、科学审查、AI profile 驱动、迁移、溯源、匿名打包和 fail-closed 终审。
- E1：在公开历史题上完成可复现的结构化演练。
- E2：由不知道版本信息的独立评阅者比较论文质量。
- E3：多届真实赛事外部结果；仅作观察，不能把获奖归因于本 Skill。

当前公开结论只到 E0。仓库中的 benchmark 是离线质量评估工具，不输出获奖率，也不参与赛中终审。

## 设计底线

- 创新不是模型数量或算法复杂度。
- 融合模型本身没有创新信用。
- 搜索宽度只告警，不阻断。
- 规则、文献、数据、结果和 critical/major finding 必须有 artifact-backed evidence。
- 最终论文以 LaTeX 为唯一真源，不做 Word/Markdown 格式转换。
- `final_report.json=pass` 只表示本框架定义的技术门禁通过，不代表官方接受或获奖保证。
