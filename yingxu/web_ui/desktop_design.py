"""Project-owned navy glass styling for the native discovery surface.

All artwork is vector UI drawing. No background loop, third-party artwork,
remote page injection, or business operations live in this module.
"""
from functools import lru_cache
from string import Template

from PySide6.QtCore import QEvent, QLineF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QStyledItemDelegate, QStyle, QWidget

from .typography import ui_font
from .resources import frontend_root

PALETTES = {
    "dark": dict(page="#0c1422", ink="#eef4ff", secondary="#c0cfe4", muted="#8ea5c5",
                 line="#293e5a", top="#1b2a40", bottom="#131e2e", hover="#243b5a",
                 input="#101b2b", accent="#2475ff", selected="#203e68", info="#142a48",
                 disabled="#121e2d", faint="#60738f", white="#ffffff"),
    "light": dict(page="#f3f6fb", ink="#1e304b", secondary="#425b7a", muted="#637d9d",
                  line="#cddbeb", top="#ffffff", bottom="#edf3fc", hover="#e4edfc",
                  input="#fbfdff", accent="#1769ed", selected="#deebff", info="#e8f1ff",
                  disabled="#eaf0f7", faint="#8d9fb7", white="#ffffff"),
}

# Same visual vocabulary as components/icons.js; paths are project-owned.
PATHS = {
    "brand": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 8h10M7 12h7M7 16h10"/>',
    "folder": '<path d="M3 7V5h7l2 3h9v11H3Z"/><path d="m3 11 3-3h15"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/>',
    "refresh": '<path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5M4 14a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/>',
    "history": '<path d="M3 11a9 9 0 1 1 2 7M3 5v6h6M12 7v5l3 2"/>',
    "settings": '<path d="m10 3-1 3-3 1-3-1-1 4 2 2-1 3 3 3 3-1 2 2 4-1 1-3 3-1 1-4-2-2V6l-3-2-3 1Z"/><circle cx="11" cy="11" r="3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/><circle cx="12" cy="12" r="10"/>',
    "next": '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    "back": '<path d="M19 12H5m6-6-6 6 6 6"/>',
    "external": '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "document": '<path d="M14 3H5v18h14V8Z M14 3v5h5M8 12h8m-8 4h6"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    "trash": '<path d="M3 6h18M9 3h6M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    "moon": '<path d="M20.5 13A9 9 0 0 1 11 3a9 9 0 1 0 9.5 10Z"/>',
    "chevron": '<path d="m7 9 5 5 5-5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
}


@lru_cache(maxsize=128)
def glyph(name, color="#d9e8ff", size=22):
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">'
           f'{PATHS.get(name, PATHS["document"])}</svg>')
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon(name, color="#d9e8ff"):
    return QIcon(glyph(name, color))


def painter_font(painter, pixels, weight=400):
    font = ui_font()
    font.setPixelSize(pixels)
    font.setWeight(QFont.Weight(weight))
    painter.setFont(font)


class AmbientSurface(QWidget):
    """A static shared backdrop, rendered only when Qt requests a repaint."""
    theme = "dark"
    lighting = "enhanced"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(PALETTES[self.theme]["page"]))
        dark = self.theme == "dark"
        strength = {'off': 0, 'soft': .5, 'enhanced': 1}.get(self.lighting, 1)
        if not strength: return
        # Flattened light pools reproduce a window reflected in dark glass.
        painter.scale(1, .62)
        for x, y, radius, alpha in ((.28, -.025, .64, 100 if dark else 30),
                                    (.77, 1.12, .60, 108 if dark else 28)):
            glow = QRadialGradient(self.width()*x, self.height()*y/.62, self.width()*radius)
            alpha = round(alpha*strength)
            glow.setColorAt(0, QColor(37, 112, 255, alpha))
            glow.setColorAt(1, QColor(37, 112, 255, 0))
            painter.fillRect(QRectF(0, 0, self.width(), self.height()/.62), glow)


