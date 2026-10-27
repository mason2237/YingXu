# Third-party notices

Current release: 0.11.0-rc.2. The application contains Electron and a frozen Qt-free Python service. Qt, PySide and Shiboken are not distributed.

The original application uses the unmodified PolyForm Noncommercial License 1.0.0. This does not relicense or limit independent MIT, BSD, OFL or other rights of third-party components.

## Runtime and build components

- **Electron 45.0.0:** MIT. Copyright (c) Electron contributors; Copyright (c) 2013-2020 GitHub Inc. Original text: `licenses/electron-LICENSE.txt`. The complete upstream `LICENSES.chromium.html` is distributed with the runtime. Application icon/version changes do not imply a valid upstream signature.
- **Python:** the exact interpreter's complete supplied `LICENSE.txt` is copied into the bundle. Its version is listed in `BUILD_MANIFEST.json`.
- **pymediainfo 7.0.1 / MediaInfoLib:** Python package MIT and bundled MediaInfo BSD 2-clause terms, including original third-party notices. Texts: `licenses/pymediainfo-MIT.txt` and `licenses/MediaInfo-License.html`; wheel and DLL provenance: `licenses/MediaInfo-ORIGIN.json` and `SOURCES.json`.
- **Noto Sans SC:** unmodified variable TTF from google/fonts commit `2894aab31764f10f29c421bdfd2340d3b382d384`, SIL OFL 1.1. Copyright 2014-2021 Adobe (http://www.adobe.com/), Reserved Font Name 'Source'. Full original text: `licenses/NotoSansSC-OFL.txt`; font origin/hash: `frontend/assets/fonts/ORIGIN.json`. Loaded locally, not installed into system fonts.
- **PyInstaller/hooks and build dependencies:** original license attachments are included under licenses/. PyInstaller's bootloader exception permits distribution of the application without changing its original license to GPL. Actual build versions are listed separately in the manifest.

## Adopted frontend code

[design-systems](https://github.com/ruiqichenbiec/design-systems), fixed commit `7a424c93b9be13cf835b91ea67495fec2ec0584e`, is MIT licensed. Copyright (c) 2026 DayDreamInAReverie.

The complete original license and adaptation records remain in `frontend/vendor/design-systems/LICENSE` and `UPSTREAM.md`. The 19 unchanged Lens modules/styles retain their original paths and Git blob hashes in `lens/ORIGIN.json`. Application lifecycle, geometry caching, business integration and procedural list vapor are separate project adapters, not replacements for the recorded original sources.

Overture transition/focus, modal/drawer, toast, tooltip and overlay adaptations are identified in UPSTREAM.md with their fixed source and changes. The application does not include the whole showcase, upstream photographs/video, three.js bundle or installation scripts. Optional showcase resources are not part of the production allowlist.

The binary bundle carries the original MIT text, author, provenance and modification records in `licenses/design-systems-*`.

## Optional diagnostics and historical releases

PresentMon 2.6.0 and PyWinRT are optional development diagnostics under their own MIT terms. Their original texts are retained in `licenses/PresentMon-LICENSE.txt` and `licenses/PyWinRT-LICENSE.txt`; neither tool is included in the application.

Historical Qt release notices remain in the corresponding Git tags, including v0.10.0-rc.1. Original license documents retained for that history do not mean Qt is shipped by this release.

See `docs/DEPENDENCIES.md` for versions, corresponding upstream source links and rebuild instructions. Each third-party license remains authoritative; this summary does not replace the original texts.
