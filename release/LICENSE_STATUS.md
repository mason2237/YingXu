# 分发许可检查

当前版本：0.11.0-rc.3。检查日期：2026-10-27。
范围：实际分发组件的许可兼容性、署名、必要原文和来源校验。没有新增运行依赖。

| 组件 | 许可与随包材料 |
| --- | --- |
| 映序原创代码 | 官方完整 PolyForm Noncommercial 1.0.0；LICENSE、NOTICE |
| Electron 45.0.0 | MIT 原文及完整 LICENSES.chromium.html |
| Python | 解释器原许可全文 |
| pymediainfo / MediaInfo | MIT / BSD 原文、第三方声明及 DLL 来源摘要 |
| design-systems Lens | MIT 原文、原作者 DayDreamInAReverie 署名、固定提交和 19 份模块来源 |
| Noto Sans SC | OFL 1.1 全文、Adobe 版权、来源及字体摘要 |
| 构建工具 | PyInstaller bootloader exception 及所用构建包原许可附件 |

未发现当前实际载荷与原创非商业许可的直接分发冲突。第三方独立权利不被改为非商业许可，不修改其原文或移除署名。商业使用映序原创部分须取得版权所有者的单独授权。

构建校验官方 Electron ZIP、MediaInfo DLL、字体 SHA256、未改动 Lens 的 Git blob 和许可证来源摘要。当前包不含 Qt、PySide、Shiboken、旧 GUI 宿主或诊断工具；旧 Qt 版本的许可记录仅对应历史版本，见 CHANGELOG 与对应标签。

应用图标和版本资源写入后不保留失效的上游签名，应用明确标注未签名。没有声称持有可信代码签名证书。

[依赖与对应源码入口](../docs/DEPENDENCIES.md) · [第三方声明](../THIRD_PARTY_NOTICES.md)
