"""SDR Widgets WebEngine compatibility host for the current local workspace."""
import logging
import json
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QUrl, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget, QFileDialog
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView

from .workspace_bridge import WorkspaceBridge
from .native_actions import WorkspaceNativeActions
from .protocol import ProtocolError
from ..operations import StalePlan
from ..version import VERSION
from .appearance import AppearanceBridge, BACKGROUNDS, native_palette, set_titlebar_theme
from .typography import ui_font
from .resources import APP_URL, WORKSPACE_ASSETS, LocalOnlyRequests, LocalResources, register_scheme, resource_key


class WorkspaceView(QWebEngineView):
    folder_dropped = Signal(str)
    drag_active = Signal(bool)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.setDropAction(Qt.DropAction.CopyAction);event.accept();self.drag_active.emit(True)
        else:event.ignore()

    def dragMoveEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():event.setDropAction(Qt.DropAction.CopyAction);event.accept()
        else:event.ignore()

    def dragLeaveEvent(self, event):
        self.drag_active.emit(False);event.accept()

    def dropEvent(self, event):
        self.drag_active.emit(False);urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.setDropAction(Qt.DropAction.CopyAction);event.accept();self.folder_dropped.emit(urls[0].toLocalFile())
        else:event.ignore()


class LocalPage(QWebEnginePage):
    def __init__(self, profile, parent=None, document_key="/workspace.html"):
        super().__init__(profile, parent)
        self.console_errors = []
        self.document_key = document_key

    def acceptNavigationRequest(self, url, kind, is_main_frame):
        # The bridge must never be available to a different document or an iframe.
        return is_main_frame and resource_key(url) == self.document_key

    def createWindow(self, kind):
        return None

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.console_errors.append(message)
            logging.getLogger(__name__).warning("Local page error at line %s: %s", line, message)


