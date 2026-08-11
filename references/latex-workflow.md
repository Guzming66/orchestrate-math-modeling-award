# 直接 LaTeX 论文工作流

## 目录

1. 单一真源
2. 目录和所有权
3. 构建循环
4. 独立小问交付
5. 结果、图表与公式
6. 引用与额外声明
7. CUMCM 附录与支撑材料同步
8. 提交检查

## 单一真源

只把 `paper/main.tex`、`paper/sections/*.tex`、`paper/generated/*.tex`、`paper/references.bib` 和 `paper/figures/` 视为论文源。最终 PDF 必须从这些文件直接构建。论文手先完整读取 [paper-presentation-engine.md](paper-presentation-engine.md)，以已标记 `ready` 的 `synthesis/paper_payload.json` 为主要科学输入，不从 audits 或任务日志复制正文措辞。

允许分支用 Markdown 记录推理，但不要把 Markdown、Word、HTML 或 Notebook 导出物转换成最终正文。不要使用 Pandoc，也不要让 `$mathmodel-skill` 的 `render_paper.py` 组装论文。若必须导入旧材料，人工迁移到一个隔离的 `.tex` 章节，逐段核对公式、引用和特殊字符，再删除平行格式。

## 目录和所有权

```text
paper/
  main.tex                  仅论文总编修改
  generated/metadata.tex    仅论文总编修改
  generated/question_sections.tex  按实际小题载入独立章节
  generated/*.tex           程序生成表格与数值宏
  sections/*.tex            每个写作任务独占一个文件
  sections/questions/qNN.tex 每个小题独占一个文件
  figures/                  程序生成的 PDF/PNG 图片
  references.bib            仅文献管理员或论文总编修改
  build/                    编译输出和 build_report.json
```

不要让两个任务同时编辑同一个 `.tex` 或 `.bib` 文件。章节任务只返回分配文件的完整内容和所需引用键；论文总编负责合并引用库与主文件。

CUMCM 不默认创建独立“问题重述”“符号说明”“模型评价与推广”和重复结论章。把任务关系写入 `01_task_analysis.tex`，把真正使用的假设、数据处理和核心符号合并到 `02_foundation.tex`，一次性符号在首次出现处定义，再由 `generated/question_sections.tex` 载入逐问章节。全局验证、跨问综合、AI 声明和附录均为条件内容，只在证据或 verified profile 要求时出现。该取舍由 [cumcm-corpus-evidence-2022-2025.md](cumcm-corpus-evidence-2022-2025.md) 校准；具体语言与制图规则见 [cumcm-paper-writing-and-figures.md](cumcm-paper-writing-and-figures.md)。

## 构建循环

从当前 Competition Profile v2 的 `build.latex_engine` 读取引擎。不要根据赛事名或年份推断。示例：

```text
python <skill>/scripts/build_latex.py <workspace>/paper --engine xelatex --mode draft
python <skill>/scripts/build_latex.py <workspace>/paper --engine pdflatex --mode submission
```

构建工具调用 `latexmk`，自动完成必要的 BibTeX 轮次，不依赖 Pandoc。草稿模式允许明确的标题和队号占位符，但构建报告把产物标记为 `review_only` 并逐项告警；不得把它称为最终稿。提交模式将占位符、空章节和未完成标记视为阻断项。

构建器只负责直编 LaTeX、通用占位符/日志检查并报告页数、正文起点、纸张、大小和元数据。`finalize_submission.py` 只按已核验 `competition_profile.json` 执行纸张、页数、大小、目录、匿名性和附加材料门禁。自动检查不能替代匿名与附件人工审计。

每次新增公式、表格、图片、引用或章节后重新构建。不要等到最后才发现宏包、浮动体或交叉引用问题。读取 `paper/build/build_report.json`，修复所有 `errors`；逐项判断 `warnings`。

## 独立小问交付

`qNN_standalone.pdf` 只用于逐问复核和合并前交付，不是赛事提交论文。它必须继续使用正式小问章节 `sections/questions/qNN.tex`，并通过统一构建器：

```text
python <skill>/scripts/build_latex.py <branch>/paper --engine xelatex --main qNN_standalone.tex --mode submission
```

裸 `xelatex` 只允许临时定位编译错误；由它产生且没有配套 `build_report_qNN_standalone.json` 的 PDF 不得交付。通过的小问报告标记为 `question_handoff_candidate` 和 `handoff_eligible=true`，同时保存 PDF 哈希；`submission_eligible` 始终为 false。

独立稿不设机械页数目标。构建器改为检查实质职责：任务/判定、模型/推导、直接结果、验证/边界必须存在；比较性验证若涉及网格、步长、复算、扰动、对照或消融，必须落成有标签的表或图，不能压缩成一段“均通过”。对多页独立稿，末页正文只占页面高度不足 55% 时阻断交付，先调整浮动体和章节组织；不要用题面复述、算法名或泛化优缺点填白。

## 结果、图表与公式

