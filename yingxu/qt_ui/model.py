"""Read-only Qt adapter; a video can later contain multiple subtitle matches."""
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, QSize, Qt, QSortFilterProxyModel
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from ..core import extract_episode
from ..review import ReviewPlan
from .design import BLUE, FONT, INK, MUTED, icon


@dataclass(frozen=True)
class SubtitleMatch:
    source: Path
    target: Path
    score: float
    state: str
    manual: bool = False
    confirmed: bool = False


@dataclass(frozen=True)
class VideoRecord:
    video: Path
    subtitles: tuple[SubtitleMatch, ...]
    review_state: str = ""
    skipped: bool = False

    @property
    def state(self):
        return self.review_state or (self.subtitles[0].state if self.subtitles else "未匹配")

    @classmethod
    def from_plan(cls, row):
        matches = ()
        if row["subtitle"]:
            matches = (SubtitleMatch(row["subtitle"], row["target"], row["score"], row["status"]),)
        return cls(row["video"], matches)

    @classmethod
    def from_review(cls, plan: ReviewPlan, index: int):
        row = plan.rows[index]
        matches = tuple(SubtitleMatch(m.source, m.target, m.score, plan.state(index), m.manual, m.confirmed)
                        for m in row.matches)
        return cls(row.video, matches, plan.state(index), row.skipped)


STATUS = {
    "待整理": ("待整理", "#347A63", "#EDF6F1"),
    "已符合": ("无需改名", "#657083", "#F0F2F5"),
    "需确认": ("需确认", "#976627", "#FBF3E5"),
    "未匹配": ("未匹配", "#976627", "#FBF3E5"),
    "已跳过": ("已跳过", "#657083", "#F0F2F5"),
}


def match_reason(record, selected=None):
    if record.skipped:
        return "此项已跳过。可随时恢复审阅；当前预览不会对文件执行操作。"
    if not record.subtitles:
        return "没有找到达到匹配阈值的字幕。请检查字幕是否位于扫描范围内。"
    match = selected or record.subtitles[0]
    if match.manual:
        return "人工选择的字幕；匹配评分仅供参考，请检查集数、语言和最终名称。"
    video_ep = extract_episode(record.video.stem)
    sub_ep = extract_episode(match.source.stem)
    reasons = []
    if video_ep and sub_ep and video_ep[1] == sub_ep[1]:
        reasons.append("集数一致")
        if video_ep[0] is not None and video_ep[0] == sub_ep[0]:
            reasons.append("季数一致")
    if record.video.parent == match.source.parent:
        reasons.append("位于同一目录")
    reasons.append("按文件名相似程度评分")
    return " · ".join(reasons) + "。评分用于辅助检查，不代表准确概率。"


class MatchModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.records = []

    def set_plan(self, plan):
        self.beginResetModel()
        self.records = [VideoRecord.from_plan(row) for row in plan]
        self.endResetModel()

    def set_review(self, plan: ReviewPlan):
        self.beginResetModel()
        self.records = [VideoRecord.from_review(plan, index) for index in range(len(plan.rows))]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ("视频 / 对应字幕", "匹配评分", "状态")[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        record = self.records[index.row()]
        match = record.subtitles[0] if record.subtitles else None
        if role == Qt.ItemDataRole.UserRole:
            return record
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return (
                record.video.name + "\n" + (match.source.name if match else "尚未匹配字幕"),
                f"{round(match.score * 100)} / 100" if match else "—",
                STATUS[record.state][0],
            )[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            if index.column() == 1:
                return match_reason(record)
            return f"视频：{record.video}\n字幕：{match.source if match else '未匹配'}\n目标：{match.target if match else '—'}"


class MatchDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_icon = icon("video", "#8992A4", 22)

    def sizeHint(self, option, index):
        return QSize(200, 76)

    def paint(self, painter, option, index):
        record = index.data(Qt.ItemDataRole.UserRole)
        match = record.subtitles[0] if record.subtitles else None
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = self.parent().property("hoveredRow") == index.row()
        painter.save()
        painter.fillRect(rect, QColor("#EDF2FF" if selected else "#F8FAFD" if hovered else "#FFFFFF"))
        painter.setPen(QColor("#F0F1F4"))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if index.column() == 0:
            if selected:
                painter.fillRect(QRect(rect.x(), rect.y() + 15, 3, rect.height() - 30), QColor(BLUE))
            self.video_icon.paint(painter, QRect(rect.x() + 17, rect.y() + 25, 22, 22))
            text_rect = rect.adjusted(53, 0, -16, 0)
            painter.setFont(QFont(FONT, 12, QFont.Weight.Medium))
            painter.setPen(QColor(INK))
            text = painter.fontMetrics().elidedText(record.video.name, Qt.TextElideMode.ElideMiddle, text_rect.width())
            painter.drawText(QRect(text_rect.x(), rect.y() + 13, text_rect.width(), 25),
                             Qt.AlignmentFlag.AlignVCenter, text)
            subtitle_font = QFont(FONT, 10)
            subtitle_font.setPointSizeF(10.5)
            painter.setFont(subtitle_font)
            painter.setPen(QColor(MUTED))
            subtitle = match.source.name if match else "尚未匹配字幕"
            if len(record.subtitles) > 1:
                subtitle += f"  ·  共 {len(record.subtitles)} 份"
            text = painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideMiddle, text_rect.width())
            painter.drawText(QRect(text_rect.x(), rect.y() + 40, text_rect.width(), 23),
                             Qt.AlignmentFlag.AlignVCenter, text)
        elif index.column() == 1:
            painter.setFont(QFont(FONT, 11))
            painter.setPen(QColor(INK if match else MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             f"{round(match.score * 100)}" if match else "—")
        else:
            label, foreground, background = STATUS[record.state]
            badge = QRect(rect.x() + (rect.width() - 84) // 2, rect.y() + 24, 84, 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(badge, 5, 5)
            painter.setBrush(QColor(foreground))
            painter.drawEllipse(badge.x() + 9, badge.y() + 11, 5, 5)
            painter.setPen(QColor(foreground))
            painter.setFont(QFont(FONT, 10))
            painter.drawText(badge.adjusted(12, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, label)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(QColor("#9AAEEB"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        painter.restore()


class MatchProxy(QSortFilterProxyModel):
    """Filter and sort records while keeping source identity independent of row order."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self.state_filter = "全部"

    def set_query(self, value):
        self.query = value.strip().casefold()
        self.invalidateFilter()

    def set_state_filter(self, value):
        self.state_filter = value
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        record = self.sourceModel().records[row]
        if self.state_filter != "全部" and record.state != self.state_filter:
            return False
        if not self.query:
            return True
        fields = [record.video.name]
        for match in record.subtitles:
            fields.extend((match.source.name, match.target.name))
        return any(self.query in value.casefold() for value in fields)

    def lessThan(self, left, right):
        first = self.sourceModel().records[left.row()]
        second = self.sourceModel().records[right.row()]
        column = left.column()
        if column == 1:
            a = max((m.score for m in first.subtitles), default=-1)
            b = max((m.score for m in second.subtitles), default=-1)
        elif column == 2:
            order = {"需确认": 0, "未匹配": 1, "待整理": 2, "已符合": 3, "已跳过": 4}
            a, b = order[first.state], order[second.state]
        else:
            a, b = first.video.name.casefold(), second.video.name.casefold()
        return a < b if a != b else str(first.video).casefold() < str(second.video).casefold()
