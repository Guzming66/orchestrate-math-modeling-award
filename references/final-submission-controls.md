# 最终提交控制

## 进入提交阶段前

1. `competition_manifest.json` 的 `workflow_stage` 已由队员明确改为 `submission`。
2. `competition_profile.json` 为 v2 verified，所有 active requirement 都有官方 source binding。
3. `shared/problem_contract.json` 已把每个小题连接到原题文件哈希和准确定位；schema v2 `model_selection.json` 与其顺序一致，并通过对应 Evidence Profile。
4. `synthesis/global_claim_certificates.json` 已覆盖 first/earliest/global minimum/global maximum/optimal/full-domain safety 等强主张；每张证书的定义域、覆盖/候选划分、端点/非光滑/内部检查、排除论证和 artifact 均完整，或根状态有经核对的 `not_applicable` 理由。
5. `review_route.json` 覆盖每问；implementation-assumption check 通过，统计审查未被错误跳过。
6. Innovation Claim Engine 与论文创新映射通过。
7. schema v4 `paper_payload.json` 为 ready，和冻结小题一致；`paper/main.tex → generated/question_sections.tex → qNN.tex` 的实际输入闭包完整，每问的 `answer_anchor` 与 `validation_anchor` 都真实存在于本问 `qNN.tex`；逐条几何主张已绑定公式和机制图/具体免图理由；所有图的最终宽度、最小字号和最终尺寸复核均闭合，量化图另有样本/像素与过绘处理。
8. schema v3 `review_findings.json` 覆盖 scientific、implementation、statistical、uncertainty、claims；每个 pass 有论文锚点、具体检查、证伪/边界攻击、outcome 和真实 artifact；critical/open major 已关闭，accepted major 不超 policy 且有责任人、影响范围和后备方案。
9. 引用、输入和结果台账全部指向实际 artifact 且 hash 匹配；跨问依赖的上游结果 fingerprint 未过期。
10. 所有 blocking task 已完成或有明确、可审计的 waiver。
11. `paper_integrity_report.json` 通过；关键公式/约束已映射到实现、测试和结果。
12. `ai_artifact_inventory.csv` 覆盖全部论文/支撑交付物，并与 AI 使用台账双向一致。
13. 本地优秀论文与实际写作模板已登记并完成相似度预检；所有命中均已人工复核。

## LaTeX 与额外产物

Finalizer 从 profile 的 `build.latex_engine` 构建 `paper/main.tex`，不根据赛事名猜引擎；当前 profile v2 的 `build.main_document` 必须精确为 `main.tex`。正文构建报告还必须明确给出 `submission_eligible=true`。AI 声明、详情 PDF、支撑包、纸张、页数、大小和官方文件名只按 profile 执行。

`qNN_standalone.pdf` 只作为逐问交付候选：必须有通过的 `build_report_qNN_standalone.json`，但其 `submission_eligible` 永远为 false。赛事正文只能由 `paper/main.tex` 生成；不得把独立小问稿改名后提交。

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

Finalizer 调用专门 validators，在隔离副本实际执行复现命令并核对结果哈希，然后才进行 submission-mode LaTeX build。上游阻断时跳过正式构建，防止产生“看起来可提交”的文件。

对 CUMCM，`validate_paper_question_coverage.py` 还会把冻结的核心小题与 `paper/generated/question_sections.tex` 一一对齐：少载、重复载入、章节缺失、仅有标题或仍为草稿均阻断。它只能证明“没有漏掉章节”，不能替代对每问是否真正作答的科学与主张审查。

第一次成功构建后，Finalizer 会渲染全部页面并生成 schema v2 `audits/presentation/final_pdf_visual_review.json`；此时通常仍为 block。队员逐页核对裁切、字体/符号、公式/表图、图形最终尺寸与密度、浮动体/页面平衡、页码/匿名性，并确认记录中的自动 `page_layout_metrics` 与当前构建报告一致。下方空白比例超过 45% 的页面必须在修复无意留白后，或明确标记为 `intentional_end_matter / intentional_structure` 并写具体理由；未触发页面必须为 `not_flagged`。再次运行 Finalizer。PDF 二进制哈希变化时全部复核失效；页面像素哈希或自动布局指标变化也会使对应页失效。

只有 `audits/submission/final_report.json` 为 `pass` 时才生成 `submission/submission_manifest.json`。Manifest 保存论文、AI 详情和支撑包的最终 hash。队员仍需核对上传界面与官方截止时间，并亲自完成提交。
