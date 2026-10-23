"""Offline desktop shell for the local workspace and retained preview entries."""
import logging
import json
from pathlib import Path
import sys

from PySide6.QtCore import QUrl, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget, QFileDialog
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView

from .workspace_bridge import WorkspaceBridge
from .protocol import ProtocolError
from ..operations import StalePlan
from ..version import VERSION
from .appearance import AppearanceBridge, BACKGROUNDS, native_palette, set_titlebar_theme
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
    def __init__(self, profile, parent=None, document_key="/index.html"):
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


class WebWindow(QMainWindow):
    def __init__(self, *, preview=False, effects=False, workspace=False, appearance_settings=None, history=None):
        super().__init__()
        if sum((preview,effects,workspace)) > 1:
            raise ValueError("Choose one preview page")
        self.workspace_mode = workspace
        self.setWindowTitle("映序 · 字幕整理器" if workspace else "映序 · 原版效果对照" if effects else "映序 · 工作台预览" if preview else "映序 · Web 架构预览")
        self.resize(1280 if preview or effects or workspace else 1120, 900 if effects else 860 if preview or workspace else 760)
        # Qt sizes are logical pixels. A fixed 860px height extends beyond a
        # 200% desktop; retain room for the native title bar and taskbar.
        available = self.screen().availableGeometry()
        max_width, max_height = max(640, available.width() - 32), max(420, available.height() - 64)
        self.setMinimumSize(min(900 if preview or effects or workspace else 820, max_width),
                            min(620 if preview or effects or workspace else 600, max_height))
        self.resize(min(self.width(), max_width), min(self.height(), max_height))
        self._loaded = False
        self._closing = False
        self.profile = QWebEngineProfile(self)  # Unnamed, off-the-record profile.
        allowed = WORKSPACE_ASSETS if workspace else None
        self.resources = LocalResources(self.profile,allowed=allowed)
        self.requests = LocalOnlyRequests(self.profile,allowed=allowed)
        self.profile.installUrlSchemeHandler(b"yingxu", self.resources)
        self.profile.setUrlRequestInterceptor(self.requests)
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)

        self.view = WorkspaceView(self) if workspace else QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        document_key = "/effects.html" if effects else "/workspace.html" if preview or workspace else "/index.html"
        self.page = LocalPage(self.profile, self.view, document_key)
        settings = self.page.settings()
        for attribute in (QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                          QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                          QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
                          QWebEngineSettings.WebAttribute.PluginsEnabled,
                          QWebEngineSettings.WebAttribute.PdfViewerEnabled,
                          QWebEngineSettings.WebAttribute.FullScreenSupportEnabled):
            settings.setAttribute(attribute, False)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        self.view.setPage(self.page)
        if workspace:
            self.bridge = WorkspaceBridge(self,history=history)
        else:
            # Release builds can omit the diagnostic backend completely.
            from .bridge import FoundationBridge
            self.bridge = FoundationBridge(self)
        self.channel = QWebChannel(self.page)
        self.appearance = None
        self.titlebar_status = {"supported": False}
        if preview or effects or workspace:
            self.appearance = AppearanceBridge(QApplication.styleHints(), self, appearance_settings)
            self.channel.registerObject("appearance", self.appearance)
            self.page.setWebChannel(self.channel)
            self.appearance.changed.connect(self.apply_appearance)
        if workspace or (not preview and not effects):
            self.channel.registerObject("bridge", self.bridge)
            self.page.setWebChannel(self.channel)
        self.view.loadStarted.connect(lambda: self.bridge.reset_page())
        self.view.loadFinished.connect(self.on_loaded)
        self.bridge.service.idle.connect(self.finish_close)
        if workspace:
            script = QWebEngineScript();script.setName("yingxu-workspace-mode")
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld);script.setRunsOnSubFrames(False)
            script.setSourceCode("Object.defineProperty(globalThis,'__yingxuWorkspaceMode',{value:'local'});")
            self.page.scripts().insert(script)
            self.bridge.service.native_requested.connect(lambda action,params,rid,sid:
                QTimer.singleShot(0,lambda:self.handle_native(action,params,rid,sid)))
            self.view.setAcceptDrops(True)
            self.view.folder_dropped.connect(lambda path:self.accept_drop(path))
            self.view.drag_active.connect(lambda active:self.page.runJavaScript(
                "document.documentElement.dataset.dragFolder='"+("true" if active else "false")+"';"))
            self.page.renderProcessTerminated.connect(lambda *_args:self.bridge.reset_page())

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.view)
        self.fallback = QLabel("本地页面未能加载。请检查前端资源后重新打开应用。", self)
        self.fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fallback.setWordWrap(True)
        self.stack.addWidget(self.fallback)
        self.setCentralWidget(self.stack)
        self.reload_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.reload_shortcut.activated.connect(self.reload_page)
        if self.appearance:
            self.apply_appearance(self.appearance.getState())
        self.view.setUrl(QUrl("yingxu://app" + document_key))

    def apply_appearance(self, payload):
        theme = json.loads(payload)["resolvedTheme"]
        self.setPalette(native_palette(theme))
        self.page.setBackgroundColor(QColor(BACKGROUNDS[theme]))
        for old in self.page.scripts().find("yingxu-appearance-bootstrap"):
            self.page.scripts().remove(old)
        self.page.scripts().insert(self.appearance.script())
        self.titlebar_status = set_titlebar_theme(int(self.winId()), theme)

    def showEvent(self, event):
        super().showEvent(event)
        if self.appearance:
            self.titlebar_status = set_titlebar_theme(int(self.winId()), self.appearance.state()["resolvedTheme"])

    def reload_page(self):
        self._loaded = False
        self.stack.setCurrentWidget(self.view)
        self.view.reload()

    def on_loaded(self, success):
        if success:
            self._loaded = True
            self.stack.setCurrentWidget(self.view)
        elif not self._loaded:
            self.stack.setCurrentWidget(self.fallback)

    def finish_close(self):
        if self._closing:
            self.close()

    def accept_drop(self, path):
        try:
            self.bridge.service.accept_folder(path,dropped=True)
        except (ProtocolError,OSError,ValueError,StalePlan) as error:
            self.bridge.service.emit("app.error",{"message":error.message if isinstance(error,ProtocolError) else str(error)})

    def handle_native(self, action, params, rid, sid):
        service = self.bridge.service;data = None;error = None
        try:
            if self.bridge.session_id != sid or self.bridge.closing:
                return
            if action == "folder.choose":
                path = QFileDialog.getExistingDirectory(self,"选择包含视频与字幕的文件夹",str(service.folder or Path.home()))
                if self.bridge.session_id != sid or self.bridge.closing:return
                service.native_busy = False
                data = {"cancelled":True} if not path else {"cancelled":False,"summary":service.accept_folder(path)}
            elif action == "result.export":
                path,_ = QFileDialog.getSaveFileName(self,"导出整理记录","映序整理记录.json","JSON 记录 (*.json)",options=QFileDialog.Option.DontConfirmOverwrite)
                if self.bridge.session_id != sid or self.bridge.closing:return
                service.native_busy = False
                data = {"cancelled":True} if not path else service.export_record(params["recordId"],Path(path))
            else:
                path = service.registered_path(params["fileId"])
                if action == "file.copyName":QApplication.clipboard().setText(path.name);data = {"copied":True}
                elif action == "file.reveal":
                    folder = path if path == service.folder else path.parent
                    if not folder.is_dir():raise FileNotFoundError(f"所在文件夹已不存在：{folder}")
                    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                        raise ProtocolError("PATH_UNREADABLE","无法打开文件所在位置。")
                    data = {"opened":True}
        except ProtocolError as caught:error = caught
        except PermissionError as caught:error = ProtocolError("PERMISSION_DENIED",str(caught))
        except (OSError,ValueError,StalePlan) as caught:error = ProtocolError("PATH_UNREADABLE",str(caught))
        except Exception:error = ProtocolError("INTERNAL_ERROR","原生操作未完成，请重试。")
        finally:
            service.native_busy = False
            self.bridge.finish_native(rid,sid,data=data,error=error)
            service.emit("native.idle")

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
        self.page.setWebChannel(None)
        self.view.stop()
        self.page.deleteLater()
        self.profile.deleteLater()
        super().closeEvent(event)


def main(*, preview=False, effects=False, workspace=False):
    register_scheme()  # Must precede QApplication and all WebEngine objects.
    app = QApplication(sys.argv)
    app.setApplicationName("映序" if workspace else "YingXu Web Foundation")
    app.setApplicationVersion(VERSION)
    app.setStyle("Fusion")
    window = WebWindow(preview=preview, effects=effects,workspace=workspace)
    icon = Path(__file__).resolve().parents[2] / "outputs" / "subtitle_organizer.ico"
    if getattr(sys, "frozen", False):
        icon = Path(sys._MEIPASS) / "subtitle_organizer.ico"
    if icon.is_file():
        window.setWindowIcon(QIcon(str(icon)))
    window.show()
    return app.exec()