class StatusLabel(QLabel):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.drawPixmap(12, (self.height()-18)//2, glyph('info', '#6ca7ff', 18))


class GuideStep(QWidget):
    lighting = 'enhanced'
    def __init__(self, number, title, description, parent=None):
        super().__init__(parent)
        self.number, self.title, self.description = number, title, description
        self.theme = "dark"
        self.setMinimumHeight(58)
        self.setAccessibleName(f"第{number}步，{title}，{description}")

    def event(self, event):
        if event.type() == QEvent.Type.DynamicPropertyChange:
            self.update()
        return super().event(event)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = PALETTES[self.theme]; active = bool(self.property("active"))
        circle = QRectF(8, (self.height()-40)/2, 40, 40)
        if active and self.lighting != 'off':
            glow = QRadialGradient(circle.center(), 28)
            glow.setColorAt(0, QColor(52, 128, 255, 72 if self.lighting == 'enhanced' else 32))
            glow.setColorAt(1, QColor(52, 128, 255, 0))
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(glow);p.drawEllipse(circle.adjusted(-8, -8, 8, 8))
        gradient = QLinearGradient(circle.topLeft(), circle.bottomRight())
        gradient.setColorAt(0, QColor("#388bff" if active else colors["top"]))
        gradient.setColorAt(1, QColor("#1461ed" if active else colors["bottom"]))
        p.setPen(QPen(QColor("#548fff" if active else colors["line"]), 1))
        p.setBrush(gradient); p.drawEllipse(circle)
        painter_font(p, 20, 600); p.setPen(QColor("#ffffff" if active else colors["muted"]))
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(self.number))
        p.setPen(QColor(colors["ink"] if active else colors["secondary"]))
        painter_font(p, 15, 600 if active else 500)
        text = p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, self.width()-66)
        p.drawText(QRectF(62, self.height()/2-21, self.width()-66, 25), text)
        p.setPen(QColor(colors["muted"])); painter_font(p, 12)
        text = p.fontMetrics().elidedText(self.description, Qt.TextElideMode.ElideRight, self.width()-66)
        p.drawText(QRectF(62, self.height()/2+3, self.width()-66, 22), text)


class EmptyArtwork(QWidget):
    theme = "dark"
    lighting = 'enhanced'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 100)

    def paintEvent(self, event):
        p = QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(60, 50, 44)
        glow.setColorAt(0, QColor(64, 142, 255, {'off': 10, 'soft': 32, 'enhanced': 70}.get(self.lighting, 32)))
        glow.setColorAt(1, QColor(37, 117, 255, 4))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(glow);p.drawEllipse(QRectF(16, 6, 88, 88))
        p.drawPixmap(38, 26, glyph("folder", "#3e89ff", 44))
        p.drawPixmap(61, 50, glyph("search", "#66a2ff", 24))
        p.setPen(QPen(QColor("#72a6ff"), 1.3))
        for x, y in ((10, 31), (110, 58)):
            p.drawLine(x-2, y, x+2, y);p.drawLine(x, y-2, x, y+2)


