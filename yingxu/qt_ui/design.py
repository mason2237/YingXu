"""Shared visual tokens and small, code-native line icons."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

INK = "#24272E"
MUTED = "#717784"
BLUE = "#4265D6"
LINE = "#E6E8ED"
FONT = "Microsoft YaHei UI"

SHAPES = {
    "folder": '<path d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11H3Z"/>',
    "scan": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M8 12h8"/>',
    "video": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 8 6 4-6 4Z"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    "open": '<path d="M13 3h8v8M21 3l-11 11M10 5H4v15h15v-6"/>',
    "panel": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    "brand": '<rect x="3" y="4" width="18" height="16" rx="4"/><path d="M7 11h10M7 15h6"/>',
    "down": '<path d="m6 9 6 6 6-6"/>',
    "up": '<path d="m6 15 6-6 6 6"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
}


def icon(name, color=MUTED, size=20):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round" '
           f'stroke-linecap="round">{SHAPES[name]}</svg>')
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def configure(app):
    app.setStyle("Fusion")
    app.setFont(QFont(FONT, 11))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F8F9FB"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(INK))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor(INK))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#EBF0FF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(INK))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


STYLE = """
QWidget { color: #24272E; }
QMainWindow, QWidget#Root { background: #F8F9FB; }
QLabel { background: transparent; }
QLabel[role="muted"] { color: #687181; font-size: 10.5pt; }
QLabel[role="brand"] { font-size: 19pt; font-weight: 600; }
QLabel[role="heading"] { font-size: 17pt; font-weight: 600; }
QLabel[role="section"] { font-size: 11pt; font-weight: 600; }
QLabel[role="eyebrow"] { color: #687181; font-size: 10.5pt; }
QLabel[role="folderTitle"] { color: #24272E; font-size: 11pt; font-weight: 600; }
QFrame#Header { background: white; border-bottom: 1px solid #E6E8ED; }
QFrame#Folder { background: #FAFBFD; border: 1px solid #E6E8ED; border-radius: 8px; }
QFrame#Inspector { background: white; border: 1px solid #E6E8ED; border-radius: 8px; }
QFrame#Destination { background: #F3F6FF; border-radius: 6px; }
QFrame#Rule { background: #E6E8ED; border: none; }
QFrame#Footer { border-top: 1px solid #E6E8ED; background: #FFFFFF; }
QPushButton {
    background: white; border: 1px solid #DDE1E8; border-radius: 6px;
    padding: 7px 14px; min-height: 22px; font-size: 10.5pt;
}
QPushButton:hover { background: #F1F3F7; border-color: #C9CFD9; }
QPushButton:pressed { background: #E7EBF2; }
QPushButton:focus { border: 1px solid #4265D6; }
QPushButton:disabled { color: #A1A7B2; background: #F5F6F8; border-color: #E9EBEF; }
QPushButton[role="primary"] { background: #4265D6; color: white; border-color: #4265D6; }
QPushButton[role="primary"]:hover { background: #3558C6; }
QPushButton[role="primary"]:pressed { background: #294BB9; }
QPushButton[role="primary"]:disabled { background: #D9E0F7; border-color: #D9E0F7; color: #7C8BB9; }
QPushButton[role="quiet"] { border-color: transparent; background: transparent; color: #606979; }
QPushButton[role="quiet"]:hover, QPushButton[role="quiet"]:checked { background: #EBEFF7; color: #4265D6; }
QCheckBox { spacing: 8px; color: #606979; font-size: 10.5pt; }
QCheckBox::indicator { width: 15px; height: 15px; }
QLineEdit, QComboBox {
    background: #FFFFFF; color: #24272E; border: 1px solid #DDE1E8;
    border-radius: 6px; padding: 7px 10px; min-height: 22px;
    selection-background-color: #DCE5FF;
}
QLineEdit:focus, QComboBox:focus { border-color: #4265D6; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #24272E; selection-background-color: #EDF2FF; }
QTableView { border: 1px solid #E6E8ED; border-radius: 8px; background: white; outline: none; }
QTreeWidget {
    border: 1px solid #E6E8ED; border-radius: 8px; background: white;
    outline: none; font-size: 10.5pt;
}
QTreeWidget::item { height: 30px; padding: 2px 6px; border-bottom: 1px solid #F1F2F5; }
QTreeWidget::item:hover { background: #F8FAFD; }
QTreeWidget::item:selected { background: #EDF2FF; color: #24272E; }
QHeaderView { background: #FAFBFD; border: none; }
QHeaderView::section {
    background: #FAFBFD; color: #717784; border: none;
    border-bottom: 1px solid #E6E8ED; padding: 12px; font-size: 10pt;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 3px 1px; }
QScrollBar::handle:vertical { background: #CDD2DC; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #ACB4C2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: transparent; width: 16px; }
QSplitter::handle:hover { background: #E8ECF4; }
QProgressBar { background: #E9EDF5; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #4265D6; border-radius: 2px; }
QTextEdit { border: none; background: transparent; selection-background-color: #DCE5FF; }
QToolTip { background: #FFFFFF; color: #24272E; border: 1px solid #DDE1E8; padding: 7px; }
"""
