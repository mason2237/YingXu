# 依赖、署名与重建

当前本地候选版本 0.12.0-rc.2。源码与运行包仅使用 Electron + Python；核心额外依赖为 pymediainfo。按需独立同步 worker 另附 requirements-sync.txt 的固定依赖，两个私有 EXE 共享同一 Python/_internal。没有 Qt；GuessIt 对照库不分发。

## 实际组件

YX-02 源码提供可选 GuessIt 4.4.0 对照适配器，默认关闭且没有加入上述运行依赖或发布包。隔离 wheel、许可证及冻结替换实验见 [可选解析器试验](research/subtitle-upgrade-2026-11/GUESSIT_TRIAL.md)。适配器原创代码不改变第三方库许可；未来若分发库本身，须单独汇集 LGPL/GPL 原文、库源码、依赖署名与替换说明。

| 组件 | 固定版本/来源 | 许可及材料 |
| --- | --- | --- |
| 映序原创代码与图标 | 本仓库 | 官方完整 PolyForm Noncommercial 1.0.0；LICENSE、NOTICE |
| Electron、Chromium、内置 Node | Electron 45.0.0 官方 Windows x64 ZIP | Electron MIT 及完整 LICENSES.chromium.html，原文随包保留 |
| CPython | 构建清单中的 Python 3.12 版本 | 原解释器完整 LICENSE.txt |
| pymediainfo / MediaInfoLib | pymediainfo 7.0.1 Windows wheel | MIT / BSD 原文及附带第三方声明，DLL/wheel 摘要在 licenses/SOURCES.json |
| design-systems Lens 与 Overture 改编 | 7a424c93b9be13cf835b91ea67495fec2ec0584e | MIT，DayDreamInAReverie 署名、LICENSE、UPSTREAM.md、19 份 Lens 的 ORIGIN.json |
| Noto Sans SC，未修改 | google/fonts 2894aab31764f10f29c421bdfd2340d3b382d384 | OFL 1.1、Adobe 版权及 Reserved Font Name，字体来源和 SHA256 随源码保留 |
| PyInstaller / hooks 及构建包 | requirements-build.txt 固定版本 | 构建工具原许可附件，PyInstaller bootloader exception |

第三方独立许可不会被重新限制为非商业；非商业要求只适用于映序原创部分。没有通过修改 MIT 原文添加禁止商用条款。构建核对官方 Electron ZIP、MediaInfo DLL、字体及未修改 Lens 的来源摘要。

当前包不捆绑 PresentMon 或 PyWinRT，它们仅用于可选诊断，许可原文保留在源码 licenses/。RAR/7z 使用用户 Windows 的 `%SystemRoot%/System32/tar.exe`，不复制系统文件；格式支持不足时提示使用 ZIP。ZIP 和直接字幕由 Python 标准库处理。

## 源码与重建

可选同步 worker 使用 ffsubsync 0.5.1（MIT）、NumPy（BSD，含附带许可）、pysubs2/srt（MIT）、ffmpeg-python（Apache-2.0）、WebRTC VAD wheel（MIT/BSD 声明）及 requirements-sync.txt 的必要依赖；完整原文随包，实际清单/版本/源码来源摘要在 SYNC_RUNTIME.json。上游入口 [ffsubsync](https://github.com/smacke/ffsubsync)、[NumPy](https://github.com/numpy/numpy)、[pysubs2](https://github.com/tkarabela/pysubs2)、[srt](https://github.com/cdown/srt)、[ffmpeg-python](https://github.com/kkroening/ffmpeg-python)、[webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels)。

仅启用 UTF-8 参考与 WebRTC，按已审查清单以 `--no-deps -r requirements-sync.txt` 安装到隔离 `.venv-sync`，另装相同 requirements-build.txt 构建工具。auditok、chardet/faust-cchardet、imageio-ffmpeg、模型不分发。FFmpeg 由用户选择本机工具；实验构建 7.1 的 SHA256 仅在阶段证据中登记，不能据此宣称已经汇集其全部对应源码或将其捆绑。构建完整候选时附 `--with-sync`；它合并相同 Python 文件及标准库，冲突即中止。

该发行所用 wheel 来源清单保存在 licenses/sync-WHEEL-ORIGINS.json，与随包 SYNC_RUNTIME.json 一致。重建同步运行时时，先取得并审查固定版本的实际安装 wheel，再把各自 wheel 名、SHA256 和许可元数据保存为 work/tools/sync-install-review.json（格式见该清单）。不要把原发行摘要当成新下载文件已经核验的证明。srt 3.5.3 原版从官方源包本地构建 wheel；PyPI 源包 SHA256 为 4884315043a4f0740fd1f878ed6caa376ac06d70e135f306a6dc44632eed0cc0，本地构建 wheel 的时间戳可能使其摘要不同。普通不带同步引擎的构建不需要该清单。

NumPy wheel 的完整许可涵盖 BLAS/LAPACK 和 GCC runtime 及其适用例外，原文全部保留。tqdm 4.67.1 的 MPL-2.0/MIT 原声明、官方完整 MPL 及未修改 Python 源码一并放在 licenses/sync-runtime/tqdm/，其源码仍适用原许可，不受映序原创非商业限制；固定源码入口 https://github.com/tqdm/tqdm/tree/v4.67.1。

运行包不需要用户安装 Node、Python 或开发服务器。源码运行见 [开发指南](DEVELOPMENT.md)，当前构建入口只有 scripts/build_electron.py。

```powershell
py -3.12 -m venv .venv-build
.venv-build/Scripts/python.exe -m pip install --only-binary=:all: -r requirements-build.txt
.venv-build/Scripts/python.exe scripts/setup_electron.py
.venv-build/Scripts/python.exe scripts/build_electron.py --zip
```

第三方源码入口：

- [Electron 45.0.0](https://github.com/electron/electron/tree/v45.0.0)、[官方构建说明](https://www.electronjs.org/docs/latest/development/build-instructions-gn)；其 DEPS 和随包 Chromium 总声明追溯 Chromium、Node、V8、FFmpeg 等组件。
- [CPython 3.12](https://github.com/python/cpython/tree/3.12)；准确解释器版本见 BUILD_MANIFEST.json。
- [pymediainfo 7.0.1](https://github.com/sbraz/pymediainfo/tree/7.0.1)、[MediaInfoLib](https://github.com/MediaArea/MediaInfoLib)；实际 wheel、DLL 来源及摘要见 licenses/MediaInfo-ORIGIN.json。
- [design-systems 固定源码](https://github.com/ruiqichenbiec/design-systems/tree/7a424c93b9be13cf835b91ea67495fec2ec0584e)；项目适配器与原模块分开维护。
- [Noto Sans SC 固定源码](https://github.com/google/fonts/tree/2894aab31764f10f29c421bdfd2340d3b382d384/ofl/notosanssc)。

发布包保留完整许可证、署名、组件清单、来源记录和源码 ZIP。包内 SHA256 供核对下载，不是阻止用户替换第三方库的运行时校验。更新组件后需重新审查版本、必要原文与对应源码入口。

Qt 旧版的 LGPL 资料和构建说明对应已发布历史标签，例如 [v0.10.0-rc.1 的依赖说明](https://github.com/mason2237/YingXu/blob/v0.10.0-rc.1/docs/DEPENDENCIES.md)。它们不表示当前包包含 Qt，不应使用当前构建脚本重建旧标签。

许可检查只涵盖实际分发组件，不能保证任意未来库或所有可选插件的授权。详见 [当前许可检查](../release/LICENSE_STATUS.md)。
