# 交接给执行 agent

> 本机状态 2026-11-09：YX-00 至 YX-05 均已完成源码验证；最新分支 codex/yx05-subtitle-needs。已交付 0.12.0-rc.1 本地 EXE（仅含 YX-00 至 04，未上传），YX-05 尚未打包。实测见 evidence/yx05-windows.json 和根目录 PROGRESS.md。下一批 YX-06/07 未实施；不重复历史全套，不增加干净 Windows 测试。

以下为历史报告的原始基线与交接记录，不代表当前完成状态；当前状态以上述检查点和 tasks.json 为准。

本机独立历史不包含公共 c7b8056 提交；其 matching.py 与本机起点 7f4b700 的 Git blob 已核对相同。对照脚本本机使用 `--baseline-ref 7f4b700`；公共仓库继续可用默认基线，勿混淆两条提交历史。

先读 [升级报告](REPORT.zh-CN.md)，再按 [tasks.json](tasks.json) 选择阶段。当前只有 **YX-01 多集覆盖/全角集号误配修复**落地；相关 70 项 Python 测试和 3 个前端脚本通过，Windows/EXE 尚待验收。其余任务是实施计划，不能标为已经完成。

本轮基于 `mason2237/YingXu` 的 `c7b8056b35d02e335723366e9916512032133a13`，公开版本仍为 `v0.11.0-rc.3`。源码改动没有增加运行依赖或数据库迁移。上游源码锁定和测试证据见 `evidence/`；该目录不包含八个上游仓库的完整源码。

可以把以下指令连同整个报告目录交给后续 agent：

> 在映序仓库继续 R11。先读取当前仓库指令、architecture.txt、docs/DEVELOPMENT.md、todo.txt，以及本目录的 REPORT.zh-CN.md 和 tasks.json。检查工作区与远端最新提交，保护已有改动；若基线变化，先审查差异再执行。先完成 YX-00 的测试环境/Windows 复验，并核对已实现的 YX-01，不要重复实现。随后按依赖执行 YX-02、YX-03、YX-04，形成下一阶段可审阅候选；其余任务保留待办。每张卡记录实际改动、测试命令/结果、限制及回退方法。保留 Electron + Python、标准库 domain、8 KiB 分页、人工审阅、事务和撤销。遇到匹配歧义进入需确认，不用相同季集号代替作品身份；不自动提取所有视频字幕。没有 Windows 环境时完成平台无关部分并明确保留验收，不放宽安全策略来制造全绿结果。按卡独立提交，不自动合并主分支或发布 Release。

在仓库根目录复核本轮源码：

```sh
python -S -m unittest discover -s tests/unit -v
python -S -m unittest discover -s tests/contract -p test_core.py -v
python -S -m unittest discover -s tests/contract -p test_subtitle_sources.py -v
node tests/frontend/online.cjs
node tests/frontend/visibility.cjs
node tests/frontend/review_details.cjs
python -S docs/research/subtitle-upgrade-2026-11/reproduce_matching.py
```

最后一个脚本需要 Git 中保留上述基线提交；浅克隆若缺失，应先获取该提交。参考字幕同步实验使用单独的研究 venv，按报告第 7 节复现，不把研究依赖安装进映序运行环境。

初始 Linux 全量结果为 198 项中 141 成功、2 failure、32 error、23 skipped；详细原因和未执行项见 [validation.json](evidence/validation.json)。70 项相关测试通过不代表全量或 Windows 发布门槛已经通过。
