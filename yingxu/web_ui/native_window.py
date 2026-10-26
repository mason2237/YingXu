"""Independent D3D11/Qt Quick host with a verified scRGB swapchain.

The local HTML and WorkspaceBridge/file services are shared with the retained
Widgets host. NativeHost is QML-only: it is never registered on WebChannel.
"""
import json
import logging
import os
from pathlib import Path
import re
import sys

from PySide6.QtCore import QByteArray, QEvent, QObject, Property, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QIcon
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWebEngineQuick import QQuickWebEngineProfile, QtWebEngineQuick
from PySide6.QtWidgets import QApplication, QWidget

from .appearance import AppearanceBridge, BACKGROUNDS, bootstrap_source, set_titlebar_theme
from .display_status import display_color_status, display_for_screen, screen_device_for_window
from .native_actions import WorkspaceNativeActions
from .resources import LocalOnlyRequests, LocalResources, WORKSPACE_ASSETS, frontend_root, register_scheme, resource_key
from .typography import ui_font
from .workspace_bridge import WorkspaceBridge
from ..version import VERSION


def compositor_chromium_flags(value):
    """Disable Chromium's HWND occlusion heuristic for our embedded texture.

    Preserve existing switches verbatim. Merge only the last recognised
    disable-features switch; never replace an unfamiliar user-supplied form.
    """
    feature = 'CalculateNativeWinOcclusion'
    pattern = r'(?<!\S)(?P<outer>"?)--disable-features=(?P<inner>"?)(?P<features>[^"\s]*)(?P=inner)(?P=outer)(?=\s|$)'
    matches = list(re.finditer(pattern, value))
    if matches:
        match = matches[-1]
        features = match.group('features')
        if feature in features.split(','): return value
        start,end = match.span('features')
        return value[:start] + features + (',' if features else '') + feature + value[end:]
    if '--disable-features' in value: return value
    return (value + ' --disable-features=' + feature).strip()


def configure_graphics():
    QQuickStyle.setStyle('Basic')
    if sys.platform == 'win32':
        os.environ.setdefault('QSG_RHI_BACKEND', 'd3d11')
        os.environ.setdefault('QSG_RENDER_LOOP', 'basic')
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = compositor_chromium_flags(os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS',''))
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Direct3D11)
    QtWebEngineQuick.initialize()


class QuickPage(QObject):
    def __init__(self, host):
        super().__init__(host);self.host = host;self.callbacks = {};self.serial = 0;self.console_errors = []

    def runJavaScript(self, code, callback=None):
        self.serial += 1;token = str(self.serial)
        if callback: self.callbacks[token] = callback
        self.host.evaluate.emit(code, token)

    def reload(self): self.host.reloadPage()
    def stop(self): self.host.stopWeb.emit()
    def setEnabled(self, enabled): self.host.enableWeb.emit(enabled)


class CompositorHints(QObject):
    """Local-page redraw hints only; no files, commands, URLs or preferences."""
    changed = Signal(bool)

    def __init__(self, parent):
        super().__init__(parent);self._overlay = False

    @Property(bool, notify=changed)
    def overlayActive(self): return self._overlay

    @Slot(bool)
    def setOverlayActive(self, active):
        if active != self._overlay:
            self._overlay = active;self.changed.emit(active)


