# Competition Profile v2

## 目的

`compliance/competition_profile.json` 是 finalizer 唯一执行的赛事规则输入。不得用赛事名、题号或 `year >= N` 推断格式与提交要求。初始化和 v8 迁移后的 profile 都是 `unverified`。

## 三层结构

1. `sources`：每个官方来源保存稳定 `source_id`、官方 URL、本地快照、SHA-256、核验方法和时间。
2. `requirements`：只写可执行的论文、提交、AI 与额外产物要求。
3. `rule_bindings`：把每个非空、会被执行的 requirement 绑定到 `source_id + locator + evidence_sha256`。

`locator` 必须能让另一名队员在快照中找到原条款，例如 PDF 页码/章节、网页标题/段落或表格行。URL、搜索摘要、往届规则、博客和模型回答不能替代官方快照。

## Build 与 requirements 的边界

`build.latex_engine` 和 `build.main_document` 是本地执行配置，不是赛事知识。Finalizer 从这里取得编译方式，不按 `competition` 分支。

`requirements` 包含：

- `paper`：格式、页数、大小、纸张、目录和匿名；
- `submission`：支撑包要求及大小；
- `ai`：政策是否已检查、声明源文件及启用 marker、声明位置、逐处披露、工具引用、人工验证、详情源文件和官方文件名；
- `artifacts`：官方要求的额外产物及工作区路径、归档路径。

不适用的条款写 `null`，不要猜 `false`。所有非 `null` 可执行值都需要 binding；AI 的 `policy_checked=true` 也需要 binding。

## 核验步骤

1. 打开当届官方入口，保存页面/PDF 快照到 `audits/rules/`。
2. 记录 source artifact 的 SHA-256、核验方式和取得时间。
3. 逐条提取 requirement，并为每条添加准确 locator。
4. 第二名队员复核来源身份、版本、生效时间、条款解释和哈希。
5. 设置唯一 `profile_id`、`status=verified`、复核人和时间。
6. 运行 `python scripts/validate_competition_profile.py <workspace>`。
7. 官方页面更新、源 hash 改变或解释有争议时，将 profile 退回 `unverified` 并重做。

Schema 位于 `schemas/competition-profile.schema.json`。当前官方入口只可用于发现线索；最终规则必须在比赛当时重新核验。