- 把可复现数值写成 `paper/generated/results.tex` 中的 LaTeX 宏，再在正文引用；不要在多处手抄数字。
- 把程序生成的表格写成不含 `table` 外壳的 `.tex` 片段，由正文负责标题、标签和浮动位置。
- 优先使用矢量 PDF 图片；栅格图使用足够分辨率并嵌入字体。所有坐标轴、图例和单位必须在最终页面尺寸下可读。
- 有源数据的量化图优先使用 `$scipilot-figure-skill` 完成数据剖析、论点驱动选图、最终尺寸绘制、程序自检、PNG 视觉复核、回改和矢量导出；`$data-analytics:visualize-data` 用于通用设计、交互探索和第二视角 QA。概念、流程、机理与网络图继续使用 TikZ/Graphviz/原生代码。SciPilot 不可用时按 [cumcm-paper-writing-and-figures.md](cumcm-paper-writing-and-figures.md) 执行同等检查。
- 图的生成脚本必须记录所用解释器与库版本；若 SciPilot 安装目录含 `.venv/Scripts/python.exe`，统一用该解释器运行其脚本。先在源代码中完成版面调整，再用 `export_figure(..., tight=False)` 导出正式矢量 PDF，避免 tight bounding box 改写既定物理尺寸；紧边界 PNG 仅作为视觉预览。最终只将通过 `check_figure.py --strict` 和实际 LaTeX 页面复核的 PDF/必要 PNG 纳入 `paper/figures/`。
- 每幅图登记 `mechanism / data / diagnostic / decision` 中一个主要证据职责；删除装饰性流程图、重复表格内容的图和没有参与论证的输出。
- 依赖空间几何、视线、遮蔽、可见性、投影、碰撞、坐标系或轨迹关系的小题必须登记一幅 `mechanism` 图；在 `presentation_plan.mechanism_visual_must_show` 列出图中必须同时出现的对象与关系。图与公式使用同一符号和坐标方向，结果曲线不能代替几何解释图。
- 每问把最强验证落到真实 `\label`：段落、式、表或图均可。正文至少写清比较对象、配置/容差、观察差异和结论边界，不能只引用内部复算或“证书通过”。
- 为公式、图、表和章节设置稳定且唯一的标签前缀，如 `eq:`、`fig:`、`tab:`、`sec:`。
- 避免直接使用 Unicode 数学符号代替 LaTeX 命令，避免复制不可见空格和特殊连字符。
- 对宽表优先重构列、减少无意义小数或转为附录，不用整体缩小到不可读。
- 先比较求解器误差、输入/参数不确定性、模型形式误差和题目要求精度；正文只显示足以支持答案位数的数值精度，机器精度留在审计台账。

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

若当届规则要求 AI 或其他工具使用说明，直接用相应 `.tex` 模板生成 PDF；不要先生成 Word 或 Markdown 再转换。把实质使用登记到 `compliance/ai_usage_ledger.csv`，并按 profile 检查正文锚点、工具引用、人工修改/核验、交互证据和官方文件名。本 Skill 不把某届或某赛事的披露位置套用到另一届。

需要生成 profile 指定的独立 AI 使用说明时，用相同 profile 引擎和 `details_source` 文件名运行：

```text
python <skill>/scripts/build_latex.py <workspace>/paper --engine xelatex --main ai_usage_details.tex --mode submission
```

最终器会按 verified profile 的 `details_source` 构建，再按 `details_filename` 命名；是否进入支撑包及包内路径由 `requirements.artifacts` 与支撑清单决定。

## CUMCM 附录与支撑材料同步

当已核验 profile 及其官方快照要求论文附录包含支撑材料文件列表和完整、可运行的源程序时，支撑压缩包也必须包含同版本程序。不要把某届历史要求静默继承到下一届。

- 从冻结的 `branches/` 或统一代码目录生成一次只读提交快照。
- 仅当 verified profile 要求时，在 `paper/sections/90_appendix.tex` 先列文件清单、入口命令、依赖、随机种子和对应正文小节，再用 `\lstinputlisting` 或等价 LaTeX 方式纳入完整文本源程序；如果 profile 只要求独立支撑包，就不要在论文里重复整份代码；如果 profile 明确要求代码随正文装订，则不得以“精简论文”为由省略。否则保持该文件为空，不生成附录标题。
- 对 Notebook、Excel、SPSS 等保留可运行文件，并按官方要求在论文附录提供完整代码或交互命令；不要用截图代替文本。
- 支撑 ZIP/RAR 只放与论文一致的代码、外部数据、必要中间结果和当届要求的额外材料；排除原始赛题附件、临时缓存、环境目录、身份、密码与令牌。
- 比较论文附录清单、支撑包清单和复现日志。任一文件缺失或版本不一致即阻断。

## 提交检查

1. 先运行 `validate_paper_presentation.py`，再填完 `final-submission-controls.md` 的台账与门禁并运行 `finalize_submission.py`；不要单独把一次 LaTeX 编译成功当成终审通过。
2. 确认编译报告无错误，并由 profile validator 确认未解析引用、缺字、占位符、严重超宽、纸张、匿名元数据、页数和文件大小均符合当届要求。
3. 用 `pdfinfo` 复核页数、纸张尺寸和 PDF 元数据，并用文件系统复核大小。
4. 用 `pdftoppm` 渲染全部页面，不只抽查第一页。
5. 逐页检查裁切、重叠、孤行、空白页、浮动体漂移、大面积无意留白、空标题、公式编号、图表清晰度、页眉页码和匿名信息；图应尽量紧跟首次引用。
6. 对照当届官方规则核对页数计数口径和额外材料位置。
7. 对照已核验 profile 检查附录、支撑包、匿名性和大小；当届要求额外材料时按官方快照核对。
8. 确认 `final_report.json` 与 `submission_manifest.json` 均为通过状态并保存论文/支撑包哈希；不提交临时辅助文件。
