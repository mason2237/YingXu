# 本轮分发许可检查

日期：2026-10-23。范围为当前应用的依赖兼容性、必要署名和许可证文件。

2026-10-26 增量说明（0.10.0-rc.1）：新增固定 Electron 45.0.0 官方运行时，MIT 原文和完整 Chromium 总声明随包保留，对应源码/构建入口见 docs/DEPENDENCIES.md。与原创 PolyForm 非商业许可没有发现直接分发冲突，第三方权利独立。独立 Qt 在线窗口保留；本次无应用 QML 插件树，必要 DLL 由 manifest 枚举并排除未用扩展。图标/版本修改后移除失效的上游证书表，应用标注未签名。沿用已审核的 Qt、字体、MediaInfo 等许可与来源摘要，不捆绑诊断工具。旧 rc.12 的 QML/许可记录作为历史保留。

2026-10-24 增量说明（0.9.0-rc.6）：新增 Qt Quick 原生 HDR 宿主，使用现有 Qt/PySide6 6.12 wheels。`scripts/qml_payload.py` 明确列出 18 个实际运行 QML 模块；只分发 Basic Controls，保留模块原署名/LGPL 头部；排除 designer、其他 Controls 样式及 Charts/3D/Timeline。Controls 的 LGPLv3 许可路径与现有 LGPL/GPL 原文已核对，Material 专属 Angular 阴影未进入白名单；Shapes、Dialogs/Templates 等为 Qt Declarative 的现有 LGPL 模块。QML、插件和 DLL 逐文件摘要随 BUILD_MANIFEST 记录，继续提供对应 Qt 6.12 源码入口和库替换方式；不修改或重许可第三方文件。没有新增字体、图片素材或 pip 依赖。

2026-10-24 增量说明（0.9.0-rc.1）：在线推荐/导入仅使用既有 PySide6 和 Python 标准库，未增加第三方依赖。miuix 风格面板由本项目自行实现，没有复制其 Kotlin/Compose 代码或素材。沿用以下许可审查；构建时继续校验官方许可文件摘要、署名资料和实际 Qt 打包范围。

2026-10-24 增量说明（0.9.0-rc.3）：新增未修改的 Noto Sans SC 字体，来自 google/fonts 固定提交 `2894aab31764f10f29c421bdfd2340d3b382d384`。SIL OFL 1.1 允许随软件嵌入和再分发；保留 Adobe 版权、Reserved Font Name 和完整官方原文 `licenses/NotoSansSC-OFL.txt`，来源/摘要见源码 `frontend/assets/fonts/ORIGIN.json`。字体未改名/修改，不单独售卖，独立 OFL 权利不受 PolyForm 限制。未新增 Python 依赖；RAR/7z 使用系统已有 tar，不分发 Windows 系统文件。未发现此次字体打包与现有许可的直接冲突。

- 原创部分：按版权所有者明确选择，使用未修改的 PolyForm Noncommercial License 1.0.0。完整原文在 LICENSE，作者及商业授权说明在 NOTICE。未经另行授权不得将原创部分用于商业用途。
- design-systems：MIT，完整许可、DayDreamInAReverie 署名、19 份原 Lens 的来源和修改说明保留在 `licenses/design-systems-*`；其独立 MIT 权利不改为非商业许可。
- Qt/PySide：按社区版 LGPL 路径使用。官方 PyPI 6.12.0 页面明确 wheel 内容同时适用于开源和商业许可，因此仅附商业文本并不意味着排除了元数据与源文件头部明示的 LGPL 选项；没有声称持有商业许可证。完整 LGPL/GPL 配套文本、原包附件及所用 Qt 模块的第三方声明随包保留。
- 默认 QML 全目录收集会带入本工具未使用的 GPL/商业模块。项目构建 hook 停止整树收集，rc.6 仅允许明确的运行模块，发布校验拒绝清单外 QML 及 Charts/Graphs/3D/Pdf 等模块。最终实际 Qt DLL 清单在 BUILD_MANIFEST.json。
- Qt/Chromium 第三方声明来自发布者官方文档，URL/摘要在 `licenses/SOURCES.json`。未伪称从无法加载的 chrome://credits 页面成功导出。文档声明保守包含少量未启用平台/可选组件。
- Python 自带许可证、PyInstaller 和 hooks 原许可附件随包保存。PyInstaller 的 bootloader exception 不要求将应用原创部分改为 GPL。
- Qt 为可替换动态库，没有强制哈希/签名限制替换。修改库及为调试库修改而必需的逆向工程不被项目条款妨碍。依赖、对应源码入口和重新构建步骤在 `docs/DEPENDENCIES.md`。

基本检查未发现本次所用模块与项目许可的直接冲突；此结论限定于实际打包范围。发布二进制时必须同时提供源码、许可材料与对应第三方源码/构建入口；不能将所有 Qt 可选插件默认为 LGPL，也不能把署名目录当成对任何未来依赖的许可保证。

官方依据：

- https://polyformproject.org/licenses/noncommercial/1.0.0
- https://pypi.org/project/PySide6/6.12.0/
- https://pypi.org/project/PySide6-WebEngine/6.12.0.140/
- https://doc.qt.io/qt-6/lgpl.html
- https://doc-snapshots.qt.io/qtwebengine/qtwebengine-licensing.html

阶段十八新增 pymediainfo 7.0.1：Python 包 MIT，官方 Windows wheel 附带 MediaInfoLib 的 BSD 2-clause 原文及第三方说明。许可证原文按 wheel 成员逐字复制到 licenses/pymediainfo-MIT.txt 和 MediaInfo-License.html；官方 wheel SHA256 及成员摘要在 licenses/SOURCES.json。与项目原创部分 PolyForm Noncommercial 的基本署名/分发要求兼容，第三方权利保持独立。没有引入 FFmpeg 或执行第三方安装脚本。
