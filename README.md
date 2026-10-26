# 映序 · 视频字幕整理器

为视频匹配字幕，预览每一处变更，确认后再整理。支持在线查找、下载后自动解压和内嵌字幕识别，配有明暗主题与玻璃交互。当前版本 **0.10.0-rc.1**。

<img src="docs/images/workspace-dark.png" width="1100" alt="映序实际 EXE 字幕工作台">

实机运行包截图使用临时样本，目录路径已隐去；普通截图不展示或测量 HDR 峰值亮度。

## 下载

在 [0.10.0-rc.1 Release](https://github.com/mason2237/YingXu/releases/tag/v0.10.0-rc.1) 下载 [Windows x64 完整运行包](https://github.com/mason2237/YingXu/releases/download/v0.10.0-rc.1/YingXu-0.10.0-rc.1-windows-x64.zip)，完整解压后双击 `YingXu/YingXu.exe`。保留所有 DLL、`resources` 和 `python`，不能单独复制 EXE；无需另装 Python、Node、浏览器或开发服务器。下载页同时提供对应源码和 SHA256 校验。

[详细功能与更新说明](release/RELEASE_NOTES.md)介绍 Electron 迁移、在线字幕、内嵌语言检查、快捷键及安全流程。此版为未签名预发布版，完成当前 Windows 的定向验证，**未进行干净 Windows 系统测试**；验证边界见 [阶段 C](docs/STAGE20C_RELEASE.md)。旧 rc.12 可保留回退，新版不自动迁移旧 Qt 数据。

## 运行与构建

源码默认入口 **`run_electron.py`**（也可双击 `start_electron.cmd`），构建 **`scripts/build_electron.py --zip`**。`run.py` 和 `scripts/build.py` 仍保留 Qt 兼容源码；旧 Tkinter/早期 Qt 工作台已移除，历史保留。

需要 Windows x64、Python 3.12。安装依赖后运行：

```powershell
py -3.12 -m venv .venv-web
.venv-web/Scripts/python.exe -m pip install --only-binary=:all: -r requirements-lock.txt
.venv-web/Scripts/python.exe scripts/setup_electron.py
.venv-web/Scripts/python.exe run_electron.py
```

保留的 Qt 源码兼容入口（独立 EXE 下载默认 Electron）：

```powershell
.venv-web/Scripts/python.exe run.py
.venv-web/Scripts/python.exe run.py --widgets
```

`--widgets` 仍使用当前网页、Python 后端和文件安全流程，采用 SDR QWebEngineView。它不启动已移除的旧 Qt 控件界面。

构建当前版本：

```powershell
.venv-web/Scripts/python.exe scripts/build_electron.py --zip
```

输出为 `outputs/releases/<版本>/YingXu/YingXu.exe` 和完整 ZIP，缓存 `work/build/electron/`。Electron 与冻结 Python/Qt 辅助进程均已包含；资源与动态库必须整包保留。构建不会替换 rc.12 输出。

`requirements.txt` 列出直接依赖；`requirements-lock.txt` 锁定完整构建环境；`requirements-dev.txt` 仅补充图标生成工具。可选在线字幕独立调试入口是 `run_subtitle_browser.py`，正式使用可直接从工作台打开。

### 运行模式与数据

阶段 A 在本机 180Hz/HDR、300 项样本的三轮交互中，通过 rAF/Chromium/PresentMon 交叉验证：实际呈现 172.319–180.001fps，p95 最大 5.6401ms；并已验证超过 SDR 白点的浮点高光，不代表面板峰值或所有设备的性能保证。B 接通完整整理流程，C 提供独立运行包。

```powershell
# 适度简化烟雾及粒子，保留增强玻璃和 HDR 高光
.venv-web/Scripts/python.exe run_electron.py --effects=moderate
# 原阶段 A 只读模式，后端拒绝改配、整理和在线下载
.venv-web/Scripts/python.exe run_electron.py --preview
```

开发安装器只下载官方 Electron 45.0.0 ZIP，验证固定 SHA256，不执行 npm 安装脚本；下载运行包不需要此步骤。在线字幕复用独立 Qt 辅助进程，远程网页无本地业务桥，仍需加载 Qt WebEngine。见 [阶段 A](docs/STAGE20A_ELECTRON.md)、[阶段 B](docs/STAGE20B_ELECTRON.md) 与 [阶段 C](docs/STAGE20C_RELEASE.md)。

正式运行包数据为 `%LOCALAPPDATA%/YingXu/Electron/`；开发入口仍用忽略的 `work/electron-profile/`。两者均不自动覆盖旧 Qt 配置/记录。诊断使用 Node.js 22+ 与内置模块，不需要 Playwright/浏览器插件；可选 HDR 捕获工具单列于 `desktop/electron/requirements-probe.txt`，不进入运行包。

## 使用流程

1. 选择或拖入文件夹，按需设置递归扫描和字幕移动选项。
2. 扫描并查看匹配列表，通过搜索、排序和筛选定位视频。
3. 核对低可信匹配，更换、确认或跳过字幕。
4. 预览原名称、目标名称和冲突，勾选确认后执行整理。
5. 查看结果及本地操作记录。

扫描和审阅不修改媒体；实际整理必须明确确认，已有目标不会被覆盖。尚无撤销功能。主工作台离线处理，不上传媒体。

- `Ctrl+F` 搜索、`Ctrl+Enter` 预览；方向键/Home/End/PageUp/PageDown 选择，Enter 查看详情。快捷操作面板和 Ctrl+K 已移除。
- 设置关闭采用 140ms 淡出，背景特效延后恢复；减少动态时直接关闭。主题、玻璃、雾气、粒子及光影强度均可设置。
- 原生 HDR 需要当前 Windows 屏幕已开启 HDR，设置显示实际输出状态；程序不修改系统 HDR 开关，不支持时回退 SDR。在线字幕窗口仍为 SDR。
- 新版外观为 `%LOCALAPPDATA%/YingXu/Electron/appearance.json`，记录为其下 `python/history.jsonl`，下载缓存为 `python/subtitle-inbox/`；旧 Qt 路径仍保留，不自动迁移。

## 已有内嵌字幕自动通过

扫描会读取视频内的独立字幕轨。**语言符合就标记“已符合”，不导出字幕、不下载外挂，也不修改视频。** 列表显示“内嵌已满足”，详情可以查看语言、格式和字幕轨标题。

在“扫描选项”中设置内嵌语言要求：默认中文（双语优先），也可要求严格中英双语、简体、繁体、英语、日语、韩语或任意语言。语言不符、未标注或标注冲突时，保留原有外挂匹配和查找流程；默认批量在线搜索会排除已经满足的视频。判断有误时可点击“仍需外挂字幕”，之后也能改回使用内嵌字幕。

这里识别的是独立软字幕轨，包括文字轨和图片轨；烧录在画面中的硬字幕无法通过轨道信息识别。语言判断依据元数据，并非实际文字 OCR 或翻译质量检测。仅有强制/片段或评论字幕不会当作完整字幕通过；严格双语不把独立中文、英文两轨误认为同一轨双语。

新读取组件随 Windows 包提供，无需额外安装工具或联网读取媒体。语言选项保存后要重新扫描，旧预览会失效；已读取且文件未变化的轨道信息可在内存中复用。

## 可选在线字幕

从工作台点击“在线字幕”，默认优先字幕库，可切换 SubHD 备用，无需 API Token。确认搜索后才联网发送片名，不上传视频。默认中英双语优先，语言偏好可保存。

按照“确认片名 → 选择并下载 → 核对匹配”操作。搜索词自动去掉清晰度、编码等片源标签，可手动修改。网站验证码和下载按钮仍需用户操作，不承诺无人值守或不同剪辑版本时间轴一致。

默认下载后自动解压并加入待确认，单版本关联待确认、多版本进入候选；最终预览并确认后才整理到视频旁边，原下载保留。支持直接字幕、ZIP 及系统 tar 支持的 RAR/7z；不支持加密/分卷/ZIP64、嵌套包及 IDX/SUB 配对。缓存可从窗口按钮打开，不自动清除或跨会话恢复审阅。

<img src="docs/images/online-subtitles-dark.png" width="1100" alt="在线字幕窗口">

## 目录与验证

- `run_electron.py`、`desktop/electron/`：当前桌面入口；`run.py`：Qt 兼容入口；`assets/`：图标。
- `yingxu/core.py`、`review.py`、`operations.py`：原有业务和文件安全机制。
- `yingxu/web_ui/`、`subtitle_sources/`：桌面容器、受限接口及字幕接入。
- `frontend/`：当前工作台、字体和保留署名的上游效果。
- `scripts/`：当前构建、发布、许可和定向检查工具；`tests/`：现行测试。
- `docs/`、[PROGRESS.md](PROGRESS.md)：设计、验证、历史记录和续接说明。

```powershell
.venv-web/Scripts/python.exe -m unittest discover -s tests -v
.venv-web/Scripts/python.exe -m unittest discover -s tests/web -v
.venv-web/Scripts/python.exe scripts/audit_public.py
```

测试仅使用可丢弃的临时样本，不能用于个人媒体。最新渲染优化与本机验证见 [STAGE19_RENDERING.md](docs/STAGE19_RENDERING.md)，内嵌字幕见 [STAGE18_EMBEDDED_SUBTITLES.md](docs/STAGE18_EMBEDDED_SUBTITLES.md)。保留既有测试结果和 Git 提交。本轮优化按钮重复更新、虚拟列表和 HDR/SDR 合成，玻璃、果冻和可选 HDR 保持；对应窗口动画和重载已定向复验，不承诺所有偶发闪烁已消除。本文截图保留自此前验证版本。未做干净 Windows、长期或所有显卡认证，EXE 未签名。

现有 GitHub Releases 可能仍为旧公开版本，本地候选不自动上传。可分发运行包、对应源码及校验文件位于 `outputs/github-release/<版本>/`。依赖、Qt 库替换及署名见 [DEPENDENCIES.md](docs/DEPENDENCIES.md)。

## 许可证与商业授权

原创代码及自有资源采用官方、未修改的 [PolyForm Noncommercial License 1.0.0](LICENSE)。允许按许可证个人免费使用、学习、修改和非商业性再分发；商业使用须事先获得相应版权所有者的单独授权。授权可通过仓库 Issues 联系维护者。

Required Notice: Copyright 2026 YingXu project authors and contributors.

第三方组件继续适用各自许可证，项目的非商业限制不覆盖其独立授予的权利。完整声明见 [NOTICE](NOTICE)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [licenses/](licenses/)。
