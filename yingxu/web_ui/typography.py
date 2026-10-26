"""One bundled, OFL-licensed family for native controls and the offline Web UI."""
from PySide6.QtGui import QFont, QFontDatabase
from .resources import frontend_root

_family = None


def ui_font(size=11):
    global _family
    if _family is None:
        identifier = QFontDatabase.addApplicationFont(str(frontend_root()/'assets/fonts/NotoSansSC.ttf'))
        families = QFontDatabase.applicationFontFamilies(identifier) if identifier >= 0 else []
        _family = families[0] if families else 'Microsoft YaHei UI'
    font = QFont(_family, size)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
