# v14 执行完整性

## 题面是唯一范围权威

把原题与附件放入 `inputs/original/`，计算哈希后填写 `shared/problem_contract.json`。每问必须包含题面定位、原始任务动词、所需答案、明确产物、输入、结构化上游依赖、精度与约束。`problem_contract.md` 只供阅读；JSON 决定模型选择、逐问 LaTeX 和终审覆盖。

运行：

`python scripts/validate_problem_contract.py <workspace> --final`

## 冻结跨小问接口

先在 `synthesis/result_manifest.csv` 为每个结果填写 `question_id`。若 Q2 沿用 Q1，则在 `shared/question_interfaces.json` 登记 Q1→Q2、实际使用的 result ID、每个结果的规范化 fingerprint，以及证明 Q2 已按该版本求解的 artifact。

结果 fingerprint 覆盖数值、单位、命令、输入、随机种子、环境和结果文件哈希。任何字段变化都会使下游接口 stale。不要仅写“沿用第一问结果”。

运行：

`python scripts/validate_question_interfaces.py <workspace> --final`

## 让终审器实际复现

把 `audits/reproduction/reproduction_status.json` 改为 `ready`，填写：

- `runner.argv`：参数数组，不写 shell 管道或重定向；
- `runner.working_directory`：相对工作区目录；
- `runner.clean_paths`：运行前必须从隔离副本删除的结果文件或目录；
- `expected_artifacts`：覆盖 result manifest 的全部结果路径与当前 SHA-256；
- 复核人、时间和未关闭问题。

Finalizer 会复制工作区到临时目录、删除 clean paths、执行 argv，再核对新产物。源工作区不会被清理或改写。隔离执行报告位于 `audits/reproduction/execution_report.json`。

## 逐页验收最终 PDF

第一次运行 Finalizer 会完成提交模式编译、渲染 `audits/presentation/final_pdf_pages/page-NNN.png`，并生成 `final_pdf_visual_review.json`。逐页检查：

1. 裁切、遮挡、越界与异常空白；
2. 中文字体、数学符号、负号和乱码；
3. 公式、表格、图注、图例、分辨率与跨页；
4. 页码、匿名性、元数据可见项与最终次序。

每项写 `pass`，填写复核人与 ISO 时间后再次运行 Finalizer。PDF 二进制哈希变化时全部页面记录重置；在同一 PDF 中，渲染页面哈希变化也会使对应页失效。这样复核既绑定最终文件，也绑定逐页视觉内容。

## 重大审查问题

`critical` 必须 closed。`major/open` 一律阻断。只有 standard policy 允许的少量 `major/accepted_risk` 可以保留，并且必须填写 `risk_owner`、`impact_scope`、`fallback` 和 artifact-backed evidence；championship 默认允许数量为 0。
