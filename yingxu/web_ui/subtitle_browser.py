"""Isolated website-assisted subtitle discovery, without a native web bridge.

Downloads are staged here; native import signals delegate review changes to the
workspace. Remote pages never receive the workspace bridge or filesystem paths.
"""
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QProgressBar, QPushButton, QSplitter,
    QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile,
    QWebEngineSettings, QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from ..core import VIDEO_EXTS, extract_episode
from ..subtitle_sources.downloads import (
    MAX_DOWNLOAD_BYTES, MAX_SESSION_BYTES, MAX_SESSION_FILES,
    inspect_download, reserve_download, safe_filename, write_receipt, same_origin_blob,
)
from ..subtitle_sources.zimuku import (
    HOME_URL, public_https, search_terms, source_url, submit_search_script, verification_script,
)
from ..subtitle_sources.websites import WEBSITES, ZIMUKU_HOSTS, website_for
from ..subtitle_sources.subhd import submit_search_script as submit_subhd_search_script
from ..subtitle_sources.candidates import LANGUAGES, candidates_script, parse_candidates, rank_candidates
from .subtitle_recommendations import RecommendationPanel
from .appearance import native_palette, set_titlebar_theme
from .typography import ui_font
from .desktop_design import AmbientSurface, GuideStep, QueueDelegate, StatusLabel, PALETTES, glyph, icon, stylesheet


@dataclass(frozen=True)
class SearchTask:
    task_id: str
    video: Path
    query: str
    scan_id: str | None = None
    row_id: str | None = None
    revision: int | None = None


class WebsiteRequests(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None, hosts=ZIMUKU_HOSTS):
        super().__init__(parent)
        self.hosts = hosts

    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = public_https(url.toString())
        if url.scheme() in {"data", "blob"}:
            allowed = source_url(info.firstPartyUrl().toString(), self.hosts)
        if not allowed:
            info.block(True)


class SubtitlePage(QWebEnginePage):
    navigation_blocked = Signal(str)

    def __init__(self, profile, parent=None, hosts=ZIMUKU_HOSTS):
        super().__init__(profile, parent)
        self.hosts = hosts

    def acceptNavigationRequest(self, url, kind, is_main_frame):
        text = url.toString()
        allowed = text == "about:blank" or (source_url(text, self.hosts) if is_main_frame else public_https(text))
        if not allowed and is_main_frame:
            self.navigation_blocked.emit("此链接离开了当前字幕来源，已停止跳转。可使用系统浏览器继续。")
        return allowed

    def chooseFiles(self, mode, old_files, accepted_mime_types):
        # Remote pages cannot ask the native application to upload media.
        return []


def label(text="", object_name=""):
    widget = StatusLabel(text) if object_name == 'status' else QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if object_name:
        widget.setObjectName(object_name)
    return widget


