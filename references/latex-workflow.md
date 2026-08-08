# 直接 LaTeX 论文工作流

## 目录

1. 单一真源
2. 目录和所有权
3. 构建循环
4. 结果、图表与公式
5. 引用与额外声明
6. CUMCM 附录与支撑材料同步
7. 提交检查

## 单一真源

只把 `paper/main.tex`、`paper/sections/*.tex`、`paper/generated/*.tex`、`paper/references.bib` 和 `paper/figures/` 视为论文源。最终 PDF 必须从这些文件直接构建。

允许分支用 Markdown 记录推理，但不要把 Markdown、Word、HTML 或 Notebook 导出物转换成最终正文。不要使用 Pandoc，也不要让 `$mathmodel-skill` 的 `render_paper.py` 组装论文。若必须导入旧材料，人工迁移到一个隔离的 `.tex` 章节，逐段核对公式、引用和特殊字符，再删除平行格式。

## 目录和所有权

```text
paper/
  main.tex                  仅论文总编修改
  generated/metadata.tex    仅论文总编修改
  generated/*.tex           程序生成表格与数值宏
  sections/*.tex            每个写作任务独占一个文件
  figures/                  程序生成的 PDF/PNG 图片
  references.bib            仅文献管理员或论文总编修改
  build/                    编译输出和 build_report.json
```

不要让两个任务同时编辑同一个 `.tex` 或 `.bib` 文件。章节任务只返回分配文件的完整内容和所需引用键；论文总编负责合并引用库与主文件。

## 构建循环

国赛使用 XeLaTeX，美赛使用 pdfLaTeX。优先运行：

```text
python <skill>/scripts/build_latex.py <workspace>/paper --competition CUMCM --mode draft
python <skill>/scripts/build_latex.py <workspace>/paper --competition MCM --mode submission
```

构建工具调用 `latexmk`，自动完成必要的 BibTeX 轮次，不依赖 Pandoc。草稿模式允许明确的标题和队号占位符；提交模式将其视为阻断项。

对 CUMCM 主论文，提交模式还检查 PDF 为 A4、文件不超过 20 MB、Author 元数据为空、源码没有 `\tableofcontents`，并要求模板输出正文页数标记。模板自身强制摘要只占第一页和正文不超过 30 页。自动检查不能替代匿名与附件人工审计。

每次新增公式、表格、图片、引用或章节后重新构建。不要等到最后才发现宏包、浮动体或交叉引用问题。读取 `paper/build/build_report.json`，修复所有 `errors`；逐项判断 `warnings`。

## 结果、图表与公式

- 把可复现数值写成 `paper/generated/results.tex` 中的 LaTeX 宏，再在正文引用；不要在多处手抄数字。
- 把程序生成的表格写成不含 `table` 外壳的 `.tex` 片段，由正文负责标题、标签和浮动位置。
- 优先使用矢量 PDF 图片；栅格图使用足够分辨率并嵌入字体。所有坐标轴、图例和单位必须在最终页面尺寸下可读。
- 为公式、图、表和章节设置稳定且唯一的标签前缀，如 `eq:`、`fig:`、`tab:`、`sec:`。
- 避免直接使用 Unicode 数学符号代替 LaTeX 命令，避免复制不可见空格和特殊连字符。
- 对宽表优先重构列、减少无意义小数或转为附录，不用整体缩小到不可读。

## 引用与额外声明

只维护一个 `paper/references.bib`。完整执行 [citation-integrity-audit.md](citation-integrity-audit.md)：使用 `$citation-management` 检查 BibTeX、重复项和 DOI 可解析性，人工核对权威题录、原文支持、正式版本及撤稿/更正状态。搜索结果页和 AI 回答只能用于发现来源。提交前不允许出现 `?`、未定义 citation、未使用条目或没有原文定位的核心主张。

在 Stage 8 和提交前运行：

```text
python <citation-management>/scripts/validate_citations.py <workspace>/paper/references.bib --check-dois --report <workspace>/audits/citations/metadata_report.json
```

把每条正文主张与引用键、原文定位和审计状态写入 `audits/citations/citation_ledger.csv`。自动报告只能证明格式和标识符可解析，不能证明文献身份一致或正文主张受到支持。

首次加入正文引用时，创建 `paper/generated/bibliography.tex`，内容保持为：

```tex
\bibliographystyle{unsrt}
\bibliography{references}
```

没有引用时不要创建这个文件，从而避免空 BibTeX 任务引发无意义的构建错误。

若当届规则要求 AI 或其他工具使用说明，直接用相应 `.tex` 模板生成 PDF；不要先生成 Word 或 Markdown 再转换。本 Skill 不增加超出官方规则的披露要求。

需要生成国赛 AI 使用说明时，可运行：

```text
python <skill>/scripts/build_latex.py <workspace>/paper --competition CUMCM --main ai_usage_details.tex --mode submission
```

按当届要求命名、放置和提交生成的 `paper/build/ai_usage_details.pdf`。美赛的相应内容可写入 `paper/sections/99_ai_report.tex`，由主论文按当届版面规则编译。

## CUMCM 附录与支撑材料同步

2026 格式规范要求论文附录包含支撑材料文件列表和全部完整、可运行的源程序，支撑压缩包也应包含同版本程序。不要只在附录写“代码见附件”。

- 从冻结的 `branches/` 或统一代码目录生成一次只读提交快照。
- 在 `paper/sections/90_appendix.tex` 先列文件清单、入口命令、依赖、随机种子和对应正文小节，再用 `\lstinputlisting` 或等价 LaTeX 方式纳入完整文本源程序。
- 对 Notebook、Excel、SPSS 等保留可运行文件，并按官方要求在论文附录提供完整代码或交互命令；不要用截图代替文本。
- 支撑 ZIP/RAR 只放与论文一致的代码、外部数据、必要中间结果和当届要求的额外材料；排除原始赛题附件、临时缓存、环境目录、身份、密码与令牌。
- 比较论文附录清单、支撑包清单和复现日志。任一文件缺失或版本不一致即阻断。

## 提交检查

1. 填完 `final-submission-controls.md` 的台账与门禁后，运行 `finalize_submission.py`；不要单独把一次 LaTeX 编译成功当成终审通过。
2. 确认编译报告无错误，无未解析引用、缺字、占位符、严重超宽、非 A4、匿名元数据和文件大小违规。
3. 用 `pdfinfo` 复核页数、纸张尺寸和 PDF 元数据，并用文件系统复核大小。
4. 用 `pdftoppm` 渲染全部页面，不只抽查第一页。
5. 逐页检查裁切、重叠、孤行、空白页、浮动体漂移、公式编号、图表清晰度、页眉页码和匿名信息。
6. 对照当届官方规则核对页数计数口径和额外材料位置。
7. 对 CUMCM 检查附录源程序与支撑包同版本、各文件匿名且支撑包不超过 20 MB；当届要求额外材料时按官方规则核对。
8. 确认 `final_report.json` 与 `submission_manifest.json` 均为通过状态并保存论文/支撑包哈希；不提交临时辅助文件。