class QueueDelegate(QStyledItemDelegate):
    theme = "dark"

    def sizeHint(self, option, index):
        return QSize(230, 76)

    def paint(self, painter, option, index):
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = PALETTES[self.theme]
        rect = QRectF(option.rect).adjusted(5, 3, -5, -3)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(QColor(colors["line"]), 1));painter.setBrush(QColor(colors["selected"]))
            painter.drawRoundedRect(rect, 8, 8)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(colors["hover"]))
            painter.drawRoundedRect(rect, 8, 8)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor("#4d90ff"), 1))
            painter.drawRoundedRect(rect, 8, 8)
        box = QRectF(rect.left()+11, rect.center().y()-8, 17, 17)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
        painter.setPen(QPen(QColor("#498fff" if checked else colors["muted"]), 1))
        painter.setBrush(QColor("#2475ff" if checked else colors["input"]))
        painter.drawRoundedRect(box, 4, 4)
        if checked:
            painter.setPen(QPen(QColor("#ffffff"), 1.7))
            painter.drawLine(QLineF(box.left()+4, box.top()+8, box.left()+7, box.top()+11))
            painter.drawLine(QLineF(box.left()+7, box.top()+11, box.left()+13, box.top()+5))
        painter.drawPixmap(int(rect.left()+40), int(rect.center().y()-11), glyph("folder", colors["muted"], 23))
        original = str(index.data(Qt.ItemDataRole.DisplayRole) or "").splitlines()
        title = str(index.data(Qt.ItemDataRole.UserRole+1) or (original[0] if original else ""))
        x = rect.left()+75;width = int(rect.width()-86)
        episode = str(index.data(Qt.ItemDataRole.UserRole+2) or '')
        title_width = max(12, width-(62 if episode else 0))
        painter.setPen(QColor(colors["ink"]));painter_font(painter, 15, 500)
        painter.drawText(QRectF(x, rect.center().y()-22, title_width, 27),
                         painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, title_width))
        if episode:
            painter.setPen(QColor(colors['muted']));painter_font(painter, 11, 500)
            painter.drawText(QRectF(x+width-58, rect.center().y()-20, 58, 25), Qt.AlignmentFlag.AlignRight, episode)
        painter.setPen(QColor(colors["muted"]));painter_font(painter, 12)
        subtitle = " · ".join(original)
        painter.drawText(QRectF(x, rect.center().y()+5, width, 24),
                         painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideMiddle, width))
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if not option.state & QStyle.StateFlag.State_Enabled:
            return False
        keyboard = event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space
        clicked = (event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton
                   and QRectF(option.rect.left()+12, option.rect.center().y()-13, 30, 28).contains(event.position()))
        if keyboard or clicked:
            checked = index.data(Qt.ItemDataRole.CheckStateRole) in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            return model.setData(index, (Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked).value, Qt.ItemDataRole.CheckStateRole)
        return False


