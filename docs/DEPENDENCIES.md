# 依赖、署名与库替换

## 当前使用范围

| 部分 | 版本/来源 | 许可与处理 |
| --- | --- | --- |
| 项目原创 Python、界面与自有图标 | 本仓库 | PolyForm Noncommercial 1.0.0；完整原文在根目录 LICENSE，作者声明在 NOTICE |
| design-systems 的 Lens 和 Overture 改编 | 固定提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e` | MIT，保留 DayDreamInAReverie 的版权、完整许可证和修改/来源记录；不改为项目的非商业许可 |
| CPython | 3.12 | PSF 及其附带声明；构建复制所用 Python 的完整 LICENSE.txt |
| PySide6 / Shiboken6、使用的 Qt 模块 | 6.12.0；WebEngine wheel 6.12.0.140 | 使用社区版的 LGPL 路径；附 LGPLv3 及其要求的 GPLv3 文本，保留原 package 附件；Qt/Chromium 第三方声明另附 |
| Qt 内嵌第三方与 Chromium | 所用 Qt 6.12 / WebEngine 6.140 系列的官方模块声明 | BSD、MIT、Apache、LGPL 等多种许可证；保存官方署名文本、来源和摘要，保守保留部分平台/可选项声明 |
| PyInstaller / hooks | 6.17.0 / 2026.8 | 构建工具，GPL 与 bootloader exception；保留原许可附件，不将本项目改成 GPL |

运行包不需要 Node；Node 22+ 只用于可选前端开发检查。旧 Tkinter 入口使用标准库，旧 Qt 工作台另用 `requirements-qt.txt`。

## 兼容性检查的结论与边界

根目录 LICENSE 只适用于本项目原创部分。MIT 组件允许在保留声明的条件下复用；Qt LGPL 允许在满足其条件的前提下与采用其他条款的应用组合。本项目没有把 Qt 或 MIT 组件重新许可为 PolyForm，也没有通过修改 MIT 原文添加禁止商用条款。

PySide6 wheel 仅附商业许可文本不等于只能商业授权：[官方 PyPI 说明](https://pypi.org/project/PySide6/6.12.0/)明确其 wheel 内容适用于开源和商业两种方式，安装模块头部同时列出 LGPL/GPL 选项。原附件保留用于溯源；本项目不声称持有 Qt 商业许可证。

旧候选包的默认 QtQml hook 收集了整个 QML 插件目录，其中包括未使用的 Charts、3D 等模块。新版使用项目构建 hook 保留实际原生依赖、不收集整个 QML 树；发布校验拒绝这些多余的 GPL/商业模块。不能仅凭 PySide6 总包的元数据推断所有 Qt 插件都可按 LGPL 分发。

这是针对所用组件的基本兼容性、署名和许可文件检查，不是对所有可选开发插件的授权。以后新增库、启用 QML 模块或修改 Qt 库时应重新检查。

## 替换或重建 LGPL 库

1. 发布采用 onedir。Qt DLL 位于 `_internal/PySide6/`，PySide `.pyd`、Shiboken 和 WebEngine helper 也保持独立；没有签名或哈希强制校验阻止库替换。
2. 为调试修改的 LGPL 库而修改库部分或进行必要的逆向工程，不受本项目针对原创部分的商业限制妨碍。具体以随附 LGPL 为准。
3. 可使用 ABI、架构及编译器匹配的修改版 DLL/绑定替换；或使用本仓库源代码与 `scripts/build_web.py` 重新构建。替换后包内 SHA256 会改变，这是预期行为。
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
