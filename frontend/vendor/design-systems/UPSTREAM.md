# Adopted design-system code

Upstream: https://github.com/ruiqichenbiec/design-systems
Commit: 7a424c93b9be13cf835b91ea67495fec2ec0584e
License: MIT, Copyright (c) 2026 DayDreamInAReverie. Full text: LICENSE.

Stage 16 removes the application command palette and its adapted commandList
helper. Toast/Tooltip and their attribution remain. Settings dismissal now uses
a 140ms opacity-only fade with matching backdrop tint, painted-frame settling,
reopen cancellation and reduced-motion fallback; other desktop dialogs keep
their existing immediate lifecycle. Original Lens source files remain intact.

- focus.js: copied unchanged from lens/lab/design-system/focus.js.
- modal.js: adapted from the modal helper in overture/src/overlays.js. Removed
  showcase data, audio, iris/GPU dependencies; shortened transitions and added
  focus restoration and a generation guard for interrupted closes.
  Native Qt desktops additionally use immediate dialog open/close to avoid
  top-layer blur/transform surface churn; browser previews retain short motion.
  Native overlay wheel scrolling is committed on the main thread so its text
  and Qt HDR source texture stay in step; standard page scrolling is unchanged.
- lens/: 19 unchanged Lens ES modules and styles, including the original
  GlassRenderer, JellyController, 18 public component factories, optical
  controls, sound synthesis and their complete local dependency closure.
  ORIGIN.json records each upstream path and Git blob SHA. .gitattributes
  preserves LF endings; source checks verify exact bytes against those SHAs.
- theme-transition.js: adapted from motion.transition/focusPoint in
  overture/src/dynamics.js, with the usage contract reviewed in core.js.
  Converted to an ES module, shortened 760ms to 180ms, added cancellation,
  hidden/reduced/unsupported fallbacks and snapshot-failure diagnostics.
  The application adapter flushes GPU palette changes synchronously: Chromium
  suspends requestAnimationFrame during View Transition snapshot updates.
  No Overture registry, showcase data, theme names, media or audio is loaded.
- workspace-overlays.js (6.3b): adapts Toast's remaining-time meter and pause
  lifecycle, CommandPalette's filtering/keyboard selection, and Tooltip's
  focus/Escape behavior from overture/src/overlays.js at the same commit.
  Reviewed source SHA256: 35d8ed1b545dda4a3ec012a76df627bdf81db6ba12e9db7b7b3412308a85ca74.
  Changes: ES module, text-only application actions, IME and disabled guards,
  asynchronous action locking, generation-safe dismissal, visibility pause,
  event cleanup, and native popover placement within the active dialog.
  Removed example collections/undo, audio, photography and the Overture registry.
- modal.js (6.3b): additionally adapts the original Drawer horizontal entrance
  and exit, shortened to 170/110ms; supports immediate breakpoint restoration
  and an application overlay event. Existing focus and interrupted-close guards
  remain. No original Lens file changes are involved.
- WorkspaceFeedback uses the unchanged Lens createOpticalProgress factory with
  real adapter values, wave disabled and DOM presentation; no extra GL renderer
  is created. The application loading/empty/error layout and result distribution
  remain project-owned; no claim is made of adopting Overture's media examples.

The original stage 6 shader remains only for the development comparison.
New integration lives outside lens/ in the project's adapters. Optical math
and upstream component implementations remain unchanged; Qt canvas lifecycle,
preferences, rendering counters and business callbacks are adapted there.

Stage 6.3a adds liquid-actions.js outside this directory: action groups share
the original Lens compositor/gestures, clipped to real stable buttons. The
list-mist.js vapor shader is project-owned, not copied from Lens or Lattice.
No new third-party source or license is introduced by those two adapters.

The workspace, preview adapter, virtual list, icons and transient particles
are this project's implementation. No photos, fonts, three.js, repository
build tools, whole showcase pages or external assets are copied.

Stage 20A updates the already adapted modal.js and theme-transition.js to
consult the project's shared desktop-host capability instead of checking
Qt globals directly. Focus, close timing and transition policy are preserved
for both hosts. The 19 recorded upstream Lens source files remain unchanged.
