# 依赖、署名与库替换

## 当前使用范围

| 部分 | 版本/来源 | 许可与处理 |
| --- | --- | --- |
| 项目原创 Python、界面与自有图标 | 本仓库 | PolyForm Noncommercial 1.0.0；完整原文在根目录 LICENSE，作者声明在 NOTICE |
| design-systems 的 Lens 和 Overture 改编 | 固定提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e` | MIT，保留 DayDreamInAReverie 的版权、完整许可证和修改/来源记录；不改为项目的非商业许可 |
| Noto Sans SC 可变字体（未修改） | google/fonts `2894aab31764f10f29c421bdfd2340d3b382d384`，`ofl/notosanssc/NotoSansSC[wght].ttf` | SIL OFL 1.1；Adobe 版权及完整许可在 `licenses/NotoSansSC-OFL.txt`，来源/摘要在 `frontend/assets/fonts/ORIGIN.json`；允许随软件嵌入分发，不改为 PolyForm |
| CPython | 3.12 | PSF 及其附带声明；构建复制所用 Python 的完整 LICENSE.txt |
| Electron / Chromium / 内置 Node | Electron 45.0.0 官方 Windows x64 ZIP | Electron MIT 和完整 LICENSES.chromium.html 随包保留；官方 ZIP SHA256 固定，原产品图标/版本适配后不保留失效上游签名 |
| PySide6 / Shiboken6、使用的 Qt 模块 | 6.12.0；WebEngine wheel 6.12.0.140 | 使用社区版的 LGPL 路径；附 LGPLv3 及其要求的 GPLv3 文本，保留原 package 附件；Qt/Chromium 第三方声明另附 |
| Qt 内嵌第三方与 Chromium | 所用 Qt 6.12 / WebEngine 6.140 系列的官方模块声明 | BSD、MIT、Apache、LGPL 等多种许可证；保存官方署名文本、来源和摘要，保守保留部分平台/可选项声明 |
| PyInstaller / hooks | 6.17.0 / 2026.8 | 构建工具，GPL 与 bootloader exception；保留原许可附件，不将本项目改成 GPL |
| pymediainfo / MediaInfoLib | pymediainfo 7.0.1 官方 Windows wheel | Python 包 MIT；附带 MediaInfoLib 采用 BSD 2-clause 路径，完整原文及附带第三方说明在 licenses/pymediainfo-MIT.txt 与 MediaInfo-License.html，官方 wheel 和成员 SHA256 记录于 SOURCES.json |

运行包不需要用户另装 Node 或 Python：Electron 包含自己的 Node/Chromium，Python 服务与 Qt 在线窗口独立冻结。开发 Node 22+ 用于可选检查，Python 依赖锁定在 `requirements-lock.txt`。Qt 兼容源码入口仍保留，旧 Tkinter/早期 Qt 工作台已移除。

## 0.10.0 Electron 运行包

固定官方 [Electron 45.0.0 源码](https://github.com/electron/electron/tree/v45.0.0)与 [Windows 运行时及校验](https://github.com/electron/electron/releases/tag/v45.0.0)。对应 Chromium、V8、Node 和 FFmpeg 等依赖版本由该标签的 DEPS、构建说明及官方运行包 `LICENSES.chromium.html` 追溯；[Electron 构建步骤](https://www.electronjs.org/docs/latest/development/build-instructions-gn)保留依赖获取流程。第三方 MIT/BSD/LGPL/Apache 等独立权利不改为本项目非商业许可。

主页面由 Electron 直接呈现，不再经过 Qt Quick 整页纹理；Qt 保留无界面业务事件循环和独立 Widgets/WebEngine 在线窗口。本包没有应用 QML 插件树，不将旧 rc.12 的 18 模块清单当成本次载荷。Qt 必要 DLL 在 BUILD_MANIFEST 枚举，排除 Charts/3D/Graphs/Pdf 等未用模块。Qt/字体位于 `python/_internal/`，可按 LGPL 要求替换；包内校验只供核对下载，不阻止运行时替换。

重建本版使用 `.venv-web/Scripts/python.exe scripts/build_electron.py --zip`。ZIP 同时包含项目声明、Electron 原文/Chromium 总声明、Python/Qt/MediaInfo/字体等原始许可。PresentMon/PyWinRT 诊断工具不进入应用。基本检查限定于实际分发内容，不替代其他组件的授权审查。

阶段十八使用 MediaInfo 只读分析内封字幕轨，符合所选语言即视为已满足需求，不导出、转码或改写视频。解析 DLL 在隐藏的受限助手进程中使用只读缓冲区，忽略引用文件和连续文件名探测；固定本地解析入口、读取预算、超时和取消保护保留。应用不需要安装 FFmpeg、MediaInfo 命令行或额外 API Token。只检查字幕轨语言/标题等元数据，不声称 OCR 识别烧录在画面的字幕，也不验证实际翻译质量或时间轴。

阶段十的 RAR/7z 读取使用 Windows 系统组件 `%SystemRoot%/System32/tar.exe`（libarchive），不复制或捆绑系统文件。当前环境为 libarchive 3.8.8；其他 Windows 版本的格式能力可能不同，缺失/不支持会提示选用 ZIP。ZIP 和直接字幕仍使用 Python 标准库。字体通过 Qt 注册和本地 CSS 加载，不安装系统字体或联网取字体。

阶段十一的原生图标使用已有 PySide6 的 QtSvg（LGPL 路径），矢量路径和背景绘制为项目自有代码；没有新增 pip 依赖，也没有提取或分发用户参考图中的素材。QtSvg 发布者声明已在现有许可资料中。原 Lens/Jelly 文件及其 MIT 来源记录保持。

## 兼容性检查的结论与边界

根目录 LICENSE 只适用于本项目原创部分。MIT 组件允许在保留声明的条件下复用；Qt LGPL 允许在满足其条件的前提下与采用其他条款的应用组合。本项目没有把 Qt 或 MIT 组件重新许可为 PolyForm，也没有通过修改 MIT 原文添加禁止商用条款。

PySide6 wheel 仅附商业许可文本不等于只能商业授权：[官方 PyPI 说明](https://pypi.org/project/PySide6/6.12.0/)明确其 wheel 内容适用于开源和商业两种方式，安装模块头部同时列出 LGPL/GPL 选项。原附件保留用于溯源；本项目不声称持有 Qt 商业许可证。

旧候选包的默认 QtQml hook 收集了整个 QML 插件目录，其中包括未使用的 Charts、3D 等模块。rc.6 原生宿主明确收集 QtQuick/QtQml、Basic Controls/Templates、Layouts、Dialogs、Shapes、folderlistmodel、QtWebEngine/ControlsDelegates 和 QtWebChannel 共 18 个运行模块，清单在 `scripts/qml_payload.py`；不收集其他样式、designer、Charts、3D、Timeline 等模块。发布检查逐文件核对 QML 清单和摘要，实际 Qt DLL 清单在 BUILD_MANIFEST。Qt Quick Controls 的 [LGPLv3 路径](https://doc.qt.io/qt-6.12/qtquickcontrols-index.html#license-and-attributions)已核对，随包 QML 头部保留 Qt 原署名及 LGPL 选项。Material 样式的 Angular 阴影实现不在本次 Basic 白名单中，没有引入该素材。

新增 shader 为本项目自有源码。构建机器可用 PySide6 自带 `qsb.exe --glsl "100 es,120,150" --hlsl 50 --msl 12 -o frontend/native/hdr.frag.qsb frontend/native/hdr.frag` 重新生成已提交的 shader；正常运行不需要 qsb 或开发服务器。原生宿主仍使用现有 6.12 wheels，没有新增 pip 依赖。整个 onedir 的 QML/plugin/DLL 保持可替换，不将第三方 QML 改为 PolyForm。

这是针对所用组件的基本兼容性、署名和许可文件检查，不是对所有可选开发插件的授权。以后新增库、启用 QML 模块或修改 Qt 库时应重新检查。

## 替换或重建 LGPL 库

1. 发布采用 onedir。Qt DLL 位于 `_internal/PySide6/`，PySide `.pyd`、Shiboken 和 WebEngine helper 也保持独立；没有签名或哈希强制校验阻止库替换。
2. 为调试修改的 LGPL 库而修改库部分或进行必要的逆向工程，不受本项目针对原创部分的商业限制妨碍。具体以随附 LGPL 为准。
3. 可使用 ABI、架构及编译器匹配的修改版 DLL/绑定替换；或使用本仓库源代码与 `scripts/build.py` 重新构建。替换后包内 SHA256 会改变，这是预期行为。
4. 必须同步使用匹配版本的 Core/Gui/Widgets/WebEngine、资源、locales 和 QtWebEngineProcess。混用不兼容的 Qt DLL 可能无法启动。

对应公开源码与构建说明：

- [Qt 6.12.0 模块源码](https://code.qt.io/cgit/qt/qt5.git/tree/.gitmodules?h=v6.12.0)，各模块选择相应版本标签。
- [PySide/Shiboken 6.12.0](https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.12.0)及[官方构建步骤](https://doc.qt.io/qtforpython-6/building_from_source/index.html)。
- [Qt WebEngine 6.140 分支](https://github.com/qt/qtwebengine/tree/6.140)及其 Chromium 子模块；实际 API 报告 WebEngine 6.140.0 / Chromium 140.0.7339.225。审查时该分支引用为 [`e4d8df13c71ea53ac2de3c75d47585bcc0da815d`](https://github.com/qt/qtwebengine/tree/e4d8df13c71ea53ac2de3c75d47585bcc0da815d)，这是检查时的固定源码入口，不冒称已从 wheel 证明了精确构建提交。克隆对应源码时须初始化其 Chromium 等子模块，单个 GitHub 自动 ZIP 不含子模块内容。
- [Qt LGPL 原文](https://doc.qt.io/qt-6/lgpl.html)与[WebEngine 许可/第三方声明](https://doc-snapshots.qt.io/qtwebengine/qtwebengine-licensing.html)。

每份二进制 Release 应同时提供应用源码 ZIP、LICENSE、NOTICE、THIRD_PARTY_NOTICES、许可证目录、依赖/源码链接和构建方法。不得单独上传一个丢失这些材料的 EXE。第三方源码入口和版本信息是提供对应源码的线索；如所用版本的对应源码无法公开取得，先解决该缺项再公开分发该版本二进制。

## 维护许可证资料

`licenses/SOURCES.json` 记录下载 URL 和文件 SHA256；根目录 LICENSE 与官方 PolyForm 原文副本逐字节相同。Qt 模块声明来自实际使用系列的发布者文档，可能保守包含未启用平台或可选功能，不代表程序启用了这些功能。

`scripts/collect_public_licenses.py` 仅在维护时下载许可文本，不执行下载的文件。正常启动和构建使用已存入仓库的材料，不需要联网。更新依赖后应重新收集并审查，不把不同版本的材料默认为完全相同。
