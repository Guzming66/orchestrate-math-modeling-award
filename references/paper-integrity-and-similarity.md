# 论文完整性、AI 使用覆盖与相似度预检

本页只定义可复核的质量与诚信检查，不推断作者身份，不输出“AI 概率”，也不承诺通过任何官方查重系统。

## 五类论文接缝

1. **结构同质化**：各问可以共享符号和接口，但不要机械复制完全相同的标题序列、首段和结尾。结构应服从任务：推导问、数据问、优化问和开放问的证据载体本来就不同。
2. **推导跳步**：出现“显然”“容易得到”“经过变换可得”并紧接非平凡公式时，补足变换、引用、边界条件或数值近似依据。不要为了消除告警改写连接词却保留逻辑缺口。
3. **公式—代码—结果断链**：把每个关键公式/约束映射到实现文件、函数或符号、最小测试 artifact 和 `result_id`。一个 trace 可以覆盖一组同一职责的公式，不必逐行登记。
4. **齐全但空泛**：删除“结果良好、精度较高、鲁棒性较强”等无局部指标、比较或边界的句子；保留时必须就地给数值、区间、对照配置或失效条件。
5. **聊天残留**：正文不得含助手自称、用户请求引用、聊天结束语、工具引用标记、Codex 指令或 Markdown 围栏。只阻断高置信度残留，不把常见学术连接词当作 AI 证据。

运行：

```text
python scripts/validate_paper_integrity.py <workspace>
```

## AI 使用双向覆盖

`compliance/ai_usage_ledger.csv` 记录一次实质使用；`compliance/ai_artifact_inventory.csv` 逐文件回答“该交付物是否使用 AI”。终审核对两个方向：

- 每个 ledger `use_id` 至少映射到一个 inventory artifact；
- 每个 `ai_used=true` artifact 必须映射到已存在的 `use_id`；
- `paper/` 与 `support/` 下所有交付文件都必须分类，不能靠不登记逃过检查；
- `sha256` 必须匹配当前文件，修改文件后重新人工核验并更新记录；
- `human_verification` 写实际复核动作，如推导重算、代码重跑、图表点值抽查或文字重写，不写空泛“已检查”。

该机制提高漏填可见性，但无法从文件内容证明一个从未登记的外部会话不存在；最终完整性仍由团队确认。

## 本地相似度预检

将优秀论文 OCR 全文和可复用写作模板复制到 `audits/similarity/corpus/`，再登记到 `reference_corpus.csv`：

- `source_type=excellent_paper`：检查无意复用历史论文表述；
- `source_type=template`：检查固定模板正文进入新论文；
- 保存实际文本的相对路径、SHA-256 与 `verified` 状态；原论文/OCR 不必随公开 Skill 仓库分发。

可用登记脚本复制文本、计算哈希并去重：

```text
python scripts/register_similarity_corpus.py <workspace> <ocr-file-or-folder> --type excellent_paper
python scripts/register_similarity_corpus.py <workspace> <template-file-or-folder> --type template
```

验证器移除公式块、LaTeX 结构、引用、网址、数字、英文字母、通用章节名后，比较规范化中文连续 24 字片段。模板命中即阻断；同一优秀论文出现 3 个互不重叠命中时阻断并要求人工复核。报告给出论文文件、来源 ID、字符位置和重合片段。

```text
python scripts/validate_similarity_precheck.py <workspace>
```

边界：这是偏保守的精确重合预检，不检测语义改写，不生成官方相似度百分比，也不能代替学校或赛事查重。题面原文较长时，应另行登记题面文本并人工排除题面导致的命中。
