# 依赖、署名与重建

当前版本 0.11.0-rc.3。源码与运行包仅使用 Electron + Python；额外 Python 运行依赖为 pymediainfo。Qt、PySide、Shiboken、QML 和旧 GUI 宿主已从当前源码及包中移除。

## 实际组件

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
