"""Native Qt interaction patterns, adapted from disclosure and table references."""
import ctypes
import os

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget


def motion_allowed():
    """Read the Windows preference; never change system settings."""
    if os.environ.get("YINGXU_REDUCED_MOTION") == "1":
        return False
    if os.name == "nt":
        enabled = ctypes.c_int()
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return bool(enabled.value)
        except (AttributeError, OSError):
            pass
    return False


class Disclosure(QWidget):
    """Interruptible 160ms height transition, with immediate reduced-motion path."""
    def __init__(self, content):
        super().__init__()
        self.expanded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)
        self.content = content
        self.setMaximumHeight(0)
        self.animation = QPropertyAnimation(self, b"maximumHeight", self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._settle)
        self.hide()

    def set_expanded(self, expanded):
        self.animation.stop()
        self.expanded = expanded
        current = self.height() if self.isVisible() else 0
        # Prevent focus from entering content while it is closed.
        self.content.setEnabled(expanded)
        if not motion_allowed():
            self._settle()
            return
        self.setMaximumHeight(current)
        self.show()
        self.layout().activate()
        target = self.layout().sizeHint().height() if expanded else 0
        self.animation.setStartValue(current)
        self.animation.setEndValue(target)
        self.animation.start()

    def _settle(self):
        self.setMaximumHeight(16777215 if self.expanded else 0)
        self.setVisible(self.expanded)


class MatchTable(QTableView):
    """Hover follows the complete record, including its status and score cells."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("hoveredRow", -1)

    def _hover(self, row):
        if row != self.property("hoveredRow"):
            self.setProperty("hoveredRow", row)
            self.viewport().update()

    def mouseMoveEvent(self, event):
        self._hover(self.indexAt(event.position().toPoint()).row())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover(-1)
        super().leaveEvent(event)
