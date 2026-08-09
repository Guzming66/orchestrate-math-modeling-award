# 最终提交控制

## 进入提交阶段前

1. `competition_manifest.json` 的 `workflow_stage` 已由队员明确改为 `submission`。
2. `competition_profile.json` 为 v2 verified，所有 active requirement 都有官方 source binding。
3. `model_selection.json` 对每个核心小题完成冻结。
4. Innovation Claim Engine 与论文创新映射通过。
5. `review_findings.json` 覆盖 scientific、statistical、claims；critical 已关闭，open major 不超 policy。
6. 引用、输入、结果和复现台账全部指向实际 artifact 且 hash 匹配。
7. 所有 blocking task 已完成或有明确、可审计的 waiver。

## LaTeX 与额外产物

Finalizer 从 profile 的 `build.latex_engine` 与 `build.main_document` 构建正文，不根据赛事名猜引擎。AI 声明、详情 PDF、支撑包、纸张、页数、大小和官方文件名只按 profile 执行。

Profile 的 `requirements.artifacts` 为每个必需产物定义：

- `artifact_id`
- `required`
- `source_path`
- `archive_path`

当支撑包被要求时，`submission/support_manifest.json` 必须把相同 `source_path` 映射到相同 `archive_path`。支撑包采用显式文件清单并进行路径、身份词、PDF 元数据、常见凭据、压缩文档内部文件和绝对用户路径扫描。

## 统一命令

```text
python scripts/finalize_submission.py <workspace>
```

Finalizer 调用专门 validators，验证状态与产物后才进行 submission-mode LaTeX build 和打包。上游阻断时跳过正式构建，防止产生“看起来可提交”的文件。

对 CUMCM，`validate_paper_question_coverage.py` 还会把冻结的核心小题与 `paper/generated/question_sections.tex` 一一对齐：少载、重复载入、章节缺失或仍为草稿均阻断。它只能证明“没有漏掉章节”，不能替代对每问是否真正作答的科学与主张审查。

只有 `audits/submission/final_report.json` 为 `pass` 时才生成 `submission/submission_manifest.json`。Manifest 保存论文、AI 详情和支撑包的最终 hash。队员仍需逐页查看 PDF、核对上传界面与官方截止时间，并亲自完成提交。
