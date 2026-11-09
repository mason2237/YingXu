# 可选解析器与冻结替换试验

2026-11-09，YX-02。默认运行环境仍只有 pymediainfo；GuessIt 未安装到 `.venv-core`、未进入默认冻结后台、未发布可选依赖包。结构化本地结果只作核对，下一卡才实现新的匹配评估。

可选接口为 `ports/release_parser.py`，实现为 `adapters/guessit_parser.py`。开启源码对照需在单独环境准备准确的 GuessIt 4.4.0，再设置 `YINGXU_RELEASE_PARSER_SHADOW=1`。默认关闭；版本不符、缺库、异常或超长/无效字段退回本地规则，不自动安装或联网。调用禁止读取用户 GuessIt 配置，结果不参与自动分配。

## 实际验证

- 官方 wheel 的 Python 库、元数据、许可和无 `.pth` 已先检查；未执行安装脚本，直接展开至忽略的 `work/tools/guessit-shadow/parser-libs`。
- 源码真实调用得到电影标题及完整的 `(1, 2)` 多集集合。
- 单独冻结的 ParserProbe 将库排除在归档外，同时包含被外部库调用的标准库模块；初次试验发现缺少 shlex 后，通过静态导入清单修正。该原型不是应用发布包。
- 冻结原型用原库返回 `guessit / 4.4.0`；换成测试替代库后返回 `Replacement Library`；库缺失时回退 builtin。无需重建宿主或修改原库即可替换。
- 冻结模块没有 GuessIt/Rebulk/Babelfish 或 Qt；完整结果、轮子摘要、标准库清单和源码材料在 [optional-parser-trial.json](evidence/optional-parser-trial.json)。原型和材料保存在本机忽略的 work 目录。

## 依赖与许可范围

| 组件 | 实际试验版本 | 许可 |
| --- | --- | --- |
| GuessIt | 4.4.0 | LGPL-3.0-or-later |
| Rebulk | 6.0.1 | MIT |
| Babelfish | 0.6.1 | BSD-3-Clause |
| python-dateutil | 4.0.0 | BSD-3-Clause |
| tzdata | 2026.6 | Apache-2.0，另保留随库许可材料 |

已获取官方 PyPI 4.4.0 源码归档并对照 PyPI SHA256；完整 GPL v3 / LGPL v3 文本复用仓库中有来源及摘要的原文。源码归档、原始 wheel 及它们附带的版权/NOTICE 不作修改；GuessIt wheel 的跨解析器测试数据还含独立来源声明，不能只依据顶层 LGPL 概括所有数据。

本试验不把第三方许可重新限制为非商业，也没有将 GPL 项目代码拷入原创核心。若将来分发外置库，须在该可选包保留所有必要署名/许可/相应源码及替换和调试修改库的说明；不对替换库添加强制签名/摘要锁。进程或目录隔离不免除许可义务。本轮默认包不新增第三方分发，不能把本地原型试验称作完整可选发布包验收。

## 复现入口

从仓库根目录运行。先在独立目录下载表中固定版本的官方 wheel；不得把它们安装到应用默认环境。按 evidence/optional-parser-trial.json 中的 wheels 写出本机 `work/tools/guessit-shadow/wheel-review.json` 并核对 SHA256，再复制以下原型脚本：

```powershell
Copy-Item docs/research/subtitle-upgrade-2026-11/parser-trial/probe.py work/tools/guessit-shadow/probe.py
.venv-core/Scripts/python.exe -S docs/research/subtitle-upgrade-2026-11/parser-trial/prepare.py
.venv-core/Scripts/python.exe -S work/tools/guessit-shadow/probe.py work/tools/guessit-shadow/parser-libs
.venv-build/Scripts/python.exe docs/research/subtitle-upgrade-2026-11/parser-trial/freeze.py
work/tools/guessit-shadow/frozen/ParserProbe/ParserProbe.exe work/tools/guessit-shadow/parser-libs
work/tools/guessit-shadow/frozen/ParserProbe/ParserProbe.exe work/tools/guessit-shadow/replacement-libs
work/tools/guessit-shadow/frozen/ParserProbe/ParserProbe.exe work/tools/guessit-shadow/missing-libs
```

`prepare.py` 只处理已下载、已核对的 wheel，不运行安装脚本；`freeze.py` 使用既有构建环境，不自动安装工具。真实应用的新 EXE 与最终可选分发许可汇集留给发布阶段。
