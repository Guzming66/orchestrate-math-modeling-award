# 数学建模大奖总控 Skill

面向全国大学生数学建模竞赛（CUMCM）和 MCM/ICM 的 Codex 总控 Skill。它负责创新方案搜索、核验当届官方规则、拆解多小问题、管理依赖关系、并行比较独立模型、审计数据/文献/结果来源、组织交叉验证，并以 LaTeX 为论文唯一真源完成提交前门禁。

## 核心能力

- 按依赖关系拆分赛题、小题和模型分支，避免不同任务互相污染。
- Innovation Engine 从题目特殊结构出发，执行多路线发散、跨领域类比、最近文献核验、便宜证伪实验、盲红队和评委淘汰。
- 用统一台账管理官方规则、原始数据、关键结论、引用和结果哈希。
- 对候选模型执行独立建模、盲交叉验证、统计与不确定性审核。
- 直接维护 CUMCM 与 MCM/ICM LaTeX 工程，不经过 Word 格式转换。
- 最终检查采用“失败即阻断”：复现、匿名性、引用、数据来源、论文编译或支撑材料任一不合格，都不会报告“可提交”。

## 配套 Skills

使用前请安装以下 Skills：

- 必需：`mathmodel-skill`、`citation-management`
- 强烈建议：`statistical-analysis`、`uncertainty-and-units`、`scientific-critical-thinking`
- 按需：`data-analytics:analyze-data-quality`

其中 `mathmodel-skill` 提供十阶段基础流程，本 Skill 负责总控、证据链和提交门禁。引用验证脚本默认从同级目录、`$CODEX_HOME/skills`、`~/.codex/skills` 或 `~/.agents/skills` 寻找；也可通过 `CITATION_VALIDATOR` 指定。

## 安装与调用

仓库地址：<https://github.com/Guzming66/orchestrate-math-modeling-award>

在 Codex 中使用 `$skill-installer` 从上述 GitHub 仓库安装，然后明确调用：

```text
使用 $orchestrate-math-modeling-award 初始化这道国赛题，启用 championship Innovation Engine；先核验当届官方规则，再按小题和模型分支建立任务板；论文只使用 LaTeX。
```

也可以手动把整个仓库复制到 Codex 的 Skills 目录，保持 `SKILL.md`、`scripts/`、`references/`、`assets/` 和 `agents/` 的相对位置不变。

## 本地依赖

- Python 3.10 或更高版本；运行时脚本只依赖标准库。
- 完整 LaTeX 工具链：`latexmk`、`xelatex`、`pdflatex`、`bibtex`。
- PDF 检查工具：Poppler 的 `pdfinfo` 和 `pdftoppm`。
- Pillow 为可选依赖，用于支撑材料中的图片元数据扫描。

建议每场比赛在独立工作区和独立 `.venv` 中运行，并保存解释器、包版本、随机种子和环境快照。

## 快速开始

```powershell
python scripts/init_competition_workspace.py <工作区> --competition CUMCM --year 2026 --problem A --branches 3 --innovation-mode championship
python scripts/validate_innovation_portfolio.py <工作区>
python scripts/build_latex.py <工作区>/paper --competition CUMCM --mode draft
python scripts/finalize_submission.py <工作区>
```

最后一条命令只有在全部硬门禁通过后才会生成可提交清单。

## 验证

```powershell
python -m unittest discover -s tests -v
```

模板编译测试会在本机具备 LaTeX 和 PDF 工具时自动运行，否则明确跳过。

## 重要说明

- 仓库不包含任何赛题原文、参赛论文、队员身份信息或比赛数据。
- 每届官方通知、格式规范和提交规则始终高于仓库内的历史参考资料；开赛后必须重新联网核验并保存来源。
- 本项目不是 CUMCM、COMAP 或 OpenAI 的官方项目，也不保证奖项结果。
- 两个 LaTeX 模板包含基于 `mathmodel-skill` 的 MIT 许可衍生部分，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