class NativeWindow(QQuickView, WorkspaceNativeActions):
    evaluate = Signal(str, str)
    reloadWeb = Signal()
    stopWeb = Signal()
    enableWeb = Signal(bool)
    sceneChanged = Signal()
    bootChanged = Signal()

    def __init__(self, *, appearance_settings=None, history=None):
        super().__init__()
        self.setPersistentGraphics(True)
        self.setPersistentSceneGraph(True)
        self.workspace_mode = True;self._closing = False;self._loaded = False
        self._page_generation = 0
        self._ready_pending = False
        self._subtitle_import = None;self.subtitle_browser = None
        self._native_theme = None;self._hdr = False;self._native_hdr_active = False;self._white_scale = 1.
        self._output_initialized = False;self._loading_text = '映序\n正在准备工作台…'
        self.appearance = AppearanceBridge(QApplication.styleHints(), self, appearance_settings)
        self.compositor = CompositorHints(self)
        self.page = self.view = QuickPage(self)
        self.bridge = WorkspaceBridge(self, history=history)
        self.file_dialog_parent = None
        self.subtitle_parent = QWidget()
        self.subtitle_parent.appearance = self.appearance;self.subtitle_parent.page = self.page
        self.profile = QQuickWebEngineProfile(self)
        self.profile.setHttpCacheType(QQuickWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QQuickWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.resources = LocalResources(self.profile, allowed=WORKSPACE_ASSETS)
        self.requests = LocalOnlyRequests(self.profile, allowed=WORKSPACE_ASSETS)
        self.profile.installUrlSchemeHandler(b'yingxu', self.resources)
        self.profile.setUrlRequestInterceptor(self.requests)
        self.profile.downloadRequested.connect(lambda request: request.cancel())
        self.appearance.changed.connect(self.apply_appearance)
        service = self.bridge.service
        service.native_requested.connect(lambda action, params, rid, sid:
            QTimer.singleShot(0, lambda: self.handle_native(action, params, rid, sid)))
        service.idle.connect(self.finish_subtitle_import)
        service.idle.connect(self.schedule_subtitle_imports)
        service.idle.connect(self.finish_close)
        self.setTitle('映序 · 字幕整理器')
        self.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        available = self.screen().availableGeometry()
        self.resize(min(1280, max(640, available.width()-32)), min(860, max(420, available.height()-64)))
        self.setMinimumSize(self.size().boundedTo(QSize(900, 620)))
        # Qt checks format support against the real window/display and safely
        # keeps SDR when scRGB is unavailable. Never use this request as proof.
        if self.appearance.preferences.get('nativeHdr', True):
            self.setProperty('_qt_sg_hdr_format', QByteArray(b'scrgb'))
        self.engine().rootContext().setContextProperty('nativeHost', self)
        self.engine().rootContext().setContextProperty('nativeProfile', self.profile)
        self.engine().rootContext().setContextProperty('compositorHints', self.compositor)
        qml = frontend_root()/'native/desktop.qml'
        component = QQmlComponent(self.engine(), QUrl.fromLocalFile(str(qml)))
        root = component.create()
        if root is None:
            raise RuntimeError('\n'.join(error.toString() for error in component.errors()))
        self.component = component
        self.setContent(QUrl.fromLocalFile(str(qml)), component, root)
        self.channel = root.findChild(QObject, 'localChannel')
        self.channel.registerObject('bridge', self.bridge)
        self.channel.registerObject('appearance', self.appearance)
        self.channel.registerObject('compositor', self.compositor)
        self.ready_timer = QTimer(self);self.ready_timer.setInterval(80)
        self.ready_timer.timeout.connect(self.check_ready);self.ready_checks = 0
        self.output_timer = QTimer(self);self.output_timer.setInterval(2000)
        self.output_timer.timeout.connect(self.refresh_output)
        self.frameSwapped.connect(self.first_frame)
        self.screenChanged.connect(lambda _screen: QTimer.singleShot(0, self.refresh_output))
        self.apply_appearance(self.appearance.getState())
        root.setProperty('documentUrl', QUrl('yingxu://app/workspace.html'))

    @Property(str, notify=bootChanged)
    def bootScript(self):
        return bootstrap_source(self.appearance.state()) + """;
        Object.defineProperty(globalThis,'__yingxuWorkspaceMode',{value:'local'});
        (()=>{const apply=()=>{if(!document.documentElement)return false;
          document.documentElement.dataset.desktopBoot='pending';
          document.documentElement.dataset.nativeCompositor='d3d11';return true;};
          if(!apply()){const o=new MutationObserver(()=>{if(apply())o.disconnect()});o.observe(document,{childList:true,subtree:true})}})();"""

    @Property(QColor, notify=sceneChanged)
    def pageBackground(self): return QColor(BACKGROUNDS[self.appearance.state()['resolvedTheme']])
    @Property(QColor, notify=sceneChanged)
    def coverColor(self):
        color = self.pageBackground
        if not self._hdr: return color
        def linear(value): return value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4
        return QColor.fromRgbF(*(linear(value)*self._white_scale for value in (color.redF(),color.greenF(),color.blueF())))
    @Property(float, notify=sceneChanged)
    def whiteScale(self): return self._white_scale
    @Property(bool, notify=sceneChanged)
    def hdrActive(self): return self._hdr
    @Property(float, notify=sceneChanged)
    def highlightBoost(self):
        requested = {'off':0.,'soft':.35,'enhanced':1.2}.get(self.appearance.preferences['lighting'],0.)
        return min(requested, max(0., 8./self._white_scale-1.)) if self._native_hdr_active else 0.
    @Property(float, notify=sceneChanged)
    def pixelRatio(self): return self.devicePixelRatio()
    @Property(bool, notify=sceneChanged)
    def loaded(self): return self._loaded
    @Property(str, notify=sceneChanged)
    def loadingText(self): return self._loading_text

    def first_frame(self):
        if not self._output_initialized:
            self._output_initialized = True;QTimer.singleShot(0, self.refresh_output)
            self.output_timer.start()

    def refresh_output(self):
        if self._closing or not self.isExposed(): return
        swapchain, rhi = self.swapChain(), self.rhi()
        if not swapchain or not rhi: return
        fmt = swapchain.format()
        self._hdr = fmt == fmt.HDRExtendedSrgbLinear
        status = display_color_status()
        display = display_for_screen(status, screen_device_for_window(int(self.winId())) or self.screen().name())
        active = self._hdr and display.get('hdrEnabled') is True
        self._native_hdr_active = active
        white = (display.get('sdrWhiteNits') or 200.) if active else 80.
        self._white_scale = max(.5, min(white/80., 8.))
        output = {'host':'qt-quick', 'backend':str(rhi.backend()).split('.')[-1],
                  'swapchain':str(fmt).split('.')[-1], 'nativeHdrActive':active,
                  'screenName':self.screen().name(),
                  'systemHdrEnabled':display.get('hdrEnabled'), 'bitsPerChannel':display.get('bitsPerChannel'),
                  'sdrWhiteNits':white, 'osSettingsChanged':False}
        if getattr(self.appearance, 'output_status', None) != output:
            self.appearance.output_status = output
            self.sceneChanged.emit();self.appearance.changed.emit(self.appearance.getState())

    def apply_appearance(self, payload):
        state = json.loads(payload);theme = state['resolvedTheme']
        self.setColor(self.coverColor)
        if theme != self._native_theme:
            self._native_theme = theme
            if self.isVisible(): set_titlebar_theme(int(self.winId()), theme)
        self.bootChanged.emit();self.sceneChanged.emit()
        if self.subtitle_browser is not None: self.subtitle_browser.set_theme(theme,state['lighting'])

    def exposeEvent(self, event):
        super().exposeEvent(event)
        if self.isExposed() and not getattr(self,'_titlebar_applied',False):
            self._titlebar_applied = True
            set_titlebar_theme(int(self.winId()), self.appearance.state()['resolvedTheme'])

    @Slot(QUrl, result=bool)
    def allowNavigation(self, url):
        return url.toString() == 'about:blank' or resource_key(url) == '/workspace.html'

    @Slot(int)
    def loadingEvent(self, status):
        if status == 0:
            self.reset_page_rendering()
        elif status == 2:
            self.ready_checks = 0;self.ready_timer.start()
        elif status == 3:
            self.ready_timer.stop()
            self._loading_text = '工作台加载失败，请按 Ctrl+R 重试。';self.sceneChanged.emit()

    def reset_page_rendering(self):
        self._page_generation += 1
        self._ready_pending = False
        self.ready_timer.stop()
        self.page.callbacks.clear()
        self.bridge.reset_page()
        self.compositor.setOverlayActive(False)
        self._loaded = False
        self.sceneChanged.emit()

    def check_ready(self):
        self.ready_checks += 1
        if self.ready_checks > 180:
            self.ready_timer.stop()
            self._loading_text = '工作台未能准备完成，请按 Ctrl+R 重试。'
            self.sceneChanged.emit()
            return
        if self._ready_pending:
            return
        self._ready_pending = True
        generation = self._page_generation
        def result(ready):
            if generation != self._page_generation:
                return
            self._ready_pending = False
            if not self.ready_timer.isActive() or self._closing:
                return
            if ready and self._output_initialized:
                self.ready_timer.stop();self._loaded = True;self.sceneChanged.emit()
        self.page.runJavaScript("document.documentElement.dataset.desktopBoot==='ready'", result)

    @Slot(str, str)
    def javascriptResult(self, token, raw):
        callback = self.page.callbacks.pop(token, None)
        if callback:
            try: value = json.loads(raw)
            except ValueError: value = None
            callback(value)

    @Slot(int, str, int)
    def consoleMessage(self, level, message, line):
        if level == 2:
            self.page.console_errors.append(message)
            logging.getLogger(__name__).warning('Local page error at line %s: %s',line,message)

    @Slot(int)
    def renderTerminated(self, code):
        self.reset_page_rendering()
        self._loading_text = '网页渲染已停止，请按 Ctrl+R 恢复；未确认的文件不会修改。';self.sceneChanged.emit()

    @Slot()
    def reloadPage(self):
        self.reset_page_rendering();self._loading_text = '映序\n正在恢复工作台…'
        self.sceneChanged.emit();self.reloadWeb.emit()

    reload_page = reloadPage

    @Slot(QUrl)
    def dropFolder(self, url):
        if url.isLocalFile(): self.accept_drop(url.toLocalFile())

    def isMinimized(self): return bool(self.windowState() & Qt.WindowState.WindowMinimized)
    def activateWindow(self): self.requestActivate()
    def setWindowTitle(self, text): self.setTitle(text)

    def event(self, event):
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, 'appearance'):
            self.sceneChanged.emit()
        if event.type() == QEvent.Type.Close and hasattr(self, 'bridge'):
            service = self.bridge.service
            if service.worker:
                self._closing = True;self.bridge.closing = True
                if service.job['kind'] in {'scan','apply'}: service.stop_job({'jobId':service.job['jobId']})
                self.setTitle('映序 · 正在安全结束当前任务…');self.enableWeb.emit(False)
                event.ignore();return True
            self._closing = True;self.bridge.closing = True
            self.ready_timer.stop();self.output_timer.stop()
            if self.subtitle_browser is not None:
                self.subtitle_browser.import_busy = False;self.subtitle_browser.close();self.subtitle_browser = None
            self.stopWeb.emit();self.subtitle_parent.deleteLater()
        return super().event(event)


def main():
    configure_graphics();register_scheme()
    app = QApplication(sys.argv);app.setApplicationName('映序');app.setApplicationVersion(VERSION);app.setStyle('Fusion')
    ui_font()
    window = NativeWindow()
    icon = Path(sys._MEIPASS)/'subtitle_organizer.ico' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]/'assets/subtitle_organizer.ico'
    if icon.is_file(): window.setIcon(QIcon(str(icon)))
    window.show();window.requestActivate();return app.exec()
