# 最终提交控制

## 任务与赛程

在 `shared/task_board.csv` 为每个任务填写负责人、依赖、截止时间、冻结时间、失败后备方案、交付物和证据。状态只使用 `pending`、`in_progress`、`done`、`blocked`、`waived`。

```text
python <skill>/scripts/validate_task_board.py <workspace>
python <skill>/scripts/validate_task_board.py <workspace> --final
```

普通检查报告未知依赖、环、越序完成和逾期；最终检查还要求所有阻断任务关闭并具备负责人、时间、后备方案和证据。

## Innovation Claim Engine

在正式模型分支启动前运行：

```text
python <skill>/scripts/validate_innovation_portfolio.py <workspace>
```

候选数量、axis、scout 和跨领域类比只作为探索告警。阻断条件是晋级 claim 缺少强基线失败证据、最小改变、最近先例、falsification、必要消融、Critic 关闭或 artifact/hash。至少一个 `primary` claim 通过即可，不强制 safe/stretch 或多个模型。

论文完成后运行 `python <skill>/scripts/validate_paper_innovation.py <workspace>`，把 promoted claim 映射到结果、引用、LaTeX 章节和锚点；未映射的强创新措辞阻断。

## 数据与结果溯源

- `audits/data/data_provenance.csv` 必须覆盖 `inputs/original/` 与 `inputs/external/` 的每个文件。记录来源、授权/条款、取得时间、原始和当前 SHA-256、使用字段、核验命令/检查、核验时间、状态及复核人。
- 原始输入不得在原位变换；清洗产物写入其他目录，并在 `transform_script` 中指回生成脚本。
- `synthesis/result_manifest.csv` 覆盖摘要、结论和关键表图中的核心结果。记录正文位置、值、单位、文件、生成器、命令、输入 ID、随机种子、环境快照、SHA-256 和复核人。
- 无量纲结果把单位明确写为 `dimensionless`；确定性程序把种子写为 `deterministic`，不要留空。

运行 `snapshot_environment.py` 生成 Python 包锁定文件与 LaTeX/PDF 工具版本。最终终审会重新生成快照并核对结果台账引用的环境文件存在。

## 八道门禁状态

在 `audits/gate_status.json` 中把 G0—G7 逐项写为 `pass`，并填写独立复核人、ISO 时间、未关闭阻断项，以及 `artifact_path + sha256 + command_or_check + checked_at` 证据对象。不能用字符串路径、口头确认或自评分代替证据。

`compliance/competition_profile.json` 必须通过 `validate_competition_profile.py`。Profile 与 manifest 的赛事/届次一致，并包含带本地快照、SHA-256、检查步骤和时间的官方来源。Finalizer 只执行该 profile，不从年份或旧模板推断要求。

## 支撑包与匿名扫描

1. 在 `compliance/anonymity_terms.txt` 每行填写一个禁止出现的真实姓名、学校、赛区、用户名或队伍别名。
2. 在 `submission/support_manifest.json` 逐文件列出要进入支撑包的相对路径；字符串项保持原路径，对官方要求固定压缩包内名称的文件使用 `{ "source": "工作区相对路径", "archive_path": "包内路径" }`。不使用目录通配符，也不重新打包原始赛题附件。
3. 运行：

```text
python <skill>/scripts/package_submission.py <workspace> --require-paper
```

脚本扫描路径、文本、PDF 可见内容与元数据、图片元数据、压缩文档内部文件、常见密钥和用户绝对路径；随后生成确定性 ZIP，检查大小并保存文件及归档哈希。邮件地址和非空图片元数据产生人工复核警告；身份词、凭据、PDF 作者和路径越界直接阻断。

## 统一终审

最终只运行：

```text
python <skill>/scripts/finalize_submission.py <workspace>
```

终审器先执行 preflight、环境快照、任务板、competition profile、Innovation Claim Engine、论文创新映射、DOI/文献、AI 使用台账、输入、结果、复现和 artifact-backed G0—G7。任一上游硬门禁失败时跳过 submission build 与打包，避免产生看似可提交的 PDF；上游全通过后才直编 LaTeX、执行 profile 版面门禁并扫描支撑包。全部通过后写出 `submission/submission_manifest.json`。
