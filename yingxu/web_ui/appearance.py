"""Appearance-only preferences. No paths, file jobs or arbitrary commands."""
import json

from PySide6.QtCore import QObject, QSettings, Signal, Slot, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWebEngineCore import QWebEngineScript


DEFAULTS = {"theme": "system", "glassEnabled": True, "strength": "enhanced",
            "particlesEnabled": True, "reducedMotion": False, "mistEnabled": True}
SETTINGS_KEY = "appearance/v1"
BACKGROUNDS = {"light": "#f5f7fa", "dark": "#13161c"}


def validated_patch(value):
    if not isinstance(value, dict) or not value or value.keys() - DEFAULTS.keys():
        raise ValueError("Unknown appearance preference")
    for key, item in value.items():
        if key == "theme":
            valid = item in ("light", "dark", "system")
        elif key == "strength":
            valid = item in ("standard", "enhanced")
        else:
            valid = type(item) is bool
        if not valid:
            raise ValueError("Invalid appearance preference")
    return value.copy()


def bootstrap_source(state):
    """DocumentCreation runs before DOM/CSS; stop observing once <html> exists."""
    payload = json.dumps(state, ensure_ascii=True, separators=(",", ":"))
    return """(() => {
      const state = %s;
      globalThis.__yingxuAppearance = Object.freeze(state);
      const apply = () => {
        const root = document.documentElement;
        if (!root) return false;
        root.dataset.theme = state.resolvedTheme;
        root.dataset.themePreference = state.theme;
        root.dataset.reduced = String(state.reducedMotion);
        root.dataset.appearanceBootstrapped = 'true';
        return true;
      };
      if (!apply()) {
        const observer = new MutationObserver(() => {if (apply()) observer.disconnect();});
        observer.observe(document, {childList:true, subtree:true});
      }
    })();""" % payload


class AppearanceBridge(QObject):
    changed = Signal(str)

    def __init__(self, style_hints, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings("YingXu", "SubtitleOrganizer")
        self.preferences = DEFAULTS.copy()
        self.system_theme = "dark" if style_hints.colorScheme() == Qt.ColorScheme.Dark else "light"
        try:
            raw = self.settings.value(SETTINGS_KEY, "")
            if raw:
                self.preferences.update(validated_patch(json.loads(raw)))
        except (ValueError, TypeError):
            pass  # A corrupt/older preference never prevents offline startup.
        # Connecting an undecorated bound method makes PySide publish a dynamic
        # slot. Keep OS events outside the channel's two-method public surface.
        connection = style_hints.colorSchemeChanged.connect(lambda scheme: self.system_changed(scheme))
        self.destroyed.connect(lambda: QObject.disconnect(connection))

    def state(self):
        return {**self.preferences, "systemTheme": self.system_theme,
                "resolvedTheme": self.system_theme if self.preferences["theme"] == "system" else self.preferences["theme"]}

    @Slot(result=str)
    def getState(self):
        return json.dumps(self.state(), separators=(",", ":"))

    @Slot(str, result=str)
    def update(self, payload):
        try:
            if len(payload) > 2048:
                raise ValueError("Appearance request too large")
            patch = validated_patch(json.loads(payload))
        except (ValueError, TypeError):
            return json.dumps({"ok": False, "error": "INVALID_APPEARANCE", "state": self.state()})
        previous = self.preferences.copy()
        self.preferences.update(patch)
        if previous != self.preferences:
            self.settings.setValue(SETTINGS_KEY, json.dumps(self.preferences, separators=(",", ":")))
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                self.preferences = previous
                return json.dumps({"ok": False, "error": "SAVE_FAILED", "state": self.state()})
            self.changed.emit(self.getState())
        return json.dumps({"ok": True, "state": self.state()})

    def system_changed(self, scheme):
        # Do not override QStyleHints: it must keep observing the actual OS.
        theme = "dark" if scheme == Qt.ColorScheme.Dark else "light"
        if theme != self.system_theme:
            self.system_theme = theme
            self.changed.emit(self.getState())

    def script(self):
        script = QWebEngineScript()
        script.setName("yingxu-appearance-bootstrap")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode(bootstrap_source(self.state()))
        return script


def native_palette(theme):
    dark = theme == "dark"
    palette = QPalette()
    colors = {QPalette.ColorRole.Window: BACKGROUNDS[theme], QPalette.ColorRole.Base: "#1b2029" if dark else "#ffffff",
              QPalette.ColorRole.WindowText: "#e5eaf2" if dark else "#202837",
              QPalette.ColorRole.Text: "#e5eaf2" if dark else "#202837",
              QPalette.ColorRole.Button: "#252c38" if dark else "#ffffff",
              QPalette.ColorRole.ButtonText: "#e5eaf2" if dark else "#202837",
              QPalette.ColorRole.Highlight: "#75a0ff" if dark else "#356de6"}
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    return palette


def set_titlebar_theme(handle, theme):
    """Windows 11 DWM colors, scoped to this HWND; no OS preference changes."""
    import sys
    if sys.platform != "win32":
        return {"supported": False}
    import ctypes
    from ctypes import wintypes
    dwm = ctypes.WinDLL("dwmapi")
    fn = dwm.DwmSetWindowAttribute
    fn.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    fn.restype = ctypes.c_long
    dark = ctypes.c_int(theme == "dark")
    mode = fn(handle, 20, ctypes.byref(dark), ctypes.sizeof(dark))
    if mode:
        mode = fn(handle, 19, ctypes.byref(dark), ctypes.sizeof(dark))
    color = "#191d25" if theme == "dark" else "#ffffff"
    red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    caption = wintypes.DWORD(red | green << 8 | blue << 16)
    title = fn(handle, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    return {"supported": mode == 0, "captionSupported": title == 0, "theme": theme}
