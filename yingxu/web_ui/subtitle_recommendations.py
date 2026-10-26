"""Miuix-inspired native result panel; website text is always plain text."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem, QPushButton, QCheckBox, QScrollArea
from .desktop_design import EmptyArtwork, PALETTES, icon


def plain(text="", name=""):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setObjectName(name)
    return label


class RecommendationPanel(QWidget):
    open_requested = Signal(dict)
    chosen = Signal(dict)
    search_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 0)
        layout.setSpacing(12)
        self.summary = plain("选择视频后开始查找。搜索结果会按片名、季集和语言偏好排序。", "section")
        layout.addWidget(self.summary)
        self.list = QListWidget()
        self.list.setObjectName('resultsList')
        self.list.setWordWrap(True)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self.select)
        layout.addWidget(self.list, 1)
        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty);empty_layout.setContentsMargins(24,18,24,18)
        empty_layout.addStretch()
        self.artwork = EmptyArtwork()
        empty_layout.addWidget(self.artwork, 0, Qt.AlignmentFlag.AlignHCenter)
        title=plain('先确认片名，再查找字幕','emptyTitle');title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title)
        description=plain('例如：星际穿越。选好字幕后到网站下载，程序会自动解压，再请你确认匹配。','emptyDescription')
        description.setAlignment(Qt.AlignmentFlag.AlignCenter);empty_layout.addWidget(description)
        self.search_button=QPushButton('查找当前片名');self.search_button.setObjectName('primary')
        self.search_button.clicked.connect(self.search_requested)
        empty_layout.addWidget(self.search_button,0,Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch()
        layout.addWidget(self.empty,1)
        self.details = plain("优先查看是一条推荐，下载后仍需核对具体字幕文件。")
        self.details.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_scroll.setMinimumHeight(64)
        self.details_scroll.setMaximumHeight(110)
        self.details_scroll.setWidget(self.details)
        layout.addWidget(self.details_scroll)
        self.ack = QCheckBox("我已核对片名、年份 / 集数及语言提示")
        self.ack.toggled.connect(self.update_actions)
        layout.addWidget(self.ack)
        actions = QHBoxLayout()
        self.open_button = QPushButton("去网站下载")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.rows[self.list.currentRow()]))
        self.choose_button = QPushButton("选作推荐")
        self.choose_button.clicked.connect(lambda: self.chosen.emit(self.rows[self.list.currentRow()]))
        actions.addWidget(self.open_button)
        actions.addStretch()
        actions.addWidget(self.choose_button)
        action_frame = QFrame();action_frame.setObjectName('resultActions')
        actions.setContentsMargins(0, 10, 0, 12);action_frame.setLayout(actions)
        layout.addWidget(action_frame)
        self.set_results([], "选择视频，或在上方输入片名开始搜索。")

    def set_results(self, rows, message, chosen_url=None):
        self.rows = rows
        self.list.setVisible(bool(rows));self.empty.setVisible(not rows)
        self.details_scroll.setVisible(bool(rows))
        self.summary.setText(message)
        self.summary.setVisible(bool(rows))
        self.empty.setToolTip(message)
        self.list.blockSignals(True)
        self.list.clear()
        for row in rows:
            kept = " · 已保留" if row["url"] == chosen_url else ""
            item = QListWidgetItem(f"{row['label']}{kept}  ·  {row['language']}\n{row['release']}")
            item.setToolTip(row["release"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.list.setCurrentRow(next((i for i, row in enumerate(rows) if row["url"] == chosen_url), 0) if rows else -1)
        self.select(self.list.currentRow())

    def select(self, index):
        self.ack.setChecked(False)
        row = self.rows[index] if 0 <= index < len(self.rows) else None
        self.ack.setVisible(bool(row and row["needsReview"]))
        if row:
            parts = [row["title"], " · ".join(row["reasons"]),
                     "；".join(row["warnings"]), "网站标注：" + row["metadata"]]
            self.details.setText("\n".join(part for part in parts if part))
        else:
            self.details.setText("字幕库验证页可在“网站浏览”中处理；也可切换右上方备用来源。")
        self.update_actions()

    def update_actions(self):
        index = self.list.currentRow()
        valid = 0 <= index < len(self.rows)
        self.open_button.setEnabled(valid)
        self.choose_button.setEnabled(valid and (not self.rows[index]["needsReview"] or self.ack.isChecked()))

    def set_theme(self, theme, lighting='enhanced'):
        self.artwork.theme = theme;self.artwork.lighting = lighting;self.artwork.update()
        for button, symbol in ((self.search_button, 'search'), (self.open_button, 'external'), (self.choose_button, 'document')):
            button.setIcon(icon(symbol, '#ffffff' if button.objectName() == 'primary' else PALETTES[theme]['secondary']))
            button.setIconSize(QSize(20, 20))
