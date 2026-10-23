# 本轮分发许可检查

日期：2026-10-23。范围为当前应用的依赖兼容性、必要署名和许可证文件。

- 原创部分：按版权所有者明确选择，使用未修改的 PolyForm Noncommercial License 1.0.0。完整原文在 LICENSE，作者及商业授权说明在 NOTICE。未经另行授权不得将原创部分用于商业用途。
- design-systems：MIT，完整许可、DayDreamInAReverie 署名、19 份原 Lens 的来源和修改说明保留在 `licenses/design-systems-*`；其独立 MIT 权利不改为非商业许可。
- Qt/PySide：按社区版 LGPL 路径使用。官方 PyPI 6.12.0 页面明确 wheel 内容同时适用于开源和商业许可，因此仅附商业文本并不意味着排除了元数据与源文件头部明示的 LGPL 选项；没有声称持有商业许可证。完整 LGPL/GPL 配套文本、原包附件及所用 Qt 模块的第三方声明随包保留。
- 默认 QML 全目录收集会带入本工具未使用的 GPL/商业模块。项目构建 hook 停止整树收集，发布校验拒绝多余 QML 树及 Charts/Graphs/3D/Pdf 等模块。最终实际 Qt DLL 清单在 BUILD_MANIFEST.json。
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
