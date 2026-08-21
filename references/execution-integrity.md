# v15 执行完整性

## 题面是唯一范围权威

把原题与附件放入 `inputs/original/`，计算哈希后填写 `shared/problem_contract.json`。每问必须包含题面定位、原始任务动词、所需答案、明确产物、输入、结构化上游依赖、精度与约束。`problem_contract.md` 只供阅读；JSON 决定模型选择、逐问 LaTeX 和终审覆盖。

运行：

`python scripts/validate_problem_contract.py <workspace> --final`

## 为强全域主张建立证书

模型或论文若声称“首次/最早发生”“全局最小/最大”“最优”“在整个定义域安全”或其他需要排除全部遗漏候选的结论，必须写入 `synthesis/global_claim_certificates.json`。模型冻结时先人工检查结果 artifact 并建立结果级主张草案；论文成文后再人工核对已加载 TeX 中的每次实际出现。验证器的自动发现只是对已加载论文 TeX 运行的有限正则哨兵，用于提示常见漏项；它不扫描结果 artifact，也不能完备识别所有等价表达。人工主张清单是范围权威，主动登记但未命中词表的强主张仍按完整证书验证，不会仅因用词不同而失败。

论文覆盖单位是每一次具体文本出现，不是文件：摘要和正文各写一次就各自需要局部定位，不能用“本文件已有一张证书”覆盖其余措辞。`locator` 应是源文件内唯一、紧邻主张的标签或文本；`claim_text` 必须使用该 locator 局部窗口内的实际强主张措辞，而不是远处摘要或泛化改写。不同位置措辞不同就拆成不同证书；同一句同时包含两种强主张时也分别登记，使一个 location 只映射一个强主张出现。随后登记：

1. `domain`：变量、边界/集合、纳入与排除项；
2. `coverage`：候选划分或覆盖策略，以及为何覆盖整个声明域；
3. `checks`：端点、非光滑/拼接/事件点和内部候选分别为 `pass` 或有具体理由的 `not_applicable`，并连接证据 ID；必需项由 coverage strategy 决定；
4. `exclusion_argument`：未入选点为什么不可能产生更早事件、更优值或安全反例；
5. `scope_limitations`：证书依赖的固定参数、离散化、模型与数据范围；
6. `evidence`：每份 artifact 的相对路径、SHA-256、实际命令/检查、ISO 时间和它支持的检查。

检查路由如下：

| coverage strategy | 必须为 pass 的检查 |
|---|---|
| `candidate_enumeration` | 无固定连续域检查；三项均可 `not_applicable`，但完整候选表、排除论证和 artifact 仍必需 |
| `analytical_exhaustion / interval_subdivision / monotonicity_reduction / bounded_global_search` | `endpoints + interior`；不存在内部驻点也应以实际检查结果说明，而不是跳过 |
| `event_partition / hybrid` | `endpoints + nonsmooth + interior` |
| `other` | 至少一项 pass，并由完整性论证说明其余项为何不适用 |

证书状态只能在完成上述责任后设为 `complete`；确无此类强主张时用根状态 `not_applicable` 并填写具体理由。运行：

`python scripts/validate_global_claim_certificates.py <workspace>`

该验证器只确认已登记证书的结构完整、正文/结果定位存在、evidence ID 可解析且 artifact 路径与哈希真实，并要求有限正则哨兵已发现的论文出现全部被映射。它不能发现人工清单遗漏的结果主张或词表外表达，也不会求解数学问题、证明候选划分完备、排除论证正确、全局最优或全域安全。审查者必须独立攻击覆盖策略；无法排除遗漏时，缩小声明域或改写为“在已检查范围/候选中”。

## 冻结跨小问接口

先在 `synthesis/result_manifest.csv` 为每个结果填写 `question_id`。若 Q2 沿用 Q1，则在 `shared/question_interfaces.json` 登记 Q1→Q2、实际使用的 result ID、每个结果的规范化 fingerprint，以及证明 Q2 已按该版本求解的 artifact。

