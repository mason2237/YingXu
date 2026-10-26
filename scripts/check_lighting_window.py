"""Isolated source window for the shared source/EXE visual smoke checker.

Use: node work/check_packaged_release.mjs scripts/check_lighting_window.py
The parent checker supplies a temporary YINGXU_DATA_DIR and loopback inspector.
No production options or filesystem bridge capabilities are added.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore
from yingxu.web_ui.window import WebWindow


if __name__ == '__main__':
    folder = Path(os.environ['YINGXU_DATA_DIR'])
    app = QApplication(sys.argv)
    app.setApplicationName('YingXu Lighting Check')
    app.setStyle('Fusion')
    settings = QSettings(str(folder/'appearance.ini'), QSettings.Format.IniFormat)
    settings.setValue('appearance/v1', '{"theme":"dark","lighting":"enhanced"}')
    window = WebWindow( appearance_settings=settings, history=HistoryStore(folder/'history.jsonl'))
    window.show()
    sys.exit(app.exec())
