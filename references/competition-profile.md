# Versioned competition profile

## 原则

不得用 `year >= N` 推断规则。每个比赛工作区维护 `compliance/competition_profile.json`，只执行经当届官方来源快照核验的 profile。初始化文件默认 `unverified`；Stage 0、8、9 重新核验，官方通知变化时创建新 `profile_id`，不静默覆盖旧版本。

## Profile 结构

字段契约见 `schemas/competition-profile.schema.json`；运行时 validator 只依赖 Python 标准库，并执行相同的关键约束。

- 身份：`schema_version`、`profile_id`、`competition`、`edition`；
- 生效与核验：`effective_from`、`effective_to`、`status`、`verified_at`、`verified_by`；
- 官方来源：每项保存 `kind`、`url`、`artifact_path`、`sha256`、`command_or_check`、`checked_at`；
- `requirements.paper`：PDF、首页/总页数/正文页数、文件大小、纸张、目录和匿名；
- `requirements.submission`：支撑包是否需要及大小；
- `requirements.ai`：政策是否核验、独立使用声明及位置、正文逐处披露、AI 工具引用、人工核验、详情 PDF 和官方文件名。不同赛事/届次要求不同；不得把“详情 PDF”误推成“必须有独立声明”，也不得反过来遗漏正文标注。

规则网页或 PDF 快照放在 `audits/rules/`。`artifact_path` 必须指向工作区内实际文件，哈希必须匹配。URL、标题或“已核验”文字不能代替快照证据。

## 工作流

1. 打开当届官方入口；保存页面/PDF 快照及取得时间。
2. 逐条提取可执行要求，不从往届 profile 复制未知项。
3. 由第二人核对来源身份、版本、生效时间和具体条款。
4. 填写 profile，设置唯一 `profile_id` 和 `status=verified`。
5. 运行 `python <skill>/scripts/validate_competition_profile.py <workspace>`。
6. 官方页面更新或 source hash 改变时，profile 立即失效并重新核验。

当前权威入口示例仅用于发现：CUMCM 使用组委会官网 `mcm.edu.cn`；MCM/ICM 使用 COMAP `contest.comap.com` 当届 instructions。最终以比赛当时官方页面为准。