结果 fingerprint 覆盖数值、单位、命令、输入、随机种子、环境和结果文件哈希。任何字段变化都会使下游接口 stale。不要仅写“沿用第一问结果”。

运行：

`python scripts/validate_question_interfaces.py <workspace> --final`

## 让终审器实际复现

把 `audits/reproduction/reproduction_status.json` 改为 `ready`，填写：

- `runner.argv`：参数数组，不写 shell 管道或重定向；
- `runner.entrypoint` 与 `runner.entrypoint_sha256`：指向工作区内实际执行的脚本或可执行文件，并绑定其哈希；禁止 `python -c`、`sh -c` 等内联答案；
- `runner.working_directory`：相对工作区目录；
- `runner.clean_paths`：只列运行前从隔离副本删除的命名输出位置，路径中必须含 `result(s) / figure(s) / build / output(s)`；不得指向工作区根、输入、代码、环境、入口文件、运行目录或其祖先；
- `expected_artifacts`：覆盖 result manifest 的全部结果路径与当前 SHA-256；
- 复核人、时间和未关闭问题。

Finalizer 会复制工作区到临时目录、删除 clean paths、执行 argv，再核对新产物。源工作区不会被清理或改写。隔离执行报告位于 `audits/reproduction/execution_report.json`。

赛前运行 `preflight.py`。Companion CLI 选项从源码静态解析，运行时依赖另用当前 Python 执行 `--help` 检查；若依赖缺失，报告具体模块和解释器，不再衍生误报“CLI 参数不存在”。应使用能通过该预检的同一 Python 执行总控与 Finalizer。

`snapshot_environment.py` 只把 profile 选定的 LaTeX 引擎、实际使用文献时的 BibTeX 和 PDF 审计工具视为必需；`latexmk` 与未选引擎只记录可选状态，避免因未使用工具缺失而阻断。

## 逐页验收最终 PDF

第一次运行 Finalizer 会完成提交模式编译、渲染 `audits/presentation/final_pdf_pages/page-NNN.png`，并生成 schema v2 `final_pdf_visual_review.json`。构建报告必须为 PDF 全部页面生成 `page_layout_metrics`：正文顶部/底部比例、下方空白比例、正文词数和被排除的纯页码词数。指标只用于定位可疑页面，不是论文质量分数。逐页检查：

1. 裁切、遮挡、越界与异常空白；
2. 中文字体、数学符号、负号和乱码；
3. 公式、表格、图注、图例、分辨率与跨页；
4. 页码、匿名性、元数据可见项与最终次序；
5. 浮动体连续性、图文关系、页面平衡和自动布局指标是否与实际页面一致。

下方空白比例超过 45% 的页面会被标记为 sparse；只有确认它属于参考文献/附录等有意结尾材料，或有可说明的结构性分页时，才能分别填写 `intentional_end_matter` 或 `intentional_structure`，并给具体 notes。其他页面必须为 `not_flagged`；不能用 disposition 掩盖浮动体漂移、空标题或图文断裂。

每项写 `pass`，填写复核人与 ISO 时间后再次运行 Finalizer。PDF 二进制哈希变化时全部页面记录重置；在同一 PDF 中，渲染页面哈希或自动布局指标变化也会使对应页失效。这样复核既绑定最终文件，也绑定逐页视觉内容和本次判断所依据的自动测量。

## 重大审查问题

`audits/review_findings.json` 使用 schema v3。每个通过的 coverage 记录都必须绑定本问论文锚点、具体检查、实际执行的证伪/边界攻击、结论 outcome 和 artifact-backed evidence，不能只写“reviewed/pass”。`critical` 必须 closed。`major/open` 一律阻断。只有 standard policy 允许的少量 `major/accepted_risk` 可以保留，并且必须填写 `risk_owner`、`impact_scope`、`fallback` 和 artifact-backed evidence；championship 默认允许数量为 0。