class WebWindow(QMainWindow, WorkspaceNativeActions):
    def __init__(self, *, appearance_settings=None, history=None):
        super().__init__()
        self.file_dialog_parent = self
        self.subtitle_parent = self
        self.workspace_mode = True
        self.subtitle_browser = None
        self._subtitle_import = None
        self._native_theme = None
        self.setFont(ui_font())
        self.setWindowTitle('映序 · 字幕整理器')
        self.resize(1280, 860)
        available = self.screen().availableGeometry()
        max_width, max_height = (max(640, available.width() - 32), max(420, available.height() - 64))
        self.setMinimumSize(min(900, max_width), min(620, max_height))
        self.resize(min(self.width(), max_width), min(self.height(), max_height))
        self._loaded = False
        self._closing = False
        self.profile = QWebEngineProfile(self)
        allowed = WORKSPACE_ASSETS
        self.resources = LocalResources(self.profile, allowed=allowed)
        self.requests = LocalOnlyRequests(self.profile, allowed=allowed)
        self.profile.installUrlSchemeHandler(b'yingxu', self.resources)
        self.profile.setUrlRequestInterceptor(self.requests)
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.view = WorkspaceView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        document_key = '/workspace.html'
        self.page = LocalPage(self.profile, self.view, document_key)
        settings = self.page.settings()
        for attribute in (QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, QWebEngineSettings.WebAttribute.PluginsEnabled, QWebEngineSettings.WebAttribute.PdfViewerEnabled, QWebEngineSettings.WebAttribute.FullScreenSupportEnabled):
            settings.setAttribute(attribute, False)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        self.view.setPage(self.page)
        self.bridge = WorkspaceBridge(self, history=history)
        self.channel = QWebChannel(self.page)
        self.appearance = None
        self.titlebar_status = {'supported': False}
        self.appearance = AppearanceBridge(QApplication.styleHints(), self, appearance_settings)
        self.channel.registerObject('appearance', self.appearance)
        self.page.setWebChannel(self.channel)
        self.appearance.changed.connect(self.apply_appearance)
        self.channel.registerObject('bridge', self.bridge)
        self.page.setWebChannel(self.channel)
        self.view.loadStarted.connect(lambda: self.bridge.reset_page())
        self.view.loadFinished.connect(self.on_loaded)
        self.bridge.service.idle.connect(self.finish_subtitle_import)
        script = QWebEngineScript()
        script.setName('yingxu-workspace-mode')
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode("Object.defineProperty(globalThis,'__yingxuWorkspaceMode',{value:'local'});\n              (()=>{const apply=()=>{if(!document.documentElement)return false;document.documentElement.dataset.desktopBoot='pending';return true;};\n              if(!apply()){const observer=new MutationObserver(()=>{if(apply())observer.disconnect();});observer.observe(document,{childList:true,subtree:true});}})();")
        self.page.scripts().insert(script)
        self.bridge.service.native_requested.connect(lambda action, params, rid, sid: QTimer.singleShot(0, lambda: self.handle_native(action, params, rid, sid)))
        self.view.setAcceptDrops(True)
        self.view.folder_dropped.connect(lambda path: self.accept_drop(path))
        self.view.drag_active.connect(lambda active: self.page.runJavaScript("document.documentElement.dataset.dragFolder='" + ('true' if active else 'false') + "';"))
        self.page.renderProcessTerminated.connect(lambda *_args: self.bridge.reset_page())
        self.bridge.service.idle.connect(self.finish_close)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.view)
        self.fallback = QLabel('本地页面未能加载。请检查前端资源后重新打开应用。', self)
        self.fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fallback.setWordWrap(True)
        self.stack.addWidget(self.fallback)
        self.setCentralWidget(self.stack)
        self.stack.installEventFilter(self)
        self.loading_cover = QLabel('映序\n正在准备工作台…', self.stack)
        self.loading_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_cover.setFont(ui_font(14))
        self.loading_cover.setAutoFillBackground(True)
        self.loading_cover.setGeometry(self.stack.rect())
        self.loading_cover.setVisible(True)
        self.loading_cover.raise_()
        self.ready_timer = QTimer(self)
        self.ready_timer.setInterval(60)
        self.ready_timer.timeout.connect(self.check_first_frame)
        self._ready_checks = 0
        self.bridge.service.idle.connect(self.schedule_subtitle_imports)
        self.reload_shortcut = QShortcut(QKeySequence('Ctrl+R'), self)
        self.reload_shortcut.activated.connect(self.reload_page)
        if self.appearance:
            self.apply_appearance(self.appearance.getState())
        self.view.setUrl(QUrl('yingxu://app' + document_key))

    def apply_appearance(self, payload):
        state = json.loads(payload)
        theme = state["resolvedTheme"]
        changed = theme != self._native_theme
        if changed:
            self.setPalette(native_palette(theme))
            self.page.setBackgroundColor(QColor(BACKGROUNDS[theme]))
            self._native_theme = theme
            if self.isVisible(): self.titlebar_status = set_titlebar_theme(int(self.winId()), theme)
        for old in self.page.scripts().find("yingxu-appearance-bootstrap"):
            self.page.scripts().remove(old)
        self.page.scripts().insert(self.appearance.script())
        if self.subtitle_browser is not None:
            self.subtitle_browser.set_theme(theme, state.get('lighting', 'enhanced'))

    def showEvent(self, event):
        super().showEvent(event)
        if self.appearance:
            self.titlebar_status = set_titlebar_theme(int(self.winId()), self.appearance.state()["resolvedTheme"])

    def reload_page(self):
        self._loaded = False
        self.stack.setCurrentWidget(self.view)
        if self.workspace_mode:
            self.loading_cover.show();self.loading_cover.raise_()
        self.view.reload()

    def on_loaded(self, success):
        if success:
            self.stack.setCurrentWidget(self.view)
            if self.workspace_mode:
                self._ready_checks = 0;self.ready_timer.start()
            else: self._loaded = True
        elif not self._loaded:
            self.loading_cover.hide()
            self.stack.setCurrentWidget(self.fallback)

    def check_first_frame(self):
        if self._closing: self.ready_timer.stop();return
        self._ready_checks += 1
        def received(ready):
            if ready:
                self.ready_timer.stop();self._loaded = True;self.loading_cover.hide()
            elif self._ready_checks > 160:
                self.ready_timer.stop();self.loading_cover.hide()
                self.fallback.setText('工作台未能准备完成，请按 Ctrl+R 重试。')
                self.stack.setCurrentWidget(self.fallback)
        self.page.runJavaScript("document.documentElement?.dataset.desktopBoot==='ready'",received)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'loading_cover'): self.loading_cover.setGeometry(self.stack.rect())

    def eventFilter(self,watched,event):
        if watched is getattr(self,'stack',None) and event.type()==QEvent.Type.Resize and hasattr(self,'loading_cover'):
            self.loading_cover.setGeometry(self.stack.rect())
        return super().eventFilter(watched,event)

    def closeEvent(self, event):
        if self.bridge.service.worker:
            self._closing = True
            self.bridge.closing = True
            if self.workspace_mode and self.bridge.service.job["kind"] in {"scan","apply"}:
                self.bridge.service.stop_job({"jobId":self.bridge.service.job["jobId"]})
            self.setWindowTitle("映序 · 正在安全结束当前任务…")
            self.view.setEnabled(False)
            event.ignore()
            return
        self.bridge.closing = True
        if self.subtitle_browser is not None:
            self.subtitle_browser.import_busy = False
            self.subtitle_browser.close()
            self.subtitle_browser = None
        self.page.setWebChannel(None)
        self.view.stop()
        self.page.deleteLater()
        self.profile.deleteLater()
        super().closeEvent(event)


def main():
    register_scheme()
    app = QApplication(sys.argv)
    app.setApplicationName('映序')
    app.setApplicationVersion(VERSION)
    app.setStyle('Fusion')
    window = WebWindow()
    icon = Path(__file__).resolve().parents[2] / 'assets' / 'subtitle_organizer.ico'
    if getattr(sys, 'frozen', False):
        icon = Path(sys._MEIPASS) / 'subtitle_organizer.ico'
    if icon.is_file():
        window.setWindowIcon(QIcon(str(icon)))
    window.show()
    window.activateWindow()
    return app.exec()
