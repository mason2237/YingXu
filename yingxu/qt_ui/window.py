"""Read-only workspace: choose a folder, scan, inspect actual naming plans."""
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QModelIndex
from PySide6.QtGui import QDesktopServices, QFont, QKeySequence, QPainter, QShortcut, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QProgressBar, QPushButton,
    QLineEdit, QMessageBox, QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from .design import BLUE, FONT, configure, icon
from .model import MatchDelegate, MatchModel, MatchProxy, STATUS, match_reason
from ..review import ReviewPlan, language_of
from ..core import extract_episode, similarity
from ..operations import HistoryStore, StalePlan, snapshot_from_review
from .worker import ScanWorker
from .apply_worker import ApplyWorker
from .flow import HistoryDialog, PreviewDialog, ResultDialog
from .interactions import Disclosure, MatchTable


def label(text, role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role:
        widget.setProperty("role", role)
    return widget


def button(text, action, role=None, symbol=None):
    widget = QPushButton(text)
    if role:
        widget.setProperty("role", role)
    if symbol:
        widget.setIcon(icon(symbol, "#FFFFFF" if role == "primary" else "#717784"))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(action)
    return widget


class ElideLabel(QLabel):
    """Keep full text for accessibility and tooltips; constrain only painting."""
    def __init__(self, text=""):
        super().__init__(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, self.width()))


class FileText(QTextEdit):
    """Selectable complete filenames, including unbroken long names."""
    def __init__(self, text="—"):
        super().__init__()
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setPlainText(text)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)

    def _fit(self, *_):
        height = max(26, math.ceil(self.document().size().height()) + 4)
        if height != self.height():
            self.setFixedHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


