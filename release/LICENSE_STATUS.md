# 分发许可检查

当前版本：0.12.0-rc.2 本地候选。检查日期：2026-11-09。
范围：实际分发组件的许可兼容性、署名、必要原文和来源校验。

核心业务使用 Python 标准库与原 pymediainfo。独立同步 worker 附 ffsubsync 0.5.1、NumPy、pysubs2、srt、ffmpeg-python、WebRTC VAD 及界面/编码等必要依赖；完整版本、来源摘要和许可见 SYNC_RUNTIME.json 与 licenses/sync-runtime/。这些组件以 MIT/BSD/Apache 等各自许可分发，不改变原创非商业许可。

NumPy wheel 的完整许可证还包含所带 BLAS/LAPACK/GCC 运行库条款及适用的 GCC Runtime Library Exception，不能概括为“全部第三方都是 MIT”。随包保留整个原文、例外与上游给出的源码入口；不修改或删去这些声明。构建器按实际文件汇集全部许可附件。

tqdm 4.67.1 采用 MPL-2.0/MIT 组合条款，随包保留原 LICENCE、Mozilla 官方完整 MPL-2.0 原文及未修改的 Python 源码（licenses/sync-runtime/tqdm/source/）和固定版本源码入口。官方原文来源与摘要见 licenses/MPL-2.0-ORIGIN.json。其独立源码不受映序原创非商业条款限制；Larger Work 不改变这些文件的许可。

明确排除 GPL auditok、chardet/faust-cchardet、ASR/模型和 imageio-ffmpeg；仅启用固定引擎的 UTF-8 参考与 WebRTC 路径。实验使用的 FFmpeg 7.1 Gyan 构建未分发，应用只在用户选择后运行其本机 FFmpeg，因此未把该测试二进制及其 GPL 源码义务混入当前 ZIP。未来如捆绑 FFmpeg，需另行提供精确构建及全部对应源码。

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
