"""Preview, results and local history dialogs for the confirmed workflow."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextOption
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from ..operations import BatchResult, HistoryStore, PlanSnapshot, export_result


ACTION_LABEL = {
    "rename": "将整理", "unchanged": "无需变更", "skipped": "已跳过",
    "unmatched": "未匹配", "pending": "需先确认",
}
RESULT_LABEL = {
    "success": "成功", "error": "失败", "blocked": "已阻止",
    "cancelled": "未执行", "skipped": "跳过", "unmatched": "未匹配",
    "unchanged": "无需变更",
}


def _label(text, role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role:
        widget.setProperty("role", role)
    return widget


def _tree():
    tree = QTreeWidget()
    tree.setColumnCount(3)
    tree.setHeaderLabels(("视频 / 源字幕", "整理后名称", "状态"))
    tree.setRootIsDecorated(True)
    tree.setUniformRowHeights(True)
    tree.setIndentation(18)
    tree.setAlternatingRowColors(False)
    tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    tree.setColumnWidth(2, 110)
    return tree


def _detail():
    detail = QTextEdit()
    detail.setReadOnly(True)
    detail.setFixedHeight(110)
    detail.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
    detail.setAccessibleName("完整文件变更详情")
    return detail


def _fill_tree(tree, entries, status_labels):
    parents = {}
    for entry in entries:
        video = entry.video
        if video not in parents:
            parent = QTreeWidgetItem((video.name, "", ""))
            parent.setToolTip(0, str(video))
            tree.addTopLevelItem(parent)
            parents[video] = parent
        title = entry.source.name if entry.source else "没有关联字幕"
        target = entry.target.name if entry.target else "—"
        status = status_labels[entry.action if hasattr(entry, "action") else entry.status]
        child = QTreeWidgetItem((title, target, status))
        child.setToolTip(0, str(entry.source or video))
        child.setToolTip(1, str(entry.target or "—"))
        child.setData(0, Qt.ItemDataRole.UserRole, entry)
        parents[video].addChild(child)
    tree.expandAll()
    if tree.topLevelItemCount() and tree.topLevelItem(0).childCount():
        tree.setCurrentItem(tree.topLevelItem(0).child(0))


class PreviewDialog(QDialog):
    def __init__(self, snapshot: PlanSnapshot, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.setWindowTitle("确认字幕变更 · 映序")
        self.setMinimumSize(740, 500)
        self.resize(900, 610)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(14)
        box.addWidget(_label("核对整理计划", "heading"))
        counts = Counter(item.action for item in snapshot.items)
        box.addWidget(_label(
            f"将整理 {counts['rename']} 份字幕  ·  无需变更 {counts['unchanged']} 份  ·  "
            f"跳过/未匹配 {counts['skipped'] + counts['unmatched']} 项  ·  待确认 {counts['pending']} 项",
            "muted"))
        note = ("仍有未确认的匹配。请关闭预览，在详情中确认或跳过后再整理。" if snapshot.pending_count else
                "以下源文件与目标名称是本次固定计划；执行前会再次检查文件状态，已有目标文件不会被覆盖。")
        self.note = _label(note, "muted")
        self.note.setWordWrap(True)
        box.addWidget(self.note)
        self.tree = _tree()
        _fill_tree(self.tree, snapshot.items, ACTION_LABEL)
        box.addWidget(self.tree, 1)
        self.detail = _detail()
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        box.addWidget(self.detail)
        self._selection_changed()
        self.acknowledge = QCheckBox("我已核对以上文件和目标名称")
        box.addWidget(self.acknowledge)
        actions = QHBoxLayout()
        actions.addStretch()
        close = QPushButton("返回审阅")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        self.execute = QPushButton("确认并整理")
        self.execute.setProperty("role", "primary")
        self.execute.setEnabled(False)
        self.execute.clicked.connect(self.accept)
        actions.addWidget(self.execute)
        self.acknowledge.toggled.connect(
            lambda checked: self.execute.setEnabled(checked and bool(snapshot.changes) and not snapshot.pending_count))
        box.addLayout(actions)

    def _selection_changed(self):
        selected = self.tree.selectedItems()
        item = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        if item is None:
            self.detail.setPlainText("选择一条字幕查看完整文件位置。")
            return
        note = ACTION_LABEL[item.action]
        if item.action == "rename":
            if item.source.parent != item.target.parent:
                note += " · 移动至视频目录"
            if re.match(re.escape(item.video.stem) + r"_\d+(?:\.|$)", item.target.stem):
                note += " · 使用编号避开重名"
        self.detail.setPlainText(f"视频：{item.video}\n原字幕：{item.source or '—'}\n目标：{item.target or '—'}\n{note}")


class ResultDialog(QDialog):
    def __init__(self, result: BatchResult, history: HistoryStore, parent=None):
        super().__init__(parent)
        self.result = result
        self.history = history
        self.setWindowTitle("整理结果 · 映序")
        self.setMinimumSize(740, 500)
        self.resize(900, 610)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(14)
        box.addWidget(_label("本次整理结果", "heading"))
        counts = Counter(item.status for item in result.items)
        box.addWidget(_label(
            f"成功 {counts['success']} 份  ·  无需变更 {counts['unchanged']} 份  ·  "
            f"跳过/未匹配 {counts['skipped'] + counts['unmatched']} 项  ·  "
            f"异常 {counts['error'] + counts['blocked']} 项  ·  未执行 {counts['cancelled']} 项",
            "muted"))
        if result.issue:
            warning = _label("计划已失效，请重新扫描：" + result.issue, "muted")
            warning.setWordWrap(True)
            box.addWidget(warning)
        if result.history_error:
            warning = _label("本地记录写入失败，请导出本次结果：" + result.history_error, "muted")
            warning.setWordWrap(True)
            box.addWidget(warning)
        self.tree = _tree()
        # Result entries use a status field instead of a preview action.
        _fill_tree(self.tree, result.items, RESULT_LABEL)
        box.addWidget(self.tree, 1)
        self.detail = _detail()
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        box.addWidget(self.detail)
        self._selection_changed()
        actions = QHBoxLayout()
        location = QPushButton("打开记录目录")
        location.clicked.connect(self._open_history)
        actions.addWidget(location)
        actions.addStretch()
        export = QPushButton("导出结果…")
        export.clicked.connect(self._export)
        actions.addWidget(export)
        close = QPushButton("完成")
        close.setProperty("role", "primary")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        box.addLayout(actions)

    def _selection_changed(self):
        selected = self.tree.selectedItems()
        item = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        if item is None:
            self.detail.setPlainText("选择一条结果查看完整文件位置。")
            return
        self.detail.setPlainText(
            f"视频：{item.video}\n原字幕：{item.source or '—'}\n目标：{item.target or '—'}\n"
            f"结果：{RESULT_LABEL[item.status]}" + (f" · {item.error}" if item.error else ""))

    def _open_history(self):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.history.path.parent))):
            QMessageBox.warning(self, "无法打开目录", str(self.history.path.parent))

    def _export(self):
        suggested = f"映序-整理结果-{self.result.run_id[:8]}.json"
        path, _ = QFileDialog.getSaveFileName(self, "导出整理结果", suggested, "JSON 文件 (*.json)")
        if not path:
            return
        try:
            export_result(self.result, Path(path))
        except FileExistsError:
            QMessageBox.warning(self, "文件已存在", "请选择一个新的文件名，已有文件不会被覆盖。")
        except OSError as error:
            QMessageBox.warning(self, "导出失败", str(error))
        else:
            QMessageBox.information(self, "已导出", f"结果已保存到：\n{path}")


class HistoryDialog(QDialog):
    def __init__(self, history: HistoryStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地操作记录 · 映序")
        self.setMinimumSize(740, 480)
        self.resize(860, 590)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(14)
        box.addWidget(_label("最近的整理记录", "heading"))
        box.addWidget(_label("记录只保存在此电脑。显示最近 30 次整理；每份字幕都有单独结果。", "muted"))
        self.tree = _tree()
        try:
            records = history.recent()
        except OSError as error:
            records = []
            box.addWidget(_label(f"读取记录失败：{error}", "muted"))
        for record in records:
            counts = Counter(item.get("status") for item in record.get("items", []))
            try:
                title = datetime.fromisoformat(record["started_at"]).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except (KeyError, ValueError):
                title = "未知时间"
            parent_item = QTreeWidgetItem((title, f"成功 {counts['success']} · 异常 {counts['error'] + counts['blocked']}", ""))
            self.tree.addTopLevelItem(parent_item)
            for item in record.get("items", []):
                child = QTreeWidgetItem((Path(item.get("source") or item.get("video", "")).name,
                                         Path(item.get("target") or "").name or "—",
                                         RESULT_LABEL.get(item.get("status"), "未知")))
                child.setData(0, Qt.ItemDataRole.UserRole, item)
                parent_item.addChild(child)
        self.tree.expandAll()
        box.addWidget(self.tree, 1)
        self.detail = _detail()
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        box.addWidget(self.detail)
        self._selection_changed()
        actions = QHBoxLayout()
        actions.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        box.addLayout(actions)

    def _selection_changed(self):
        selected = self.tree.selectedItems()
        item = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.detail.setPlainText(
            f"视频：{item.get('video')}\n原字幕：{item.get('source') or '—'}\n目标：{item.get('target') or '—'}\n"
            f"结果：{RESULT_LABEL.get(item.get('status'), '未知')} · {item.get('error') or '无错误'}"
            if item else "选择一条字幕记录查看完整路径与结果。")
