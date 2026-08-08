# 最终提交控制

## 任务与赛程

在 `shared/task_board.csv` 为每个任务填写负责人、依赖、截止时间、冻结时间、失败后备方案、交付物和证据。状态只使用 `pending`、`in_progress`、`done`、`blocked`、`waived`。

```text
python <skill>/scripts/validate_task_board.py <workspace>
python <skill>/scripts/validate_task_board.py <workspace> --final
```

普通检查报告未知依赖、环、越序完成和逾期；最终检查还要求所有阻断任务关闭并具备负责人、时间、后备方案和证据。

## 数据与结果溯源

- `audits/data/data_provenance.csv` 必须覆盖 `inputs/original/` 与 `inputs/external/` 的每个文件。记录来源、授权/条款、取得时间、原始和当前 SHA-256、使用字段、状态及复核人。
- 原始输入不得在原位变换；清洗产物写入其他目录，并在 `transform_script` 中指回生成脚本。
- `synthesis/result_manifest.csv` 覆盖摘要、结论和关键表图中的核心结果。记录正文位置、值、单位、文件、生成器、命令、输入 ID、随机种子、环境快照、SHA-256 和复核人。
- 无量纲结果把单位明确写为 `dimensionless`；确定性程序把种子写为 `deterministic`，不要留空。

运行 `snapshot_environment.py` 生成 Python 包锁定文件与 LaTeX/PDF 工具版本。最终终审会重新生成快照并核对结果台账引用的环境文件存在。

## 八道门禁状态

在 `audits/gate_status.json` 中把 G0—G7 逐项写为 `pass`，并填写独立复核人、ISO 时间、证据路径和未关闭阻断项。不能用空字符串、口头确认或自评分代替证据。

`compliance/official_sources.json` 必须把 `status` 改为 `verified`，填写核验人与时间，并在 `sources` 中保存每个实际采用的官方页面或 PDF 的类型、URL、版本和 SHA-256。候选链接不等于已核验来源。

## 支撑包与匿名扫描

1. 在 `compliance/anonymity_terms.txt` 每行填写一个禁止出现的真实姓名、学校、赛区、用户名或队伍别名。
2. 在 `submission/support_manifest.json` 逐文件列出要进入支撑包的相对路径；不使用目录通配符，也不重新打包原始赛题附件。
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

终审器执行环境快照、任务板最终检查、DOI 验证、官方来源、文献、输入、结果、复现、证据矩阵、G0—G7、LaTeX 提交构建和 CUMCM 支撑包扫描。通过后写出 `submission/submission_manifest.json`，其中保存论文和支撑包 SHA-256；任一检查失败时只写阻断报告，不宣称可提交。