def stylesheet(theme, lighting='enhanced'):
    assets = frontend_root() / 'assets/icons'
    values = {**PALETTES[theme], 'check_svg': (assets / 'check.svg').as_posix(),
              'chevron_svg': (assets / 'chevron.svg').as_posix()}
    if lighting == 'enhanced' and theme == 'dark':
        values.update(top='rgba(36, 55, 79, 220)', bottom='rgba(15, 28, 46, 233)', line='#3c5e85')
    elif lighting == 'enhanced':
        values.update(top='rgba(255, 255, 255, 245)', bottom='rgba(226, 238, 255, 220)', line='#c3d8f1')
    values['rim'] = ('rgba(157, 202, 255, 112)' if theme == 'dark' else '#ffffff') if lighting == 'enhanced' else values['line']
    return Template("""
      QWidget { font-family: 'Noto Sans SC'; font-size: 15px; font-weight: 400; color: $ink; background: transparent; }
      QMainWindow { background: $page; }
      QWidget#appChrome { border-bottom: 1px solid $line; }
      QLabel#brandName { font-size: 23px; font-weight: 700; }
      QLabel#brandDescription { color: $muted; border-left: 1px solid $line; padding-left: 18px; }
      QLabel#heading { font-size: 36px; font-weight: 700; }
      QLabel#subtitle { color: $secondary; font-size: 15px; }
      QLabel#muted, QLabel#section { color: $muted; font-size: 13px; }
      QLabel#section { font-weight: 500; }
      QLabel#panelTitle { color: $secondary; font-size: 14px; font-weight: 600; }
      QLabel#emptyTitle { font-size: 23px; font-weight: 650; }
      QLabel#emptyDescription { color: $muted; font-size: 14px; }
      QFrame#guideStrip, QFrame#queuePanel, QFrame#resultsPanel {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 $top,stop:1 $bottom);
        border: 1px solid $line; border-radius: 12px;
        border-top-color: $rim;
      }
      QFrame#queueHeading { border-bottom: 1px solid $line; }
      QFrame#stepConnector { background: $line; border: 0; max-height: 1px; }
      QLabel#status { padding: 9px 13px 9px 38px; background: $info; color: $secondary; border: 1px solid $line; border-radius: 9px; font-size: 13px; }
      QLabel#guideHint { color: $muted; font-size: 12px; }
      QLineEdit, QComboBox {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 $top,stop:1 $input);
        border: 1px solid $line; border-radius: 9px; padding: 9px 12px; selection-background-color: $accent;
      }
      QLineEdit { font-size: 17px; padding: 11px 15px; }
      QLineEdit:focus, QComboBox:focus { border: 1px solid #448fff; }
      QComboBox { padding-right: 25px; min-height: 22px; }
      QComboBox::drop-down { border: 0; width: 22px; }
      QComboBox::down-arrow { image: url('$chevron_svg'); width: 15px; height: 15px; }
      QComboBox QAbstractItemView { background: $input; color: $ink; selection-background-color: $selected; border: 1px solid $line; outline: none; }
      QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 $top,stop:1 $bottom);
        color: $ink; border: 1px solid $line; border-radius: 9px; padding: 10px 15px;
        border-top-color: $rim;
        font-weight: 500; min-height: 20px;
      }
      QPushButton:hover { background: $hover; border-color: #4574ab; }
      QPushButton:pressed { background: $selected; border-color: #528eed; }
      QPushButton:focus { border-color: #548fff; }
      QPushButton:disabled { background: $disabled; color: $faint; border-color: $line; }
      QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3188ff,stop:1 #1761ec); color: white; border-color: #5194ff; }
      QPushButton#primary:hover { background: #3586ff; border-color: #7bb3ff; }
      QPushButton#primary:pressed { background: #1358d8; }
      QPushButton#primary:disabled { background: $selected; color: $faint; border-color: $line; }
      QPushButton#quiet { background: transparent; border-color: transparent; padding: 7px; color: $muted; }
      QPushButton#quiet:hover { color: $ink; background: $hover; }
      QTabWidget { border: 0; }
      QTabWidget::pane { border: 0; background: transparent; }
      QTabBar { background: transparent; }
      QTabBar::tab { padding: 12px 18px; color: $muted; border-bottom: 2px solid transparent; margin-right: 4px; }
      QTabBar::tab:selected { color: $ink; background: $selected; border-bottom-color: #3785ff; border-top-left-radius: 8px; border-top-right-radius: 8px; }
      QTabBar::tab:hover { color: $ink; }
      QListWidget { border: none; background: transparent; outline: none; }
      QListWidget#resultsList::item { padding: 13px 14px; margin: 3px 0; border: 1px solid $line; border-radius: 9px; color: $secondary; }
      QListWidget#resultsList::item:selected { background: $selected; border-color: #4388ec; color: $ink; }
      QListWidget#resultsList::item:hover { background: $hover; }
      QListWidget#downloadList { background: $input; border: 1px solid $line; border-radius: 9px; padding: 5px; }
      QListWidget#downloadList::item { padding: 7px; color: $secondary; }
      QListWidget#downloadList::item:selected { background: $selected; color: $ink; border-radius: 5px; }
      QCheckBox { spacing: 9px; }
      QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid $muted; border-radius: 4px; background: $input; }
      QCheckBox::indicator:checked { background: $accent; border-color: #5596ff; image: url('$check_svg'); }
      QCheckBox::indicator:disabled { border-color: $faint; background: $disabled; }
      QProgressBar { background: $input; border: 0; border-radius: 2px; }
      QProgressBar::chunk { background: #3188ff; border-radius: 2px; }
      QSplitter::handle { background: transparent; width: 12px; }
      QScrollBar:vertical { background: transparent; width: 7px; margin: 3px 0; }
      QScrollBar::handle:vertical { background: $line; min-height: 28px; border-radius: 3px; }
      QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
      QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
      QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
      QFrame#resultActions { border-top: 1px solid $line; }
      QToolTip { background: $top; border: 1px solid $line; color: $ink; padding: 7px; }
      QMainWindow[compact="true"] QLabel#heading { font-size: 28px; }
      QMainWindow[compact="true"] QLabel#emptyTitle { font-size: 20px; }
      QMainWindow[compact="true"] QPushButton { padding: 8px 12px; font-size: 14px; }
      QMainWindow[compact="true"] QLineEdit { padding: 9px 12px; font-size: 16px; }
    """).substitute(values)
