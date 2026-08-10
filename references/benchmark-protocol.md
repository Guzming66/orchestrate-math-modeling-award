# Innovation Claim Engine benchmark protocol

使用 `benchmarks/innovation_claim_cases.json` 中的官方历史题信号做去答案化评测；不向被测任务提供预期模型或本次重构结论。对旧版和新版使用相同题面、时间、工具、数据和盲评者。

每个 case 记录：有效且有证据的创新主张数、假创新数、模型组件数、相对基准增益覆盖、复现率、论文映射率、内部元语言泄漏率、自适应审查路由正确率、数学—实现漏洞检出率、论文表达盲评分和综合盲评质量。另保存每个 claim 的 semantic-fidelity/failure test、falsification、ablation、paper mapping 与 Presentation Firewall 原始 artifact。

所有 required metrics 必须逐 case 填写；scorer 对缺失字段、负值、越界率或越界盲评分 fail-closed，不能把缺失证据默认为 0 分后继续比较。

重点比较去掉“强制多路线、safe/stretch、类比数量”前后：

- 假创新率是否下降；
- 简单方案能否胜出；
- 增益是否能由创新开/关消融解释；
- 论文是否更清楚地回答“为什么必须这样改”；
- 确定性题是否停止生成无意义统计段落，统计题是否仍得到完整审查；
- freeze/hash/audit 等内部语言是否从论文消失但仍保留在证据台账；
- 数学定义与代码实现的隐含假设是否更早被发现；
- 图表、精度和篇幅是否把注意力放在建模思想与实际增益上；
- 复现与盲评是否至少不下降。

用 `python scripts/score_claim_benchmark.py <新版结果.json> --compare <旧版结果.json>` 只计算描述性差异。不得把小样本得分当作获奖概率或自动回归阈值；模型质量仍由盲评和 artifact 审核决定。
