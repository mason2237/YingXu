"""Serve an explicit asset list, never arbitrary local paths or remote content."""
from pathlib import Path
import sys
from urllib.parse import unquote

from PySide6.QtCore import QByteArray, QBuffer, QFile, QIODevice, QUrl
from PySide6.QtWebEngineCore import (
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestJob,
    QWebEngineUrlScheme, QWebEngineUrlSchemeHandler,
)

APP_URL = "yingxu://app/workspace.html"
ASSETS = {
    '/assets/fonts/NotoSansSC.ttf': 'font/ttf',
    '/assets/icons/check.svg': 'image/svg+xml',
    '/assets/icons/chevron.svg': 'image/svg+xml',
    '/css/desktop-polish.css': 'text/css',
    '/css/lighting.css': 'text/css',
    '/js/bridge-client.js': 'text/javascript',
    '/js/channel.js': 'text/javascript',
    '/js/components/prototype-mode.js': 'text/javascript',
    '/js/local-adapter.js': 'text/javascript',
    '/js/components/local-workspace.js': 'text/javascript',
    '/js/components/local-dialogs.js': 'text/javascript',
    '/js/components/glass-controls.js': 'text/javascript',
    '/css/glass-controls.css': 'text/css',
    '/css/local-workspace.css': 'text/css',
    '/qt/qwebchannel.js': 'text/javascript',
    '/workspace.html': 'text/html',
    '/css/tokens.css': 'text/css',
    '/css/components.css': 'text/css',
    '/css/workspace.css': 'text/css',
    '/js/workspace.js': 'text/javascript',
    '/js/store.js': 'text/javascript',
    '/js/model.js': 'text/javascript',
    '/js/components/icons.js': 'text/javascript',
    '/js/components/file-list.js': 'text/javascript',
    '/js/components/inspector.js': 'text/javascript',
    '/js/components/dialogs.js': 'text/javascript',
    '/vendor/design-systems/focus.js': 'text/javascript',
    '/vendor/design-systems/modal.js': 'text/javascript',
    '/css/lens-adapter.css': 'text/css',
    '/css/appearance.css': 'text/css',
    '/css/materials.css': 'text/css',
    '/css/feedback.css': 'text/css',
    '/js/components/workspace-feedback.js': 'text/javascript',
    '/vendor/design-systems/workspace-overlays.js': 'text/javascript',
    '/js/components/list-mist.js': 'text/javascript',
    '/js/components/liquid-actions.js': 'text/javascript',
    '/js/appearance.js': 'text/javascript',
    '/vendor/design-systems/theme-transition.js': 'text/javascript',
    '/js/components/lens-runtime.js': 'text/javascript',
    '/js/components/upstream-effects.js': 'text/javascript',
    '/js/components/particle-feedback.js': 'text/javascript',
    '/vendor/design-systems/lens/card-list.js': 'text/javascript',
    '/vendor/design-systems/lens/component-catalog.js': 'text/javascript',
    '/vendor/design-systems/lens/component-patterns.js': 'text/javascript',
    '/vendor/design-systems/lens/components.css': 'text/css',
    '/vendor/design-systems/lens/components.js': 'text/javascript',
    '/vendor/design-systems/lens/focus.js': 'text/javascript',
    '/vendor/design-systems/lens/index.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/context-budget.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/jelly-physics.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/jelly.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/lens-surface.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/optical-motion.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/optics.js': 'text/javascript',
    '/vendor/design-systems/lens/internal/renderer.js': 'text/javascript',
    '/vendor/design-systems/lens/optical-components.js': 'text/javascript',
    '/vendor/design-systems/lens/runtime.js': 'text/javascript',
    '/vendor/design-systems/lens/sound.js': 'text/javascript',
    '/vendor/design-systems/lens/tokens.css': 'text/css',
    '/vendor/design-systems/lens/tokens.js': 'text/javascript',
}

WORKSPACE_ASSETS = frozenset(ASSETS)


def register_scheme():
    if QWebEngineUrlScheme.schemeByName(b"yingxu").name():
        return
    scheme = QWebEngineUrlScheme(b"yingxu")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme
                    | QWebEngineUrlScheme.Flag.CorsEnabled
                    | QWebEngineUrlScheme.Flag.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)


def frontend_root():
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "frontend"


def resource_key(url):
    if (url.scheme() != "yingxu" or url.host() != "app" or url.port() != -1
            or url.userName() or url.password() or url.hasQuery()):
        return None
    key = unquote(url.path(QUrl.ComponentFormattingOption.FullyEncoded))
    if "\\" in key or "%" in key or any(part in {".", ".."} for part in key.split("/")):
        return None
    return key if key in ASSETS else None


class LocalResources(QWebEngineUrlSchemeHandler):
    def __init__(self, parent=None, *, allowed=None):
        super().__init__(parent)
        self.root = frontend_root().resolve()
        self.allowed = frozenset(ASSETS if allowed is None else allowed)

    def requestStarted(self, job):
        key = resource_key(job.requestUrl())
        if key is None or key not in self.allowed or bytes(job.requestMethod()) != b"GET":
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        if key == "/qt/qwebchannel.js":
            source = QFile(":/qtwebchannel/qwebchannel.js")
            if not source.open(QIODevice.OpenModeFlag.ReadOnly):
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            data = bytes(source.readAll())
        else:
            path = (self.root / key.lstrip("/")).resolve()
            if not path.is_relative_to(self.root):
                job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
                return
            try:
                data = path.read_bytes()
            except OSError:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
        buffer = QBuffer(job)
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(QByteArray(ASSETS[key].encode("ascii")), buffer)


class LocalOnlyRequests(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None, *, allowed=None):
        super().__init__(parent)
        self.allowed = frozenset(ASSETS if allowed is None else allowed)

    def interceptRequest(self, info):
        if resource_key(info.requestUrl()) not in self.allowed:
            info.block(True)
