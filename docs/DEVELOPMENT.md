# 开发指南

产品介绍和使用流程见根目录 README。这里保留运行、构建和技术资料。

## 从源码运行

Windows x64、Python 3.12；Node.js 22+ 用于可选前端检查。

```powershell
py -3.12 -m venv .venv-web
.venv-web/Scripts/python.exe -m pip install --only-binary=:all: -r requirements-lock.txt
.venv-web/Scripts/python.exe scripts/setup_electron.py
.venv-web/Scripts/python.exe run_electron.py
```

也可双击 `start_electron.cmd`。安装器只下载校验过的官方 Electron 45.0.0，不执行 npm 安装脚本；下载运行包的用户无需执行这些步骤。

`run_electron.py --effects=moderate` 关闭次要雾气和粒子；`--preview` 保留阶段 A 只读模式，后台拒绝改配、执行和在线窗口。

保留的 Qt 兼容入口为 `run.py`，其 `--widgets` 模式使用 SDR WebEngine 容器。原 Tkinter/早期 Qt 工作台已移除，历史代码可从 Git 恢复。

## 构建与验证

```powershell
.venv-web/Scripts/python.exe scripts/build_electron.py --zip
```

输出 `outputs/releases/<版本>/YingXu/YingXu.exe` 和完整 ZIP；构建缓存在 `work/build/electron/`。运行包包含 Electron 与冻结 Python/Qt 辅助进程，资源和动态库须整包保留。依赖、对应源码、重建及库替换说明见 [DEPENDENCIES.md](DEPENDENCIES.md)。

```powershell
.venv-web/Scripts/python.exe -m unittest discover -s tests -v
.venv-web/Scripts/python.exe -m unittest discover -s tests/web -v
.venv-web/Scripts/python.exe scripts/audit_public.py
```

检查仅使用可丢弃的临时媒体。接续开发时读取 [PROGRESS.md](../PROGRESS.md)，按实际改动选择增量检查，不重复未受影响的全部历史测试。

## 代码与数据

- `desktop/electron/`：主窗口、受限 IPC 和 preload。
- `yingxu/desktop_host/`：后台服务与独立在线字幕窗口适配。
- `yingxu/core.py`、`review.py`、`operations.py`：扫描、匹配、固定计划和文件操作。
- `yingxu/subtitle_sources/`：站点、候选、下载与安全解压。
- `frontend/`：本地界面、字体和保留署名的上游效果。
- `scripts/`、`tests/`、`docs/`：构建/发布、验证及历史记录。

发布版数据目录为 `%LOCALAPPDATA%/YingXu/Electron/`，外观 `appearance.json`，记录 `python/history.jsonl`，字幕缓存 `python/subtitle-inbox/`。源码入口使用忽略的 `work/electron-profile/`，不自动迁移旧 Qt 数据。

## 技术记录

- [阶段 A：架构、性能测量与 HDR](STAGE20A_ELECTRON.md)
- [阶段 B：业务接入与窗口隔离](STAGE20B_ELECTRON.md)
- [阶段 C：独立运行包、验证与发布](STAGE20C_RELEASE.md)
- [内嵌字幕与语言判断](STAGE18_EMBEDDED_SUBTITLES.md)
- [依赖、许可和库替换](DEPENDENCIES.md)
- [发布流程](PUBLISHING.md)

接口、浮点输出、呈现指标、来源限制、压缩格式边界和原始验证摘要保留在上述文档，不以产品文案代替技术记录。发布资产与版本标签保持不可变；文案修订只更新仓库和 Release 说明。
