# 开发指南

默认源码入口为 Electron + Python（R7 / 0.11 候选），不需要 Qt。可扫描、审阅、预览、确认整理、恢复、撤销及辅助查找；下载、验证、安全解压、待审阅导入和记录导出均已接入。
0.11.0-rc.2 的源码和运行包对应相同业务实现，旧发布版本保留。结构只见 [architecture.txt](../architecture.txt)，任务见 [todo.txt](../todo.txt)，历史见 [CHANGELOG.md](../CHANGELOG.md)。

## 从源码运行

Windows x64、Python 3.12；Node.js 22+ 只用于可选检查。无需开发服务器。

```powershell
py -3.12 -m venv .venv-core
.venv-core/Scripts/python.exe -m pip install --only-binary=:all: -r requirements.txt
.venv-core/Scripts/python.exe scripts/setup_electron.py
.venv-core/Scripts/python.exe run.py
```

也可双击 `start_electron.cmd`。脚本优先使用 `.venv-core`，不存在时使用 `.venv-build`。
安装器只下载校验过的官方 Electron 45.0.0，不执行 npm 安装脚本。
`run_electron.py` 是同一入口；`--effects=moderate` 关闭次要雾气和粒子，不改变业务能力。

本轮专用验证环境无 PySide6，只复用了原环境已有的 pymediainfo 7.0.1，没有联网安装。
新安装环境请用上面的正常 venv/pip 命令；不要把验证环境的构建方式当成发布方案。

## 增量验证

```powershell
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/unit -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/contract -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/integration -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/recovery -v
node tests/frontend/online.cjs
node tests/frontend/visibility.cjs
node scripts/check_noqt_desktop.cjs
node scripts/check_recovery_desktop.cjs
node scripts/check_subtitle_desktop.cjs
```

集成检查只使用生成的临时媒体。R3 桌面检查打开实际可见窗口，通过本机 CDP 验证恢复提示、预览确认、整理、撤销、刷新历史与正常退出，不访问真实网站；结果和截图在忽略的 `work/test-results/r3-desktop-*/`。
`scripts/check_noqt_desktop.cjs` 检查 300 项真实窗口和 5000 项虚拟列表契约，包含节点复用、缓存、乱序回执与文件名纯文本显示。旧证据继续保留。
`-S` 跳过第三方包；真实内嵌字幕助手另用同一虚拟环境启动，只依赖 pymediainfo。无该组件时不自动通过任何视频。

业务基准独立于正确性测试：

```powershell
.venv-core/Scripts/python.exe -S benchmarks/business.py --implementation layered --output work/test-results/business-benchmarks/current.json
```

基准生成可丢弃样本，只运行当前实现，记录计时和磁盘检查次数，不设时间通过门槛，也不推算整体帧率。历史前后对照保留在 evidence/refactor-r5.json；旧实现已清理，当前脚本不再接受 legacy 参数。
按实际改动选择检查，保留已有结果，不重复未受影响的完整历史验收。若 Codex 的文件沙箱拒绝 Windows 最终路径解析，应区分沙箱失败与产品失败，不修改系统权限来绕过。

## 数据与进程入口

默认源码数据在 `work/electron-profile-noqt/`：外观为 `appearance.json`；`python/embedded.json` 为内嵌语言，`python/online.json` 为在线偏好，`python/tasks.sqlite3` 为字幕工作流及回执，`python/history.jsonl` 读取兼容历史。
不自动迁移旧资料。搜索只在用户确认后访问字幕网站；R3 文件变更需要独立的预览与明确确认。
`python/operations/journal.sqlite3` 保存逐项文件意图/结果，`python/operations/buffers/` 是恢复与撤销备份；目标目录内可能保留受管 `.yingxu-*.part`。不要只拷贝单个数据库或手动清空这些文件。
应用退出后一起保留整个数据目录（含可能存在的 WAL）；同一数据目录拒绝同时启动两个 Python 服务。
启动只读核对不会继续改文件；在操作记录查看恢复预览并确认后才能续接，也可稍后处理或打开缓存人工核对。
撤销仅支持 R3 新任务；已被修改/替换的目标、原位置占用或无法证明归属时拒绝自动撤销。
缓存回收保护草稿、恢复、撤销与活跃下载引用，只删除内容未变化且无引用的载荷；恢复备份继续保守保留。这不构成真实断电恢复的证明。

Python 进程入口：

```powershell
.venv-core/Scripts/python.exe -S -m yingxu.desktop.host --profile work/test-results/manual-host
```

它是受限 NDJSON 服务，普通用户使用图形入口。输入/输出必须是 v2 消息；stdout 只用于通信。
业务规则修改与接口替换示例见 [learning.md](learning.md)。

## 当前打包与历史版本

当前仓库已移除 Qt 宿主、入口、QML、Qt 构建钩子和专用测试，仅保留 Electron + Python。
旧版本可从对应 Git 标签检出到独立目录；不会删除已经发布的运行包，不在当前源码维护第二套容器。
构建只使用 scripts/build_electron.py；通用的哈希/资源工具在 scripts/build_utils.py，许可清单在 release_payload.py。

```powershell
py -3.12 -m venv .venv-build
.venv-build/Scripts/python.exe -m pip install --only-binary=:all: -r requirements-build.txt
.venv-build/Scripts/python.exe scripts/build_electron.py --zip
```

7 份根目录旧业务测试已按用途迁入 unit/contract/integration；与新用例共同由 `unittest discover -s tests` 发现。
旧 Qt 容器专属检查随容器移除，保留的字体/Lens/显示选择/PresentMon 分析测试已迁入 unit。
Qt 历史依赖和原发布证据保留在对应旧标签与历史阶段文档，不能作为当前运行依赖说明。

下载缓存见 `python/subtitles/`。重启后从“下载暂存”查看，核对原目录/视频身份后才能导入。草稿、恢复、撤销仍引用的载荷不能清除；blob 需从网站重新获取。
`check_subtitle_desktop.cjs` 使用生成 HTTPS 页面验证浏览器边界；`check_live_provider.cjs --provider=subhd --title=Interstellar` 为有界的真实网站检查，只对生成视频下载一份字幕并导入待审阅，不修改实际媒体，也不代替网站验证。

候选 EXE 可直接传给增量桌面检查：

```powershell
node scripts/check_noqt_desktop.cjs outputs/releases/0.11.0-rc.2/YingXu/YingXu.exe
node scripts/check_recovery_desktop.cjs outputs/releases/0.11.0-rc.2/YingXu/YingXu.exe
node scripts/check_subtitle_desktop.cjs outputs/releases/0.11.0-rc.2/YingXu/YingXu.exe
```

300 项列表检查同时记录启动、短时滚动 CPU 样本和各进程工作集，检查真实窗口缩放/最小化/恢复。它不构成新的高刷新率认证。使用 diagnostics PID/句柄核对的专用辅助脚本调整测试窗口，不操作其他应用。

审阅草稿与网站队列存储在 python/workspace.sqlite3。重启后先核对字幕内容/文件身份，旧预览授权不恢复；继续队列需要新的明确确认。30 天以上已导入缓存仅回收内容未变化、无草稿/恢复/撤销引用的载荷，保留撤销目录身份。