class SubtitleBrowser(QMainWindow):
    download_staged = Signal(dict)
    import_requested = Signal(object)
    review_requested = Signal()

    def __init__(self, parent=None, *, download_root=None, website="zimuku", settings=None):
        super().__init__(parent)
        self.website = website_for(website)
        self.preferences = settings if settings is not None else QSettings("YingXu", "SubtitleDiscovery")
        preferred = self.preferences.value("language", "bilingual")
        self.language = preferred if preferred in LANGUAGES else "bilingual"
        self.workspace_context = None
        self.import_busy = False
        self.return_after_import = True
        self._theme = None
        self._lighting = getattr(parent, 'appearance', None).state().get('lighting', 'enhanced') if getattr(parent, 'appearance', None) else 'enhanced'
        self._theme_preference = 'system'
        self.auto_timer = QTimer(self);self.auto_timer.setSingleShot(True);self.auto_timer.setInterval(250)
        self.auto_timer.timeout.connect(self.auto_import_ready)
        self.results = {}
        self.choices = {}
        self.queries = {}
        self.search_pending = False
        self.batch_running = False
        self.batch_rows = []
        self.batch_done = 0
        self.batch_total = 0
        self.setWindowTitle("映序 · 在线字幕")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        available = self.screen().availableGeometry()
        self.resize(min(1280, available.width() - 32), min(860, available.height() - 64))
        self.setMinimumSize(min(880, available.width() - 32), min(660, available.height() - 64))
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.cache_root = Path(download_root) if download_root is not None else base / 'subtitle-inbox'
        self.inbox = self.cache_root / uuid4().hex
        self.tasks = []
        self.downloads = {}
        self.active_task = None
        self.pending_query = None
        self.navigation_generation = 0
        self.closing = False
        self.last_load_error = ""
        self.verification_required = False

        # Never share this profile/page with the privileged local workspace.
        self.profile = QWebEngineProfile(self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.requests = WebsiteRequests(self.profile, self.website.hosts)
        self.profile.setUrlRequestInterceptor(self.requests)
        self.profile.downloadRequested.connect(self.receive_download)
        self.view = QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.page = None
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True)
        self.load_timer.setInterval(30000)
        self.load_timer.timeout.connect(self.load_timed_out)
        self.batch_timer = QTimer(self)
        self.batch_timer.setSingleShot(True)
        self.batch_timer.setInterval(1500)
        self.batch_timer.timeout.connect(self.advance_batch)
        self.build_ui()
        self.set_theme("dark" if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light")
        self.replace_page()
        self.update_controls()

    def build_ui(self):
        root = AmbientSurface(self)
        root.setObjectName("browserRoot")
        outer = QVBoxLayout(root);outer.setContentsMargins(0, 0, 0, 0);outer.setSpacing(0)
        self._icon_buttons = []

        def action(text, symbol, callback, primary=False):
            button = QPushButton(text)
            button.setProperty('iconName', symbol)
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(callback)
            if primary: button.setObjectName('primary')
            self._icon_buttons.append(button)
            return button

        chrome = QWidget();chrome.setObjectName('appChrome')
        chrome_layout = QHBoxLayout(chrome);chrome_layout.setContentsMargins(28, 14, 28, 14);chrome_layout.setSpacing(14)
        self.brand_logo = label('', 'brandLogo');self.brand_logo.setFixedSize(34, 36)
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chrome_layout.addWidget(self.brand_logo)
        chrome_layout.addWidget(label('映序', 'brandName'))
        chrome_layout.addWidget(label('字幕整理', 'brandDescription'))
        chrome_layout.addStretch()
        self.workspace_button = action('工作台', 'back', lambda: self.review_requested.emit())
        chrome_layout.addWidget(self.workspace_button)
        self.theme_picker = QComboBox();self.theme_picker.setMinimumWidth(138)
        for value, name in (('system', '跟随系统'), ('dark', '深色'), ('light', '浅色')):
            self.theme_picker.addItem(name, value)
        self.theme_picker.currentIndexChanged.connect(self.change_theme)
        chrome_layout.addWidget(self.theme_picker)
        self.history_button = action('操作记录', 'history', lambda: self.open_workspace_dialog('history-button'))
        self.appearance_button = action('', 'settings', lambda: self.open_workspace_dialog('appearance-button'))
        self.appearance_button.setAccessibleName('外观与动效');self.appearance_button.setToolTip('外观与动效')
        chrome_layout.addWidget(self.history_button);chrome_layout.addWidget(self.appearance_button)
        has_workspace = hasattr(self.parent(), 'appearance')
        self.workspace_button.setVisible(has_workspace);self.history_button.setVisible(has_workspace);self.appearance_button.setVisible(has_workspace)
        outer.addWidget(chrome)

        body = QWidget();self.body_layout = layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 22, 28, 18);layout.setSpacing(14)
        outer.addWidget(body, 1)
        header = QHBoxLayout();header.setSpacing(12)
        titles = QVBoxLayout();titles.setSpacing(3)
        titles.addWidget(label('在线字幕', 'heading'))
        self.subtitle = label('从网络资源中查找并下载字幕，支持批量处理。', 'subtitle')
        titles.addWidget(self.subtitle);header.addLayout(titles, 1)
        self.source_picker = QComboBox();self.source_picker.setMinimumWidth(168)
        for site in WEBSITES: self.source_picker.addItem(site.label, site.key)
        self.source_picker.setCurrentIndex(self.source_picker.findData(self.website.key))
        self.source_picker.currentIndexChanged.connect(self.change_source)
        header.addWidget(self.source_picker, 0, Qt.AlignmentFlag.AlignVCenter)
        self.add_button = action('添加视频', 'plus', self.choose_videos)
        self.inbox_button = action('下载缓存', 'folder', self.open_inbox)
        self.inbox_button.setToolTip('打开下载缓存，包含所有会话的原始压缩包和解压副本')
        header.addWidget(self.add_button);header.addWidget(self.inbox_button)
        layout.addLayout(header)

        self.guide_strip = QFrame();self.guide_strip.setObjectName('guideStrip')
        guide = QHBoxLayout(self.guide_strip);guide.setContentsMargins(16, 3, 16, 3);guide.setSpacing(12)
        self.guide_steps = []
        for number, (title, description) in enumerate((('确认片名', '输入电影或剧集名称'), ('选择并下载', '从搜索结果中选择字幕'), ('核对匹配', '核对并匹配到视频文件')), 1):
            step = GuideStep(number, title, description);step.setProperty('active', number == 1)
            self.guide_steps.append(step);guide.addWidget(step, 1)
            if number < 3:
                line = QFrame();line.setFrameShape(QFrame.Shape.HLine);line.setObjectName('stepConnector');line.setMaximumWidth(65)
                guide.addWidget(line, 1)
        layout.addWidget(self.guide_strip)
        self.guide_hint = label('', 'guideHint');self.guide_hint.hide()
        query_row = QHBoxLayout();query_row.setSpacing(12)
        self.query = QLineEdit();self.query.setMaxLength(200);self.query.setClearButtonEnabled(True)
        self.query.setPlaceholderText('输入电影或剧名，例如：星际穿越')
        self.search_action = self.query.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.query.textChanged.connect(lambda _text: self.update_guide());self.query.returnPressed.connect(self.start_search)
        query_row.addWidget(self.query, 1)
        self.search_button = action('查找字幕', 'search', self.start_search, True);self.search_button.setMinimumWidth(144)
        query_row.addWidget(self.search_button)
        self.fill_button = action('填入本页', 'copy', self.fill_current_page)
        self.fill_button.setToolTip('完成网页验证后，重新填写当前页面的搜索框')
        query_row.addWidget(self.fill_button);layout.addLayout(query_row)

        preference_row = QHBoxLayout();preference_row.setSpacing(12)
        preference_row.addWidget(label('语言偏好', 'section'))
        self.language_picker = QComboBox()
        for key, name in LANGUAGES.items(): self.language_picker.addItem(name, key)
        self.language_picker.setCurrentIndex(self.language_picker.findData(self.language))
        self.language_picker.currentIndexChanged.connect(self.change_language)
        preference_row.addWidget(self.language_picker)
        self.batch_status = label('勾选队列中的视频，可按顺序批量查找。', 'muted')
        preference_row.addWidget(self.batch_status, 1)
        self.batch_button = action('批量查找', 'search', self.start_batch)
        self.stop_batch_button = action('停止批量', 'stop', self.stop_batch)
        preference_row.addWidget(self.batch_button);preference_row.addWidget(self.stop_batch_button)
        layout.addLayout(preference_row)

        tools_row = QHBoxLayout();tools_row.setSpacing(8)
        self.back_button = action('返回', 'back', self.go_back)
        self.reload_button = action('重新加载', 'refresh', self.reload_page)
        tools_row.addWidget(self.back_button);tools_row.addWidget(self.reload_button)
        self.address = label('尚未联网', 'muted');self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tools_row.addWidget(self.address, 1)
        copy_button = action('复制搜索词', 'copy', lambda: QApplication.clipboard().setText(self.query.text().strip()))
        tools_row.addWidget(copy_button)
        self.external_button = action('浏览器打开', 'external', self.open_external)
        self.external_button.setToolTip('打开当前字幕库页面并复制搜索词；系统浏览器下载不能由本窗口直接接收')
        tools_row.addWidget(self.external_button)
        self.web_tools = QWidget();self.web_tools.setLayout(tools_row);tools_row.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_tools)
        self.status = label('选择一个或多个视频开始，或直接输入片名搜索。', 'status')
        layout.addWidget(self.status)
        self.progress = QProgressBar();self.progress.setRange(0, 100);self.progress.setTextVisible(False);self.progress.setFixedHeight(3);self.progress.hide()
        layout.addWidget(self.progress)

        self.split = split = QSplitter(Qt.Orientation.Horizontal);split.setChildrenCollapsible(False)
        sidebar = QFrame();sidebar.setObjectName('queuePanel')
        side_layout = QVBoxLayout(sidebar);side_layout.setContentsMargins(6, 0, 6, 8);side_layout.setSpacing(0)
        queue_header = QFrame();queue_header.setObjectName('queueHeading')
        queue_header_layout = QHBoxLayout(queue_header);queue_header_layout.setContentsMargins(10, 8, 5, 8)
        self.queue_title = label('视频搜索队列', 'panelTitle');queue_header_layout.addWidget(self.queue_title, 1)
        self.clear_button = action('', 'trash', self.clear_tasks);self.clear_button.setObjectName('quiet')
        self.clear_button.setToolTip('清空本次搜索队列，不删除任何文件');self.clear_button.setAccessibleName('清空搜索队列')
        queue_header_layout.addWidget(self.clear_button);side_layout.addWidget(queue_header)
        self.queue = QListWidget();self.queue.setObjectName('searchQueue');self.queue.setMinimumWidth(215)
        self.queue.setMouseTracking(True);self.queue.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.queue_delegate = QueueDelegate(self.queue);self.queue.setItemDelegate(self.queue_delegate)
        self.queue.currentRowChanged.connect(self.select_task);self.queue.itemChanged.connect(lambda _item: self.update_controls())
        side_layout.addWidget(self.queue, 1)
        self.next_button = action('下一项并查找', 'next', self.next_task);side_layout.addWidget(self.next_button)
        split.addWidget(sidebar)
        self.pages = QTabWidget()
        self.recommendations = RecommendationPanel()
        self.recommendations.open_requested.connect(self.open_candidate);self.recommendations.chosen.connect(self.keep_candidate)
        self.recommendations.search_requested.connect(self.start_search)
        self.pages.addTab(self.recommendations, '推荐结果');self.pages.addTab(self.view, '网站浏览')
        self.pages.currentChanged.connect(self.update_page_tools);self.update_page_tools()
        results_frame = QFrame();results_frame.setObjectName('resultsPanel')
        results_layout = QVBoxLayout(results_frame);results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(self.pages)
        split.addWidget(results_frame);split.setStretchFactor(1, 1);split.setSizes([285, 950])
        layout.addWidget(split, 1)

        download_header = QHBoxLayout();download_header.setSpacing(12)
        self.auto_import = QCheckBox('下载后自动解压并加入审阅')
        self.auto_import.setToolTip('只解压到缓存并登记待确认；整理到视频旁边仍需要你最终确认')
        self.auto_import.setChecked(self.preferences.value('autoImport', True, type=bool))
        self.auto_import.toggled.connect(lambda enabled: self.preferences.setValue('autoImport', enabled))
        self.auto_import.toggled.connect(lambda _enabled: self.schedule_auto_import())
        download_header.addWidget(self.auto_import, 1)
        self.review_button = action('查看待确认匹配', 'document', lambda: self.review_requested.emit())
        download_header.addWidget(self.review_button)
        self.import_button = action('导入所选', 'download', self.request_import, True)
        self.import_button.setToolTip('将勾选下载解压并加入待确认匹配；不会修改视频目录')
        download_header.addWidget(self.import_button)
        self.cancel_button = action('停止下载', 'stop', self.cancel_selected);download_header.addWidget(self.cancel_button)
        layout.addLayout(download_header)
        self.download_list = QListWidget();self.download_list.setObjectName('downloadList');self.download_list.setMaximumHeight(92);self.download_list.setMinimumHeight(52)
        self.download_list.currentRowChanged.connect(lambda _row: self.update_controls());self.download_list.itemChanged.connect(lambda _item: self.update_controls())
        layout.addWidget(self.download_list)
        self.setCentralWidget(root);self.setFont(ui_font())
        self.update_density()

    def change_theme(self):
        preference = self.theme_picker.currentData()
        appearance = getattr(self.parent(), 'appearance', None)
        if appearance:
            appearance.update(json.dumps({'theme': preference}))
        else:
            self._theme_preference = preference
            dark = preference == 'dark' or preference == 'system' and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
            self.set_theme('dark' if dark else 'light')

    def open_workspace_dialog(self, identifier):
        parent = self.parent()
        if not hasattr(parent, 'page'): return
        self.review_requested.emit()
        # Fixed local UI targets only; the untrusted website never gains a bridge.
        if identifier in {'history-button', 'appearance-button'}:
            parent.page.runJavaScript("document.getElementById('" + identifier + "').click()")

    def clear_tasks(self):
        if self.busy_downloads() or self.batch_running or self.import_busy: return
        self.search_pending = False;self.pending_query = None;self.active_task = None
        self.navigation_generation += 1;self.load_timer.stop();self.progress.hide()
        self.replace_page()
        self.tasks.clear();self.results.clear();self.choices.clear();self.queries.clear()
        self.queue.clear();self.query.clear();self.show_recommendations()
        self.pages.setCurrentWidget(self.recommendations)
        self.status.setText('搜索队列已清空，已下载的文件仍保留在缓存。')
        self.update_controls()

    def update_density(self):
        if not hasattr(self, 'body_layout'): return
        compact = self.width() < 1060 or self.height() < 780
        if self.property('compact') == compact: return
        self.setProperty('compact', compact)
        self.body_layout.setContentsMargins(20 if compact else 28, 14 if compact else 22, 20 if compact else 28, 14 if compact else 18)
        self.body_layout.setSpacing(10 if compact else 14)
        self.subtitle.setVisible(not compact)
        if self._theme: self.setStyleSheet(stylesheet(self._theme, self._lighting))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_density()

    def update_page_tools(self, _index=None):
        website_visible = self.pages.currentWidget() is self.view
        self.web_tools.setVisible(website_visible)
        self.fill_button.setVisible(website_visible)

    def set_theme(self, theme, lighting=None):
        appearance = getattr(self.parent(), 'appearance', None)
        lighting = lighting or (appearance.state().get('lighting', 'enhanced') if appearance else self._lighting)
        value = appearance.state()['theme'] if appearance else self._theme_preference
        self.theme_picker.blockSignals(True);self.theme_picker.setCurrentIndex(self.theme_picker.findData(value));self.theme_picker.blockSignals(False)
        if theme == self._theme and lighting == getattr(self.centralWidget(), 'lighting', None): return
        theme_changed = theme != self._theme
        self._theme = theme
        self._lighting = lighting
        if theme_changed: self.setPalette(native_palette(theme))
        self.setStyleSheet(stylesheet(theme, lighting))
        self.centralWidget().theme = theme;self.centralWidget().lighting = lighting;self.centralWidget().update()
        colors = PALETTES[theme]
        self.brand_logo.setPixmap(glyph('brand', '#ffffff', 27))
        self.brand_logo.setStyleSheet('background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4c9bff,stop:1 #1056ec); border: 1px solid #5596ff; border-radius: 9px;')
        for button in self._icon_buttons:
            button.setIcon(icon(button.property('iconName'), '#ffffff' if button.objectName() == 'primary' else colors['secondary']))
        for step in self.guide_steps: step.theme = theme;step.lighting = lighting;step.update()
        self.queue_delegate.theme = theme;self.queue.viewport().update()
        self.recommendations.set_theme(theme, lighting)
        self.search_action.setIcon(icon('search', colors['secondary']))
        if self.isVisible() and theme_changed: set_titlebar_theme(int(self.winId()), theme)

    def showEvent(self,event):
        super().showEvent(event)
        if self._theme: set_titlebar_theme(int(self.winId()),self._theme)

    def update_guide(self):
        if not hasattr(self,'recommendations'): return
        imported = sum(bool(entry.get('imported')) for entry in self.downloads.values())
        if self.import_busy:
            index,message = 2,'正在自动解压并登记，完成后在工作台核对匹配；不会修改视频文件。'
        elif imported:
            index,message = 2,f'已准备 {imported} 份下载，点击“查看待确认匹配”核对文件与版本。'
        elif self.verification_required:
            index,message = 1,'网站要求验证码：请在网页完成，或切换右上方 SubHD 备用来源。'
        elif self.recommendations.rows:
            index,message = 1,'选中候选 → 去网站下载；下载完成后自动解压，再回到工作台核对匹配。'
        elif self.search_pending or self.batch_running:
            index,message = 0,'正在按片名查找；原视频与完整文件名保留在本机。'
        else:
            index,message = 0,'确认上方只有电影或剧名，再点击查找；年份、集数和片源不会塞进搜索词。'
        for i,step in enumerate(self.guide_steps):
            if step.property('active') != (i==index):
                step.setProperty('active',i==index);step.update()
        self.guide_hint.setText(message)
        self.guide_strip.setToolTip(message)
        self.recommendations.search_button.setEnabled(bool(self.query.text().strip()) and not (self.import_busy or self.batch_running))

    def current_task(self):
        row = self.queue.currentRow()
        return self.tasks[row] if 0 <= row < len(self.tasks) else None

    def result_key(self, task):
        return (task.task_id, self.website.key, self.queries.get(task.task_id, task.query))

    def append_task(self, task):
        self.tasks.append(task)
        item = QListWidgetItem(task.video.name)
        episode = extract_episode(task.video.stem)
        episode_label = (f'S{episode[0]:02}E{episode[1]:02}' if episode[0] is not None else f'第{episode[1]}集') if episode else ''
        item.setData(Qt.ItemDataRole.UserRole+1, task.query)
        item.setData(Qt.ItemDataRole.UserRole+2, episode_label)
        item.setToolTip(task.video.name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.queue.addItem(item)

    def add_workspace_tasks(self, values):
        if self.busy_downloads() or self.batch_running:
            raise ValueError("在线窗口正在处理任务，请先停止后再添加视频。")
        # Validate all native inputs first. No JSON/frontend paths reach here.
        known = {(task.scan_id, task.row_id) for task in self.tasks}
        tasks = []
        for value in values:
            if (value["scanId"], value["rowId"]) in known:
                continue
            path = value["video"].resolve(strict=True)
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
                raise ValueError("视频已经变化，请重新扫描。")
            tasks.append(SearchTask(uuid4().hex, path, search_terms(path.name),
                                    value["scanId"], value["rowId"], value["revision"]))
        first = len(self.tasks)
        for task in tasks:
            self.append_task(task)
        if tasks:
            self.queue.setCurrentRow(first)
        self.status.setText(f"已准备 {len(self.tasks)} 个视频。可取消勾选以跳过；点击“批量查找”后才会发送搜索词。")
        self.update_controls()
        return len(tasks)

    def change_language(self, _index):
        self.language = self.language_picker.currentData()
        self.preferences.setValue("language", self.language)
        self.preferences.sync()
        self.show_recommendations()
        if self.preferences.status() != QSettings.Status.NoError:
            self.status.setText("语言偏好已用于本次窗口，但未能保存到本机设置。")

    def show_recommendations(self):
        task = self.current_task()
        key = self.result_key(task) if task else (self.active_task or {}).get("resultKey")
        entry = self.results.get(key)
        choice = self.choices.get(key)
        if entry is None:
            self.recommendations.set_results([], "尚未获取此视频在当前来源的候选。点击查找，或勾选多个视频后批量查找。")
            return
        ranked = rank_candidates(entry["rows"], entry["videoName"], self.language)
        message = (f"本页 {len(ranked)} 条候选 · {LANGUAGES[self.language]} · 仅供推荐，请核对版本"
                   if ranked else "本次搜索没有结果，可调整片名或切换备用来源。")
        self.recommendations.set_results(ranked, message, choice["url"] if choice else None)

    def update_queue_labels(self):
        self.queue.blockSignals(True)
        for i, task in enumerate(self.tasks):
            key = self.result_key(task)
            entry = self.results.get(key)
            state = "已保留推荐" if key in self.choices else (f"{len(entry['rows'])} 条候选" if entry else "待查找")
            self.queue.item(i).setText(f"{task.video.name}\n{state}")
        self.queue.blockSignals(False)

    def start_batch(self):
        if self.batch_running or self.busy_downloads():
            return
        self.batch_rows = [i for i, task in enumerate(self.tasks)
                           if self.queue.item(i).checkState() == Qt.CheckState.Checked
                           and self.result_key(task) not in self.results]
        if not self.batch_rows:
            self.status.setText("勾选的视频均已有本来源结果；如需更新，可选中视频后单独查找。")
            return
        self.batch_total = len(self.batch_rows)
        self.batch_done = 0
        self.batch_running = True
        self.advance_batch()

    def advance_batch(self):
        if not self.batch_running or self.closing:
            return
        if not self.batch_rows:
            self.batch_running = False
            self.batch_status.setText(f"已查找 {self.batch_done} / {self.batch_total}，逐项核对并保留推荐。")
            self.pages.setCurrentWidget(self.recommendations)
            self.update_controls()
            self.schedule_auto_import()
            return
        row = self.batch_rows.pop(0)
        self.queue.setCurrentRow(row)
        self.batch_status.setText(f"正在查找 {self.batch_done + 1} / {self.batch_total} · 随时可停止")
        self.start_search()

    def pause_batch(self, reason):
        self.batch_timer.stop()
        if self.batch_running:
            self.batch_status.setText(f"已暂停 · 完成 {self.batch_done} / {self.batch_total} · {reason}")
        self.batch_running = False
        self.update_controls()
        self.schedule_auto_import()

    def stop_batch(self):
        self.pause_batch("已保留结果，可再次点击批量查找继续")
        self.search_pending = False
        self.pending_query = None
        self.navigation_generation += 1
        self.load_timer.stop()
        self.page.triggerAction(QWebEnginePage.WebAction.Stop)
        self.progress.hide()
        self.status.setText("已停止批量查找，已获取的候选保留。")

    def read_candidates(self, page, generation):
        if not self.search_pending or not self.active_task:
            return
        context, site = dict(self.active_task), self.website
        def received(raw):
            if self.closing or page is not self.page or generation != self.navigation_generation or not self.search_pending:
                return
            status, rows = parse_candidates(raw, site)
            self.search_pending = False
            if status not in {"ready", "empty"}:
                self.pause_batch("当前页面需要人工操作")
                self.status.setText("当前来源尚不能读取候选，或网页结构已变化。可在网站浏览中继续，也可切换 SubHD 备用来源。")
                return
            if not self.batch_running and self.batch_status.text().startswith("已暂停"):
                self.batch_status.setText("当前来源已恢复搜索，可继续批量查找。")
            self.results[context["resultKey"]] = {"rows": rows, "videoName": context["videoName"]}
            self.show_recommendations()
            self.update_queue_labels()
            self.pages.setCurrentWidget(self.recommendations)
            self.status.setText(f"已读取当前结果页 {len(rows)} 条候选；不自动翻页或下载，保留推荐不代表匹配完成。")
            if self.batch_running:
                self.batch_done += 1
                self.batch_timer.start()
            self.update_controls()
        page.runJavaScript(candidates_script(site, context["query"]), received)

    def keep_candidate(self, candidate):
        if self.batch_running or self.busy_downloads():
            return
        if candidate["needsReview"] and not self.recommendations.ack.isChecked():
            return
        task = self.current_task()
        key = self.result_key(task) if task else (self.active_task or {}).get("resultKey")
        if key not in self.results or not any(row["url"] == candidate["url"] for row in self.results[key]["rows"]):
            return
        self.choices[key] = dict(candidate)
        self.show_recommendations()
        self.update_queue_labels()
        self.status.setText("已保留此推荐，可随时选择其他候选。尚未下载或关联字幕。")

    def open_candidate(self, candidate):
        if self.batch_running or self.busy_downloads() or not self.trusted_source(candidate["url"]):
            return
        task = self.current_task()
        key = self.result_key(task) if task else (self.active_task or {}).get("resultKey")
        if key not in self.results or not any(row["url"] == candidate["url"] for row in self.results[key]["rows"]):
            return
        self.prepare_context(task, key[2])
        self.query.setText(key[2])
        self.search_pending = False
        self.pending_query = None
        self.replace_page()
        self.pages.setCurrentWidget(self.view)
        self.page.setUrl(QUrl(candidate["url"]))

    def prepare_context(self, task, query):
        existing = self.active_task or {}
        task_id = task.task_id if task else (existing.get("taskId") if existing.get("rowId") is None
                                             and existing.get("query") == query else None) or uuid4().hex
        self.active_task = {"taskId": task_id, "videoName": task.video.name if task else query,
                            "query": query, "source": self.website.provider, "endpoint": self.website.key,
                            "resultKey": (task_id, self.website.key, query), "scanId": task.scan_id if task else None,
                            "rowId": task.row_id if task else None, "revision": task.revision if task else None}
        if task:
            self.queries[task.task_id] = query

    def replace_page(self):
        self.navigation_generation += 1
        previous = self.page
        if previous is not None:
            previous.triggerAction(QWebEnginePage.WebAction.Stop)
        self.requests.hosts = self.website.hosts
        self.page = SubtitlePage(self.profile, self.view, self.website.hosts)
        settings = self.page.settings()
        for name in ("LocalContentCanAccessRemoteUrls", "LocalContentCanAccessFileUrls",
                     "JavascriptCanAccessClipboard", "JavascriptCanPaste", "PluginsEnabled",
                     "AllowRunningInsecureContent", "FullScreenSupportEnabled", "ScreenCaptureEnabled"):
            settings.setAttribute(getattr(QWebEngineSettings.WebAttribute, name), False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        self.page.permissionRequested.connect(lambda permission: permission.deny())
        self.page.fileSystemAccessRequested.connect(lambda request: request.reject())
        self.page.certificateError.connect(lambda error: error.rejectCertificate())
        self.page.navigation_blocked.connect(self.status.setText)
        self.page.newWindowRequested.connect(self.open_popup)
        self.page.loadStarted.connect(self.load_started)
        self.page.loadProgress.connect(self.progress.setValue)
        self.page.loadingChanged.connect(self.loading_changed)
        self.page.loadFinished.connect(self.load_finished)
        self.page.urlChanged.connect(self.url_changed)
        self.page.renderProcessTerminated.connect(self.render_stopped)
        self.view.setPage(self.page)
        if previous is not None:
            previous.deleteLater()

    def busy_downloads(self):
        return any(not entry["finished"] for entry in self.downloads.values())

    def trusted_source(self, url):
        return source_url(url, self.website.hosts)

    def change_source(self, _index):
        if self.busy_downloads() or self.batch_running:
            return
        self.website = website_for(self.source_picker.currentData())
        self.show_recommendations()
        self.update_queue_labels()
        if self.query.text().strip():
            self.start_search()
        else:
            self.replace_page()
            self.status.setText(f"已选择 {self.website.label}，输入片名或选择视频开始。")
        self.update_controls()

    def choose_videos(self):
        if self.busy_downloads() or self.batch_running:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要查找字幕的视频", "",
            "视频文件 (" + " ".join("*" + ext for ext in sorted(VIDEO_EXTS)) + ")")
        if files:
            self.add_videos(files)

    def add_videos(self, paths):
        if self.busy_downloads() or self.batch_running:
            return
        known = {str(task.video).casefold() for task in self.tasks}
        first_new = len(self.tasks)
        rejected = 0
        for value in paths:
            try:
                path = Path(value).resolve(strict=True)
                if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
                    raise ValueError("not a video")
                key = str(path).casefold()
                if key in known:
                    continue
                known.add(key)
                self.append_task(SearchTask(uuid4().hex, path, search_terms(path.name)))
            except (OSError, ValueError):
                rejected += 1
        if len(self.tasks) > first_new:
            self.queue.setCurrentRow(first_new)
            self.start_search()
        if rejected:
            self.status.setText(f"已略过 {rejected} 个无法读取或不支持的文件。")
        self.update_controls()

    def select_task(self, row):
        if 0 <= row < len(self.tasks):
            task = self.tasks[row]
            self.query.setText(self.queries.get(task.task_id, task.query))
        self.show_recommendations()
        self.pages.setCurrentWidget(self.recommendations)
        self.update_controls()

    def next_task(self):
        if self.busy_downloads() or self.batch_running:
            return
        row = self.queue.currentRow() + 1
        if row < len(self.tasks):
            self.queue.setCurrentRow(row)
            self.start_search()

    def start_search(self):
        if self.busy_downloads() or self.closing:
            return
        query = " ".join(self.query.text().split()).strip()
        if not query:
            self.status.setText("请先选择视频或输入搜索词。")
            self.query.setFocus()
            return
        task = self.current_task()
        self.prepare_context(task, query)
        self.search_pending = True
        # A new page invalidates download events belonging to the previous task.
        # The profile remains alive so in-window verification cookies can persist.
        self.replace_page()
        self.pending_query = query
        self.pages.setCurrentWidget(self.view)
        self.status.setText(f"正在打开 {self.website.label}；找到明确的搜索框后会自动填写并提交。")
        self.page.setUrl(QUrl(self.website.home))
        self.update_controls()

    def load_started(self):
        if self.sender() is not self.page or self.closing:
            return
        self.navigation_generation += 1
        self.last_load_error = ""
        self.verification_required = False
        self.progress.setValue(0)
        self.progress.show()
        self.load_timer.start()

    def loading_changed(self, info):
        if self.sender() is not self.page or self.closing:
            return
        if info.errorCode():
            self.last_load_error = (f"HTTP {info.errorCode()}" if info.errorDomain().name == "HttpStatusCodeDomain"
                                    else f"{info.errorString()} ({info.errorCode()})")

    def load_finished(self, success):
        if self.sender() is not self.page or self.closing:
            return
        self.load_timer.stop()
        self.progress.hide()
        self.update_controls()
        page, generation = self.page, self.navigation_generation

        def classified(challenge):
            if self.closing or self.page is not page or generation != self.navigation_generation:
                return
            # Some sites deliberately return 404 for a usable CAPTCHA page.
            self.verification_required = challenge is True
            if self.verification_required:
                self.pause_batch("网站要求验证码，请处理或切换来源")
                self.status.setText("当前网站要求完成验证码。可在网页验证后继续，或切换右上角备用来源。")
            elif not success:
                self.pending_query = None
                self.search_pending = False
                self.pause_batch("网站未能加载")
                self.status.setText("当前网站未能加载。可切换右上角备用来源，或使用系统浏览器。 " + self.last_load_error)
            elif self.pending_query is not None:
                query, self.pending_query = self.pending_query, None
                QTimer.singleShot(400, lambda: self.fill_search(page, generation, query))
            else:
                self.status.setText("网页已打开。选择合适的字幕下载，文件将自动进入暂存区；需要验证时直接在网页完成。")
                if self.search_pending:
                    self.read_candidates(page, generation)

        page.runJavaScript(verification_script(), classified)

    def load_timed_out(self):
        self.pending_query = None
        self.search_pending = False
        self.pause_batch("网页超时")
        self.page.triggerAction(QWebEnginePage.WebAction.Stop)
        self.progress.hide()
        self.status.setText("网页加载超过 30 秒，已停止等待。可重新加载或使用系统浏览器。")

    def fill_current_page(self):
        if self.busy_downloads():
            return
        if self.verification_required:
            self.status.setText("请先在网页中完成网站验证码，搜索词已为你保留。")
            return
        row = self.queue.currentRow()
        task_id = self.tasks[row].task_id if 0 <= row < len(self.tasks) else None
        query = self.query.text().strip()
        if (self.active_task is None or self.active_task["query"] != query
                or (task_id is not None and self.active_task["taskId"] != task_id)):
            self.start_search()
            return
        self.fill_search(self.page, self.navigation_generation, query)

    def fill_search(self, page, generation, query):
        if (self.closing or self.page is not page or generation != self.navigation_generation
                or not query or not self.trusted_source(page.url().toString())):
            return
        self.search_pending = True

        def filled(result):
            if self.closing or self.page is not page or generation != self.navigation_generation:
                return
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (ValueError, RecursionError):
                    result = None
            if isinstance(result, dict) and result.get("status") == "submitted":
                self.load_timer.start()
                self.status.setText("已自动填写搜索词并提交；正在等待网站结果。")
            else:
                self.pause_batch("需要在网页完成搜索")
                self.status.setText("未找到唯一可用的搜索框。完成网页验证后可点“填入本页”，也可复制搜索词在网页中搜索。")

        script = submit_subhd_search_script if self.website.provider == "subhd" else submit_search_script
        # Qt 6 does not reliably convert arbitrary JS objects to QVariantMap.
        page.runJavaScript("JSON.stringify(" + script(query, self.website.hosts) + ")", filled)

    def url_changed(self, url):
        if self.sender() is not self.page or self.closing:
            return
        # Display only origin + path; signed query strings are not copied to logs.
        self.address.setText(url.host() + url.path() if url.host() else "尚未联网")
        self.update_controls()

    def go_back(self):
        if not self.busy_downloads():
            self.pending_query = None
            self.page.triggerAction(QWebEnginePage.WebAction.Back)

    def reload_page(self):
        if not self.busy_downloads() and self.trusted_source(self.page.url().toString()):
            # Refresh does not automatically submit a form a second time.
            if not self.verification_required:
                self.pending_query = None
            self.page.triggerAction(QWebEnginePage.WebAction.Reload)

    def open_popup(self, request):
        if request.isUserInitiated() and self.trusted_source(request.requestedUrl().toString()):
            request.openIn(self.page)
        else:
            self.status.setText("已阻止自动弹窗或站外跳转。需要站外页面时可使用系统浏览器。")

    def open_external(self):
        url = self.page.url()
        if not self.trusted_source(url.toString()):
            url = QUrl(self.website.home)
        QApplication.clipboard().setText(self.query.text().strip())
        if QDesktopServices.openUrl(url):
            self.status.setText("已在系统浏览器打开，搜索词已复制。系统浏览器的下载暂不能自动接入此窗口。")
        else:
            self.status.setText(f"系统浏览器未能打开，可手动访问 {self.website.home}。搜索词已复制。")

    def receive_download(self, download):
        if download.id() in self.downloads:
            return
        try:
            if (self.closing or self.batch_running or self.active_task is None or download.page() is not self.page
                    or not self.trusted_source(self.page.url().toString()) or download.isSavePageDownload()
                    or not (public_https(download.url().toString()) or same_origin_blob(
                        download.url().toString(), self.page.url().toString(), self.website.hosts))):
                raise ValueError("此下载不属于当前网站搜索，已拒绝。")
            if len(self.downloads) >= MAX_SESSION_FILES:
                raise ValueError("本次窗口已接收 20 个文件，请先处理暂存文件。")
            if sum(not row["finished"] for row in self.downloads.values()) >= 2:
                raise ValueError("已有两份文件正在下载，请完成后再下载。")
            total = download.totalBytes()
            used = sum(row["received"] for row in self.downloads.values())
            if total > MAX_DOWNLOAD_BYTES or used + max(0, total) > MAX_SESSION_BYTES:
                raise ValueError("下载超出限制：单份 64 MiB，每次窗口累计 256 MiB。")
            if download.mimeType().split(";")[0] in {
                "text/html", "application/xhtml+xml", "application/x-msdownload", "application/x-executable",
            }:
                raise ValueError("网站返回了网页或程序，未作为字幕接收。")
            filename = safe_filename(download.suggestedFileName())
            path = reserve_download(self.inbox, filename)
            item = QListWidgetItem(f"{filename} · 等待下载")
            context = {key: value for key, value in self.active_task.items() if key != "resultKey"}
            # Selected recommendations are hints; never mark a download matched.
            choice = self.choices.get(self.active_task["resultKey"])
            if choice and self.page.url().toString().rstrip("/") == choice["url"]:
                context["chosenCandidate"] = {key: choice[key] for key in ("url", "title", "release", "language")}
            entry = {"request": download, "path": path, "item": item,
                     "context": context, "finished": False,
                     "received": 0, "reason": "", "cancel_requested": False}
            self.downloads[download.id()] = entry
            item.setData(Qt.ItemDataRole.UserRole, download.id())
            self.download_list.addItem(item)
            self.download_list.setCurrentItem(item)
            download.setDownloadDirectory(str(path.parent))
            download.setDownloadFileName(path.name)
            for signal in (download.receivedBytesChanged, download.totalBytesChanged,
                           download.stateChanged, download.isFinishedChanged):
                signal.connect(lambda *_args, key=download.id(): self.download_changed(key))
            self.status.setText("正在接收下载。网页可能自动触发下载，完成后仍需检查内容与匹配关系。")
            download.accept()
            self.download_changed(download.id())
        except (ValueError, OSError) as error:
            download.cancel()
            self.status.setText(str(error))
        self.update_controls()

    def download_changed(self, key):
        entry = self.downloads.get(key)
        if entry is None or entry["finished"]:
            return
        request = entry["request"]
        entry["received"] = max(0, request.receivedBytes())
        aggregate = sum(row["received"] for row in self.downloads.values())
        if not entry["cancel_requested"] and (
            entry["received"] > MAX_DOWNLOAD_BYTES or request.totalBytes() > MAX_DOWNLOAD_BYTES
            or aggregate > MAX_SESSION_BYTES
        ):
            entry["reason"] = "下载超过暂存限额，已停止。"
            entry["cancel_requested"] = True
            request.cancel()
            return
        state = request.state()
        terminal = QWebEngineDownloadRequest.DownloadState
        if state in {terminal.DownloadCompleted, terminal.DownloadCancelled, terminal.DownloadInterrupted}:
            self.finish_download(entry)
        else:
            received, total = entry["received"], request.totalBytes()
            progress = f"{received / 1048576:.1f} MiB"
            if total > 0:
                progress += f" / {total / 1048576:.1f} MiB · {min(100, received * 100 // total)}%"
            entry["item"].setText(f"{entry['path'].name} · {progress}")
        self.update_controls()

    def finish_download(self, entry):
        entry["finished"] = True  # Signals can fire twice; write a receipt only once.
        request, path = entry["request"], entry["path"]
        state = request.state()
        terminal = QWebEngineDownloadRequest.DownloadState
        status = "cancelled"
        message = entry["reason"] or "已停止，未导入"
        if state == terminal.DownloadCompleted:
            try:
                status = inspect_download(path)
                message = "压缩包已暂存，待检查解压" if status == "archive_pending" else "字幕已暂存，待匹配"
            except (OSError, ValueError) as error:
                status, message = "rejected", str(error)
        elif state == terminal.DownloadInterrupted:
            status = "interrupted"
            message = request.interruptReasonString() or "下载中断，请在网页中重试"
        entry["stagingId"] = uuid4().hex
        receipt = {**entry["context"], "status": status, "stagingId":entry["stagingId"],
                   "receivedBytes": entry["received"], "matchConfirmed": False,
                   "savedAt": datetime.now().astimezone().isoformat(timespec="seconds"), "message": message}
        try:
            write_receipt(path, receipt)
        except OSError as error:
            message += f"；收据保存失败：{error}"
        entry["item"].setText(f"{path.name} · {message}")
        entry["item"].setToolTip(f"搜索任务：{entry['context']['videoName']}\n{message}")
        if status in {"archive_pending", "subtitle_candidate"}:
            self.download_staged.emit({**receipt, "stagingPath": str(path)})
        if entry.get("registered"):
            entry["item"].setFlags(entry["item"].flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry["item"].setCheckState(Qt.CheckState.Checked)
        self.status.setText(entry.get("import_error") or message + "。可勾选下载后导入审阅；最终确认前不会写入视频目录。")
        self.schedule_auto_import()

    def import_selection(self):
        return [entry["stagingId"] for entry in self.downloads.values()
                if entry.get("registered") and not entry.get("imported")
                and entry["item"].checkState() == Qt.CheckState.Checked]

    def schedule_auto_import(self):
        if not self.closing and hasattr(self,'auto_import') and self.auto_import.isChecked(): self.auto_timer.start()

    def auto_import_ready(self):
        if (self.closing or not self.workspace_context or not self.auto_import.isChecked()
                or self.import_busy or self.busy_downloads() or self.batch_running): return
        if self.import_selection(): self.request_import(automatic=True)

    def request_import(self, _checked=False, *, automatic=False):
        selected = self.import_selection()
        if automatic:
            selected = [entry['stagingId'] for entry in self.downloads.values()
                if entry.get('stagingId') in selected and not entry.get('auto_attempted')]
        if not selected or self.import_busy or self.busy_downloads() or self.batch_running:
            return
        self.import_busy = True
        if automatic:
            for entry in self.downloads.values():
                if entry.get('stagingId') in selected: entry['auto_attempted'] = True
        self.return_after_import = not automatic
        self.status.setText('正在检查并自动解压下载，准备实际字幕与待确认匹配…')
        self.update_controls()
        self.import_requested.emit(selected)

    def import_finished(self, result=None, error=""):
        self.import_busy = False
        if error:
            self.status.setText(error)
        elif result:
            by_id = {entry.get("stagingId"):entry for entry in self.downloads.values()}
            for outcome in result["outcomes"]:
                entry = by_id.get(outcome["stagingId"])
                if not entry: continue
                entry["imported"] = bool(outcome["count"])
                message = outcome["error"] or f"已导入 {outcome['count']} 份，等待审阅"
                if outcome["skipped"]: message += f" · 忽略 {len(outcome['skipped'])} 项"
                entry["item"].setText(f"{entry['path'].name} · {message}")
                entry["item"].setToolTip("\n".join([message, *outcome["skipped"]]))
                if entry["imported"]: entry["item"].setCheckState(Qt.CheckState.Unchecked)
            failures=[outcome['error'] for outcome in result['outcomes'] if outcome['error']]
            if failures and not result['imported']:
                self.status.setText('自动解压未完成：'+failures[0]+' 原包保留在下载缓存，可更换下载版本。')
            else:
                self.status.setText(f"已准备 {result['imported']} 份字幕 · {result['assigned']} 个匹配待确认 · {result['unassigned']} 份请从候选选择。")
        self.update_controls()

    def cancel_selected(self):
        item = self.download_list.currentItem()
        entry = self.downloads.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if entry and not entry["finished"]:
            entry["reason"] = "用户已停止下载"
            entry["cancel_requested"] = True
            entry["request"].cancel()

    def open_inbox(self):
        try:
            self.cache_root.mkdir(parents=True,exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cache_root))):
                self.status.setText('未能打开下载缓存。')
        except OSError as error: self.status.setText(f'缓存目录无法访问：{error}')

    def render_stopped(self, *_args):
        if self.sender() is not self.page or self.closing:
            return
        self.load_timer.stop()
        self.pending_query = None
        self.search_pending = False
        self.pause_batch("网页进程已停止")
        self.progress.hide()
        self.status.setText("网页进程已停止。已接收的文件仍保留，可重新查找或使用系统浏览器。")

    def update_controls(self):
        if not hasattr(self, "download_list"):
            return
        busy = self.busy_downloads() or self.batch_running or self.import_busy
        for widget in (self.add_button, self.search_button, self.query, self.queue, self.source_picker):
            widget.setEnabled(not busy)
        ready = self.page is not None and self.trusted_source(self.page.url().toString())
        self.fill_button.setEnabled(not busy and ready)
        self.reload_button.setEnabled(not busy and ready)
        self.back_button.setEnabled(not busy and self.page is not None and self.page.history().canGoBack())
        self.next_button.setEnabled(not busy and self.queue.currentRow() + 1 < len(self.tasks))
        self.batch_button.setEnabled(not busy and any(self.queue.item(i).checkState() == Qt.CheckState.Checked for i in range(len(self.tasks))))
        self.stop_batch_button.setEnabled(self.batch_running)
        self.language_picker.setEnabled(not self.batch_running)
        self.recommendations.setEnabled(not busy)
        task = self.current_task()
        self.pages.setTabEnabled(1, self.active_task is not None and (task is None or self.active_task["taskId"] == task.task_id))
        self.inbox_button.setEnabled(True)
        self.queue_title.setText(f'视频搜索队列  ({len(self.tasks)})')
        self.clear_button.setEnabled(not busy and bool(self.tasks))
        self.review_button.setVisible(bool(self.workspace_context))
        self.review_button.setEnabled(not self.import_busy and any(entry.get('imported') for entry in self.downloads.values()))
        self.auto_import.setVisible(bool(self.workspace_context))
        item = self.download_list.currentItem()
        entry = self.downloads.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self.cancel_button.setEnabled(entry is not None and not entry["finished"])
        self.import_button.setEnabled(not busy and bool(self.workspace_context) and bool(self.import_selection()))
        self.import_button.setVisible(bool(self.workspace_context))
        self.download_list.setEnabled(not self.import_busy)
        self.download_list.setVisible(bool(self.downloads))
        self.update_guide()

    def closeEvent(self, event):
        if self.import_busy:
            self.status.setText("正在完成字幕导入，请稍候再关闭。")
            event.ignore()
            return
        self.closing = True
        self.auto_timer.stop()
        self.batch_running = False
        self.batch_timer.stop()
        self.load_timer.stop()
        self.pending_query = None
        for entry in list(self.downloads.values()):
            if not entry["finished"]:
                entry["reason"] = "窗口关闭，下载已停止"
                entry["cancel_requested"] = True
                entry["request"].cancel()
        self.page.triggerAction(QWebEnginePage.WebAction.Stop)
        self.page.deleteLater()
        self.profile.deleteLater()
        super().closeEvent(event)


def main():
    import sys
    app = QApplication(sys.argv)
    app.setOrganizationName("YingXu")
    app.setApplicationName("YingXu Subtitle Browser Preview")
    app.setStyle("Fusion")
    window = SubtitleBrowser()
    window.show()
    return app.exec()
