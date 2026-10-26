# Third-party code adopted for the Web workspace

## Electron desktop release (0.10.0-rc.1)

- Electron 45.0.0: MIT, Copyright (c) Electron contributors and Copyright (c)
  2013-2020 GitHub Inc. Original text: `licenses/electron-LICENSE.txt`.
  The reviewed official Windows runtime is downloaded without npm scripts;
  its `LICENSE` and `LICENSES.chromium.html` remain alongside `electron.exe`.
  The complete `LICENSES.chromium.html` accompanies the runtime; the original
  Electron MIT notice is retained in licenses/. The product icon and version
  are adapted; no valid upstream signature is claimed after this modification.
  Runtime provenance and package hashes are in BUILD_MANIFEST.json.
- Optional HDR capture diagnostics use PyWinRT under MIT. They are installed
  only in `work/tools/hdr-python/`, outside the application environment; exact
  diagnostic versions are in `desktop/electron/requirements-probe.txt`.
  Original notice: `licenses/PyWinRT-LICENSE.txt`. These tools are not required
  to run the prototype. Each installed wheel retains its own original notice.
- PresentMon 2.6.0 is an optional external diagnostic tool from Intel's official
  GameTechDev/PresentMon release. It is not bundled or installed as a service.
  Its MIT text is retained in `licenses/PresentMon-LICENSE.txt`.
- The release retains existing Python/Qt Core and all existing third-party
  obligations. It does not change the independent licenses or original authors
  of the adopted Lens modules. The online browser uses the existing separate
  Qt Widgets/WebEngine helper; no application QML plugin tree is distributed.
  Actual Qt DLLs and source/replacement links are recorded in the manifest
  and docs/DEPENDENCIES.md.


## Current Qt release baseline (0.9.0-rc.12)

The project's original portions use the unmodified PolyForm Noncommercial
License 1.0.0 in LICENSE; the project notice is in NOTICE. That restriction does
not relicense or remove the independent rights of the components below.

- design-systems: MIT, Copyright (c) 2026 DayDreamInAReverie. Original source,
  adaptation notes and provenance are retained as detailed below. The binary
  bundle carries licenses/design-systems-* rather than the entire source tree.
- Python: the exact interpreter's supplied LICENSE.txt is copied into the bundle.
- Noto Sans SC: an unmodified variable TTF from google/fonts commit
  `2894aab31764f10f29c421bdfd2340d3b382d384`, distributed under SIL OFL 1.1.
  Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name
  'Source'. The complete original notice/license is `licenses/NotoSansSC-OFL.txt`;
  asset origin and SHA256 are in `frontend/assets/fonts/ORIGIN.json` in the source.
  This font remains independently licensed and is not subject to PolyForm's
  noncommercial restriction. It is bundled for offline rendering, not installed
  into the user's system fonts.
- Qt/PySide6/Shiboken6: community LGPL licensing for the modules actually used.
  GPL companion texts required by LGPL and the original wheel attachments are
  included. See docs/DEPENDENCIES.md for dynamic replacement, source and build
  instructions. No Qt commercial license is claimed.
- Qt/Chromium embedded components: primary-publisher attribution texts and
  licenses are in licenses/; SOURCES.json records URLs and content hashes.
  Qt's copied documentation carries its GFDL notice and accompanying text.
- PyInstaller/hooks: build tools with their own GPL/bootloader exceptions;
  original license attachments are retained for traceability.

Runtime Qt DLLs are enumerated in BUILD_MANIFEST.json. The whole QML plugin tree
and unused Charts/3D/Graphs/Pdf modules are excluded. Installed development
wheel metadata describes the environment, not a promise that every optional
module is distributed. Additional Qt plugins require their own review.

## Frontend adoption history

The stage 6 preview includes code from [design-systems](https://github.com/ruiqichenbiec/design-systems),
commit `7a424c93b9be13cf835b91ea67495fec2ec0584e`, under the MIT License.
Copyright (c) 2026 DayDreamInAReverie.

The full license and per-file changes are in
`frontend/vendor/design-systems/LICENSE` and `UPSTREAM.md`.
Stage 6.1 adopts 19 unchanged Lens modules/styles; each original path and Git
blob SHA is recorded in `frontend/vendor/design-systems/lens/ORIGIN.json`.
Qt-specific canvas lifecycle and business integration are in separate project
adapters, with no changes to those recorded source files. No upstream fonts,
photos, video, three.js bundle, build tools or whole showcase is included.
Stage 6.2 adapts the Overture motion.transition/focusPoint source in
`overture/src/dynamics.js` into `frontend/vendor/design-systems/theme-transition.js`.
It retains the trigger-centered iris principle with a shorter duration,
application preferences, cancellation and reduced-motion handling. This is an
adaptation, not a byte-identical copy; the same fixed commit and MIT apply.
Stage 6.3a extends the existing original Lens integration to review/preview
action buttons. Its procedural list vapor is project-owned, not a claim of
adopting the Lattice particle-field source. The 19 original Lens files remain
unchanged and retain the existing provenance record.
Stage 6.3b adds a targeted adaptation of Overture Toast, CommandPalette and
Tooltip in `frontend/vendor/design-systems/workspace-overlays.js` and extends
the existing modal adaptation with Drawer motion. Source, fixed commit, reviewed
SHA256 and changes are recorded in `UPSTREAM.md`; the same MIT notice applies.
Loading uses the unchanged Lens createOpticalProgress DOM factory. No Overture
registry, example undo, media, fonts, build scripts or new dependency is included.
Stage 8a uses the unchanged Lens JellyController for all remaining semantic
buttons, with bounded travel, lifecycle guards and application drag safety in
glass-controls.js. Action groups and a reusable modal footer retain original
Lens GPU optics; other buttons use project CSS glass. The unchanged optical
progress factory now feeds an original Lens renderer with real task values and
wave motion. No original Lens file is edited or replaced by these adapters.
Stage 8b recorded incomplete package attachments and an unavailable internal
Chromium credits page. Stage 8c resolves the basic inventory through official
PyPI licensing statements, explicit standard texts and the publisher's Qt/
Chromium attribution pages. It does not claim that the internal credits export
succeeded. Detailed scope and source/replacement instructions accompany the
release in LICENSE_STATUS.md and docs/DEPENDENCIES.md.

## 视频内嵌字幕信息

pymediainfo 7.0.1 使用 MIT，版权 Patrick Altman、Louis Sautier；完整原文见 licenses/pymediainfo-MIT.txt。Windows wheel 附带的 MediaInfoLib 使用其 BSD 2-clause 许可路径，MediaArea.net SARL 版权及第三方说明完整保留于 licenses/MediaInfo-License.html。来源与 wheel/文件摘要记录在 licenses/SOURCES.json。项目的非商业限制不覆盖这些第三方权利。