class Inspector(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Inspector")
        self.setMinimumWidth(300)
        self.record = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(16)
        heading = QHBoxLayout()
        heading.addWidget(label("匹配详情", "section"))
        self.badge = label("")
        self.badge.setFixedHeight(28)
        heading.addWidget(self.badge)
        heading.addStretch()
        self.position = label("", "muted")
        heading.addWidget(self.position)
        outer.addLayout(heading)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(0, 0, 4, 0)
        self.body.setSpacing(8)
        self.video = self._field("视频文件")
        self.body.addSpacing(6)
        self.subtitle = self._field("匹配字幕")
        self.body.addSpacing(6)
        target_box = QFrame()
        target_box.setObjectName("Destination")
        target_layout = QVBoxLayout(target_box)
        target_layout.setContentsMargins(12, 12, 12, 12)
        target_layout.setSpacing(6)
        target_layout.addWidget(label("整理后名称", "eyebrow"))
        self.target = FileText()
        self.target.setAccessibleName("整理后完整名称")
        target_layout.addWidget(self.target)
        self.location_hint = label("", "muted")
        self.location_hint.setWordWrap(True)
        target_layout.addWidget(self.location_hint)
        self.body.addWidget(target_box)
        self.body.addSpacing(8)
        self.score = label("", "section")
        self.body.addWidget(self.score)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setFixedHeight(4)
        self.meter.setTextVisible(False)
        self.body.addWidget(self.meter)
        self.reason = label("", "muted")
        self.reason.setWordWrap(True)
        self.body.addWidget(self.reason)
        self.body.addSpacing(8)
        self.body.addWidget(label("关联字幕", "eyebrow"))
        self.match_select = QComboBox()
        self.match_select.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.match_select.setMinimumContentsLength(8)
        self.match_select.currentIndexChanged.connect(self._match_changed)
        self.body.addWidget(self.match_select)
        self.body.addWidget(label("候选字幕", "eyebrow"))
        self.candidate = QComboBox()
        self.candidate.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.candidate.setMinimumContentsLength(8)
        self.candidate.setMaxVisibleItems(12)
        self.candidate.currentIndexChanged.connect(self._candidate_changed)
        self.body.addWidget(self.candidate)
        self.candidate_info = label("", "muted")
        self.candidate_info.setWordWrap(True)
        self.body.addWidget(self.candidate_info)
        review_actions = QHBoxLayout()
        self.replace = button("更换字幕", lambda: self.window().assign_candidate(False))
        self.add = button("添加语言", lambda: self.window().assign_candidate(True), "quiet")
        review_actions.addWidget(self.replace)
        review_actions.addWidget(self.add)
        self.body.addLayout(review_actions)
        self.remove = button("移除关联", self._remove_match, "quiet")
        self.body.addWidget(self.remove, alignment=Qt.AlignmentFlag.AlignLeft)
        decision_actions = QHBoxLayout()
        self.confirm = button("确认匹配", lambda: self.window().confirm_current(), "primary")
        self.skip = button("跳过", lambda: self.window().toggle_skip(), "quiet")
        decision_actions.addWidget(self.confirm)
        decision_actions.addWidget(self.skip)
        self.body.addLayout(decision_actions)
        self.paths_toggle = button("文件位置", self._toggle_paths, "quiet", "down")
        self.paths_toggle.setToolTip("展开或收起完整路径")
        self.paths_toggle.setCheckable(True)
        self.body.addWidget(self.paths_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.paths = FileText()
        self.paths.setFont(QFont(FONT, 10))
        self.path_disclosure = Disclosure(self.paths)
        self.body.addWidget(self.path_disclosure)
        self.body.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.adjust = button("调整匹配与候选", lambda: self.scroll.ensureWidgetVisible(self.replace, 0, 12), "quiet", "down")
        outer.addWidget(self.adjust)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy = button("复制名称", self.copy_name, symbol="copy")
        self.copy.setToolTip("复制整理后的完整文件名")
        self.open = button("打开目录", self.open_folder, "quiet", "open")
        actions.addWidget(self.copy, 1)
        actions.addWidget(self.open, 1)
        outer.addLayout(actions)

    def _field(self, title):
        self.body.addWidget(label(title, "eyebrow"))
        value = FileText()
        value.setAccessibleName(title)
        self.body.addWidget(value)
        return value

    def _toggle_paths(self):
        expanded = self.paths_toggle.isChecked()
        self.paths_toggle.setIcon(icon("up" if expanded else "down"))
        self.path_disclosure.set_expanded(expanded)

    def show_record(self, record, index, total, move):
        self.record = record
        match = record.subtitles[0] if record.subtitles else None
        self.position.setText(f"{index + 1} / {total}")
        text, fg, bg = STATUS[record.state]
        self.badge.setText(text)
        self.badge.setStyleSheet(f"color:{fg}; background:{bg}; border-radius:5px; padding:3px 10px; font-size:10pt;")
        self.video.setPlainText(record.video.name)
        self.subtitle.setPlainText(match.source.name if match else "尚未找到匹配字幕")
        self.target.setPlainText(match.target.name if match else "等待选择字幕")
        self.location_hint.setText(("移动至视频所在目录" if move else "保留字幕所在目录") if match else "未匹配项目不会产生文件变更")
        self.score.setText(f"匹配评分   {round(match.score * 100)} / 100" if match else "需要检查")
        self.meter.setVisible(bool(match))
        self.meter.setValue(round(match.score * 100) if match else 0)
        self.reason.setText(match_reason(record))
        self.paths.setPlainText(f"视频\n{record.video}\n\n字幕\n{match.source if match else '—'}\n\n目标\n{match.target if match else '—'}")
        self.copy.setText("复制名称")
        self.copy.setIcon(icon("copy"))
        self.copy.setEnabled(bool(match))
        self.open.setToolTip("打开字幕所在目录" if match else "打开视频所在目录")
        self.adjust.setEnabled(bool(self.window().review))

    def show_review(self, plan: ReviewPlan, index: int):
        row = plan.rows[index]
        self.match_select.blockSignals(True)
        self.match_select.clear()
        for match in row.matches:
            self.match_select.addItem(f"{language_of(match.source)} · {match.source.name}", match.source)
        self.match_select.setEnabled(bool(row.matches))
        self.match_select.blockSignals(False)
        self.candidate.blockSignals(True)
        self.candidate.clear()
        for sub, score, owner, lang in plan.candidates(index):
            note = f"  ·  已用于第 {owner + 1} 项" if owner is not None and owner != index else ""
            self.candidate.addItem(f"{round(score * 100)} · {lang} · {sub.name}{note}", sub)
        self.candidate.setEnabled(bool(plan.subtitles))
        self.candidate.blockSignals(False)
        self._candidate_changed()
        self._match_changed()
        self.confirm.setEnabled(bool(row.matches) and not row.skipped)
        self.skip.setText("恢复审阅" if row.skipped else "跳过")

    def _match_changed(self, *_):
        if not self.record:
            return
        source = self.match_select.currentData()
        match = next((item for item in self.record.subtitles if item.source == source), None)
        if match is None:
            self.remove.setEnabled(False)
            return
        self.remove.setEnabled(True)
        self.subtitle.setPlainText(match.source.name)
        self.target.setPlainText(match.target.name)
        self.score.setText(f"匹配评分   {round(match.score * 100)} / 100" + (" · 人工指定" if match.manual else ""))
        self.meter.setValue(round(match.score * 100))
        self.reason.setText(match_reason(self.record, match))
        self.paths.setPlainText(f"视频\n{self.record.video}\n\n字幕\n{match.source}\n\n目标\n{match.target}")

    def _candidate_changed(self, *_):
        sub = self.candidate.currentData()
        if not self.record or sub is None:
            self.candidate_info.setText("扫描范围内没有可选字幕")
            self.replace.setEnabled(False)
            self.add.setEnabled(False)
            return
        video_ep = extract_episode(self.record.video.stem)
        sub_ep = extract_episode(sub.stem)
        mismatch = bool(video_ep and sub_ep and (video_ep[1] != sub_ep[1] or
                        (video_ep[0] is not None and sub_ep[0] is not None and video_ep[0] != sub_ep[0])))
        owner = self.window().review.owner(sub) if self.window().review else None
        episode_note = ("季数或集数冲突，请核对后人工选择" if mismatch else
                        "集数一致" if video_ep and sub_ep else "集数未完整识别，请核对")
        owner_note = f" · 已用于第 {owner + 1} 项" if owner is not None and owner != self.window().current_source_row() else ""
        self.candidate_info.setText(f"{sub.name}\n{language_of(sub)} · 评分 {round(similarity(self.record.video, sub) * 100)} / 100 · {episode_note}{owner_note}")
        available = owner is None or owner == self.window().current_source_row()
        self.replace.setEnabled(available)
        self.add.setEnabled(available and bool(self.record.subtitles))

    def _remove_match(self):
        source = self.match_select.currentData()
        if source:
            self.window().remove_current(source)

    def copy_name(self):
        if self.record and self.record.subtitles:
            source = self.match_select.currentData()
            match = next((item for item in self.record.subtitles if item.source == source), self.record.subtitles[0])
            QApplication.clipboard().setText(match.target.name)
            self.copy.setText("已复制")
            self.copy.setIcon(icon("check", "#347A63"))
            QTimer.singleShot(1200, self._reset_copy)

    def _reset_copy(self):
        self.copy.setText("复制名称")
        self.copy.setIcon(icon("copy"))

    def open_folder(self):
        if self.record:
            source = self.match_select.currentData()
            path = source if source else self.record.video
            success = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            self.window().status.setText("已打开文件所在目录" if success else "无法打开目录，请检查路径是否仍然存在")


class Workspace(QMainWindow):
    def __init__(self):
        super().__init__()
        self.folder = None
        self.worker = None
        self.apply_worker = None
        self.history = HistoryStore()
        self.last_result = None
        self._apply_result_data = None
        self._apply_failure = ""
        self.review = None
        self.scan_move = False
        self._cancel_requested = False
        self._pending_close = False
        self._compact = False
        self._detail_requested = True
        self.setWindowTitle("映序 · 字幕整理器")
        self.setWindowIcon(icon("brand", BLUE, 32))
        self.setMinimumSize(920, 620)
        self.setAcceptDrops(True)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        content = QWidget()
        area = QVBoxLayout(content)
        area.setContentsMargins(28, 22, 28, 20)
        area.setSpacing(16)
        titles = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(5)
        text.addWidget(label("匹配预览", "heading"))
        self.summary = label("选择文件夹，查看视频与字幕的对应关系", "muted")
        text.addWidget(self.summary)
        titles.addLayout(text, 1)
        self.counts = label("", "muted")
        titles.addWidget(self.counts)
        self.details_button = button("显示详情", self.toggle_details, "quiet", "panel")
        self.details_button.setToolTip("显示或收起匹配详情 · Ctrl+I")
        self.details_button.setEnabled(False)
        titles.addWidget(self.details_button)
        self.preview_button = button("预览变更", self.preview_changes, "primary")
        self.preview_button.setEnabled(False)
        self.preview_button.setToolTip("先核对全部源文件与最终名称，再确认整理")
        titles.addWidget(self.preview_button)
        area.addLayout(titles)
        tools = QHBoxLayout()
        tools.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索视频、字幕或目标名称  ·  Ctrl+F")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_changed)
        tools.addWidget(self.search, 1)
        self.state_filter = QComboBox()
        self.state_filter.addItems(("全部", "需确认", "未匹配", "待整理", "已符合", "已跳过"))
        self.state_filter.currentTextChanged.connect(self._filter_changed)
        tools.addWidget(self.state_filter)
        area.addLayout(tools)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(16)
        self.splitter.setChildrenCollapsible(False)
        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(420)
        self.table = MatchTable()
        self.model = MatchModel(self)
        self.proxy = MatchProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(MatchDelegate(self.table))
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(76)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionsClickable(True)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 96), (2, 108)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.selectionModel().currentRowChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _: self._reveal_details())
        self.stack.addWidget(self.table)
        self.empty = self._empty_page()
        self.stack.addWidget(self.empty)
        self.stack.setCurrentWidget(self.empty)
        self.splitter.addWidget(self.stack)
        self.inspector = Inspector()
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([820, 340])
        self.inspector.hide()
        area.addWidget(self.splitter, 1)
        layout.addWidget(content, 1)
        layout.addWidget(self._footer())
        self.resize(1240, 840)
        for keys, action in (("Ctrl+O", self.choose_folder), ("F5", self.start_scan),
                             ("Ctrl+I", self.toggle_details), ("Ctrl+F", self.search.setFocus)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(action)

    def _header(self):
        frame = QFrame()
        frame.setObjectName("Header")
        box = QVBoxLayout(frame)
        box.setContentsMargins(28, 14, 28, 14)
        box.setSpacing(14)
        brand = QHBoxLayout()
        mark = label("")
        mark.setPixmap(icon("brand", BLUE, 30).pixmap(30, 30))
        brand.addWidget(mark)
        brand.addSpacing(4)
        brand.addWidget(label("映序", "brand"))
        brand.addSpacing(12)
        brand.addWidget(label("字幕工作台", "muted"))
        brand.addStretch()
        self.history_button = button("操作记录", self.show_history, "quiet")
        brand.addWidget(self.history_button)
        brand.addWidget(label("本地处理", "muted"))
        box.addLayout(brand)
        directory = QHBoxLayout()
        directory.setSpacing(12)
        folder = QFrame()
        folder.setObjectName("Folder")
        folder_layout = QHBoxLayout(folder)
        folder_layout.setContentsMargins(14, 10, 14, 10)
        folder_icon = label("")
        folder_icon.setPixmap(icon("folder").pixmap(20, 20))
        folder_layout.addWidget(folder_icon)
        folder_text = QVBoxLayout()
        folder_text.setSpacing(2)
        self.folder_title = ElideLabel("选择一个工作目录")
        self.folder_title.setProperty("role", "folderTitle")
        self.folder_title.setMinimumHeight(22)
        self.folder_label = ElideLabel("视频与字幕所在的文件夹")
        self.folder_label.setFont(QFont(FONT, 10))
        self.folder_label.setMinimumHeight(20)
        folder_text.addWidget(self.folder_title)
        folder_text.addWidget(self.folder_label)
        folder_layout.addLayout(folder_text, 1)
        directory.addWidget(folder, 1)
        self.choose = button("选择文件夹", self.choose_folder)
        self.choose.setToolTip("选择工作目录 · Ctrl+O")
        directory.addWidget(self.choose)
        self.scan = button("扫描文件", self.start_scan, "primary", "scan")
        self.scan.setEnabled(False)
        self.scan.setToolTip("扫描并生成预览 · F5")
        directory.addWidget(self.scan)
        box.addLayout(directory)
        options = QHBoxLayout()
        options.setSpacing(24)
        self.recursive = QCheckBox("包含子文件夹")
        self.recursive.setChecked(True)
        self.move = QCheckBox("字幕移至视频目录")
        self.move.setToolTip("仅影响目标路径预览；扫描不会移动文件")
        self.recursive.toggled.connect(self._invalidate)
        self.move.toggled.connect(self._invalidate)
        options.addWidget(self.recursive)
        options.addWidget(self.move)
        options.addStretch()
        self.cancel_scan = button("取消扫描", self.request_cancel, "quiet")
        self.cancel_scan.hide()
        options.addWidget(self.cancel_scan)
        options.addWidget(label("扫描只生成预览", "muted"))
        box.addLayout(options)
        return frame

    def _empty_page(self):
        page = QFrame()
        page.setStyleSheet("QFrame {background:white; border-radius:8px;}")
        box = QVBoxLayout(page)
        box.setContentsMargins(36, 30, 36, 30)
        box.addStretch(3)
        image = label("")
        image.setPixmap(icon("folder", "#A0ACC5", 48).pixmap(48, 48))
        box.addWidget(image, alignment=Qt.AlignmentFlag.AlignHCenter)
        box.addSpacing(16)
        self.empty_title = label("从一个文件夹开始", "heading")
        box.addWidget(self.empty_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.empty_note = label("选择包含视频和字幕的目录。\n映序会先列出匹配关系与整理后的名称。", "muted")
        self.empty_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_note.setWordWrap(True)
        box.addWidget(self.empty_note)
        box.addSpacing(16)
        self._empty_action = self.choose_folder
        self.empty_button = button("选择文件夹", lambda: self._empty_action(), "primary", "folder")
        box.addWidget(self.empty_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        box.addStretch(4)
        box.addWidget(label("支持 MKV、MP4 视频与 SRT、ASS、VTT 等字幕格式", "muted"),
                      alignment=Qt.AlignmentFlag.AlignHCenter)
        return page

    def _footer(self):
        footer = QFrame()
        footer.setObjectName("Footer")
        box = QHBoxLayout(footer)
        box.setContentsMargins(28, 10, 28, 10)
        self.status = ElideLabel("准备就绪")
        self.status.setFont(QFont(FONT, 10))
        box.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedSize(120, 4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        box.addWidget(self.progress)
        box.addSpacing(12)
        self.stop_apply = button("停止剩余项", self.request_stop_apply, "quiet")
        self.stop_apply.hide()
        box.addWidget(self.stop_apply)
        self.latest_button = button("查看结果", self.show_last_result, "quiet")
        self.latest_button.hide()
        box.addWidget(self.latest_button)
        self.footer_note = label("审阅前文件未改动", "muted")
        box.addWidget(self.footer_note)
        return footer

    def _show_empty(self, title, note, action=None, action_text="选择文件夹"):
        self.empty_title.setText(title)
        self.empty_note.setText(note)
        self._empty_action = action
        self.empty_button.setText(action_text)
        self.empty_button.setVisible(action is not None)
        self.stack.setCurrentWidget(self.empty)
        self.inspector.hide()
        self.details_button.setEnabled(False)
        self.details_button.setText("显示详情")
        self.preview_button.setEnabled(False)

    def choose_folder(self):
        if self.worker or self.apply_worker:
            return
        chosen = QFileDialog.getExistingDirectory(self, "选择工作目录", str(self.folder or Path.home()))
        if chosen:
            self.set_folder(Path(chosen))

    def set_folder(self, folder):
        if self.worker or self.apply_worker:
            return
        self.folder = Path(folder)
        self.folder_title.setText(self.folder.name or str(self.folder))
        self.folder_label.setText(str(self.folder))
        self.choose.setText("更换文件夹")
        self.scan.setEnabled(True)
        self.cancel_scan.setEnabled(True)
        self._invalidate()

    def _invalidate(self):
        if self.worker or self.apply_worker or not self.folder:
            return
        self.review = None
        self.model.set_plan([])
        self.summary.setText("扫描后可查看每个视频对应的字幕")
        self.counts.setText("")
        self.status.setText("目录或选项已更新，请扫描以生成预览")
        self.footer_note.setText("扫描与审阅不修改文件")
        self._show_empty("准备扫描", "将读取所选目录，生成一份可以检查的匹配清单。",
                         self.start_scan, "扫描文件")

    def start_scan(self):
        if self.worker or self.apply_worker or not self.folder:
            return
        self.review = None
        self._cancel_requested = False
        self.cancel_scan.setEnabled(True)
        self.model.set_plan([])
        self.scan_move = self.move.isChecked()
        self.counts.setText("")
        self.summary.setText("正在生成匹配预览…")
        self._show_empty("正在扫描文件", "读取目录并计算字幕匹配，文件不会被改动。")
        for control in (self.choose, self.scan, self.recursive, self.move):
            control.setEnabled(False)
        self.scan.setText("扫描中…")
        self.cancel_scan.show()
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status.setText("正在读取视频与字幕文件…")
        self.footer_note.setText("扫描与审阅不修改文件")
        self.worker = ScanWorker(self.folder, self.recursive.isChecked(), self.scan_move, self)
        self.worker.phase.connect(self.status.setText)
        self.worker.result.connect(self._show_result)
        self.worker.failed.connect(self._scan_error)
        self.worker.finished.connect(self._scan_finished)
        self.worker.start()

    def _show_result(self, review, videos, subtitles):
        if self._cancel_requested:
            return
        self.review = review
        self.model.set_review(review)
        self.preview_button.setEnabled(bool(videos))
        self.footer_note.setText("扫描与审阅不修改文件")
        self._update_summary()
        self.status.setText(f"扫描完成 · {subtitles - sum(len(r.matches) for r in review.rows)} 份字幕未分配")
        if not videos:
            self._show_empty("没有找到视频文件", f"扫描到 {subtitles} 份字幕。请检查目录或“包含子文件夹”选项。",
                             self.choose_folder)
        else:
            self.stack.setCurrentWidget(self.table)
            self.details_button.setEnabled(True)
            self._filter_changed()

    def _scan_error(self, error):
        if self._cancel_requested:
            return
        self.summary.setText("扫描未完成")
        self.status.setText(error)
        self._show_empty("无法读取这个目录", error, self.choose_folder, "重新选择文件夹")

    def _scan_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        for control in (self.choose, self.scan, self.recursive, self.move):
            control.setEnabled(True)
        self.scan.setText("重新扫描")
        self.cancel_scan.hide()
        self.progress.hide()
        if self._cancel_requested and not self._pending_close:
            self.status.setText("扫描已取消；预览未更新")
            self._show_empty("扫描已取消", "当前没有待审阅的扫描结果。", self.start_scan, "重新扫描")
        if self._pending_close:
            self.close()

    def _selection_changed(self, current, previous):
        if current.isValid():
            source = self.proxy.mapToSource(current).row()
            record = self.model.records[source]
            self.inspector.show_record(record, source, self.model.rowCount(), self.scan_move)
            if self.review:
                self.inspector.show_review(self.review, source)

    def current_source_row(self):
        current = self.table.currentIndex()
        return self.proxy.mapToSource(current).row() if current.isValid() else -1

    def _current_video(self):
        row = self.current_source_row()
        return self.model.records[row].video if row >= 0 else None

    def _select_video(self, video):
        for source_row, record in enumerate(self.model.records):
            if record.video == video:
                index = self.proxy.mapFromSource(self.model.index(source_row, 0))
                if index.isValid():
                    self.table.setCurrentIndex(index)
                    self.table.selectRow(index.row())
                    self._selection_changed(index, QModelIndex())
                    return
        if self.proxy.rowCount():
            self.table.selectRow(0)
            self._selection_changed(self.proxy.index(0, 0), QModelIndex())

    def _filter_changed(self, *_):
        video = self._current_video()
        self.proxy.set_query(self.search.text())
        self.proxy.set_state_filter(self.state_filter.currentText())
        if not self.review or not self.review.rows:
            return
        if self.proxy.rowCount():
            self.stack.setCurrentWidget(self.table)
            self.details_button.setEnabled(True)
            self._select_video(video)
            self._sync_details()
        else:
            self._show_empty("没有符合条件的项目", "修改搜索词或筛选条件后再试。")
        self.counts.setText(f"显示 {self.proxy.rowCount()} / {self.model.rowCount()} 项")
        self.preview_button.setEnabled(bool(self.review.rows))

    def _refresh_review(self, video=None):
        if not self.review:
            return
        video = video or self._current_video()
        self.model.set_review(self.review)
        self.preview_button.setEnabled(True)
        self._update_summary()
        self._filter_changed()
        self._select_video(video)

    def _update_summary(self):
        if not self.review:
            return
        matched = sum(bool(row.matches) for row in self.review.rows)
        pending = sum(self.review.state(index) in {"需确认", "未匹配"}
                      for index in range(len(self.review.rows)))
        self.summary.setText(f"{len(self.review.rows)} 个视频  ·  {len(self.review.subtitles)} 份字幕  ·  {matched} 项已匹配")
        self.counts.setText(f"{pending} 项需要检查")

    def assign_candidate(self, add):
        if self.apply_worker:
            return
        row = self.current_source_row()
        if row < 0 or not self.review:
            return
        subtitle = self.inspector.candidate.currentData()
        replace = None if add else self.inspector.match_select.currentData()
        try:
            self.review.assign(row, subtitle, replace)
        except ValueError as error:
            self.status.setText(str(error))
            return
        video = self.review.rows[row].video
        self._refresh_review(video)
        self.status.setText("已更新匹配预览；文件尚未改动")

    def remove_current(self, subtitle):
        if self.apply_worker:
            return
        row = self.current_source_row()
        if row >= 0 and self.review:
            video = self.review.rows[row].video
            self.review.remove(row, subtitle)
            self._refresh_review(video)
            self.status.setText("已移除字幕关联；文件尚未改动")

    def confirm_current(self):
        if self.apply_worker:
            return
        row = self.current_source_row()
        if row >= 0 and self.review:
            video = self.review.rows[row].video
            try:
                self.review.confirm(row)
            except ValueError as error:
                self.status.setText(str(error))
                return
            self._refresh_review(video)
            self.status.setText("已确认当前匹配；文件尚未改动")

    def toggle_skip(self):
        if self.apply_worker:
            return
        row = self.current_source_row()
        if row >= 0 and self.review:
            video = self.review.rows[row].video
            self.review.skip(row, not self.review.rows[row].skipped)
            self._refresh_review(video)
            self.status.setText("审阅状态已更新；文件尚未改动")

    def request_cancel(self):
        if self.worker:
            self._cancel_requested = True
            self.cancel_scan.setEnabled(False)
            self.status.setText("取消请求已收到，正在等待当前计算结束…")

    def preview_changes(self):
        if self.worker or self.apply_worker or not self.review:
            return
        try:
            snapshot = snapshot_from_review(self.review)
        except (StalePlan, OSError) as error:
            QMessageBox.warning(self, "无法生成安全预览", f"{error}\n\n请重新扫描并检查文件位置。")
            return
        dialog = PreviewDialog(snapshot, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._start_apply(snapshot)

    def _start_apply(self, snapshot):
        if self.worker or self.apply_worker or snapshot.pending_count or not snapshot.changes:
            return
        self._apply_result_data = None
        self._apply_failure = ""
        for control in (self.choose, self.scan, self.recursive, self.move, self.search,
                        self.state_filter, self.table, self.inspector, self.details_button,
                        self.preview_button, self.history_button):
            control.setEnabled(False)
        self.stop_apply.setEnabled(True)
        self.stop_apply.show()
        self.latest_button.hide()
        self.footer_note.setText("正在整理 · 可停止剩余项")
        self.progress.setRange(0, len(snapshot.changes))
        self.progress.setValue(0)
        self.progress.show()
        self.status.setText(f"正在整理 0 / {len(snapshot.changes)} 份字幕…")
        self.apply_worker = ApplyWorker(snapshot, self.history, self)
        self.apply_worker.progress.connect(self._apply_progress)
        self.apply_worker.result.connect(self._apply_result)
        self.apply_worker.failed.connect(self._apply_failed)
        self.apply_worker.finished.connect(self._apply_finished)
        self.apply_worker.start()

    def _apply_progress(self, done, total, filename):
        self.progress.setValue(done)
        self.status.setText(f"已处理 {done} / {total} · {filename}")

    def _apply_result(self, result):
        self._apply_result_data = result

    def _apply_failed(self, error):
        self._apply_failure = error

    def _apply_finished(self):
        worker = self.apply_worker
        self.apply_worker = None
        worker.deleteLater()
        self.stop_apply.hide()
        self.progress.hide()
        for control in (self.choose, self.scan, self.recursive, self.move, self.search,
                        self.state_filter, self.table, self.inspector, self.history_button):
            control.setEnabled(True)
        self.review = None
        self.model.set_plan([])
        self._show_empty("本次整理已结束", "查看本次结果，然后重新扫描以获取最新文件状态。",
                         self.start_scan, "重新扫描")
        self.counts.setText("")
        self.scan.setEnabled(bool(self.folder))
        self.footer_note.setText("请查看结果 · 重新扫描后可继续审阅")
        if self._apply_result_data:
            self.last_result = self._apply_result_data
            result = self.last_result
            self.latest_button.show()
            self.summary.setText(f"本次成功整理 {result.count('success')} 份字幕；最新结果可随时查看")
            self.status.setText(
                f"整理结束 · 成功 {result.count('success')} · 异常 {result.count('error') + result.count('blocked')} · 未执行 {result.count('cancelled')}")
            if not self._pending_close:
                ResultDialog(result, self.history, self).exec()
        elif self._apply_failure:
            self.summary.setText("整理过程异常，请重新扫描核对文件状态")
            self.status.setText("整理过程异常，请重新扫描核对文件状态")
            if not self._pending_close:
                QMessageBox.warning(self, "整理过程异常", self._apply_failure + "\n请重新扫描核对文件状态。")
        if self._pending_close:
            self.close()

    def request_stop_apply(self):
        if self.apply_worker:
            self.apply_worker.request_stop()
            self.stop_apply.setEnabled(False)
            self.status.setText("停止请求已收到；当前文件完成后停止剩余项…")

    def show_last_result(self):
        if self.last_result and not self.apply_worker:
            ResultDialog(self.last_result, self.history, self).exec()

    def show_history(self):
        if not self.apply_worker:
            HistoryDialog(self.history, self).exec()

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.worker and not self.apply_worker and len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).is_dir():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        folder = Path(event.mimeData().urls()[0].toLocalFile())
        if not self.worker and not self.apply_worker and folder.is_dir():
            self.set_folder(folder)
            self.start_scan()
            event.acceptProposedAction()

    def _reveal_details(self):
        if self.model.rowCount():
            self._detail_requested = True
            self._sync_details()

    def toggle_details(self):
        if self.model.rowCount():
            self._detail_requested = not self._detail_requested
            self._sync_details()

    def _sync_details(self):
        visible = self._detail_requested and bool(self.model.rowCount())
        self.inspector.setVisible(visible)
        self.details_button.setText("收起详情" if visible else "显示详情")
        if visible:
            self.splitter.setSizes([max(420, self.splitter.width() - 356), 340])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "inspector"):
            compact = self.width() < 1100
            if compact != self._compact:
                self._compact = compact
                self._detail_requested = not compact
                self._sync_details()

    def closeEvent(self, event):
        if self.worker or self.apply_worker:
            self._pending_close = True
            self.status.setText("正在等待当前任务结束，随后关闭窗口…")
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("映序")
    configure(app)
    window = Workspace()
    window.show()
    sys.exit(app.exec())
