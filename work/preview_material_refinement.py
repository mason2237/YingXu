"""One short real-window visual check for the 6.3a material revision."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from check_theme_preview import ROOT, ready, data, theme
from check_materials_preview import move
from check_web_foundation import wait_for
from PySide6.QtCore import QSettings, QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    with TemporaryDirectory(prefix='yingxu-refinement-') as directory:
        settings = QSettings(str(Path(directory) / 'appearance.ini'), QSettings.Format.IniFormat)
        settings.setValue('appearance/v1', '{"theme":"light"}')
        window = WebWindow(preview=True, appearance_settings=settings)
        window.show(); window.activateWindow()
        results = {}
        try:
            ready(window)
            wait_for(lambda: data(window, 'yingxuPreview.stats().effects.mist.mode') == 'webgl2', 'Vapor shader did not initialize')
            for value in ('light', 'dark'):
                if value == 'dark': theme(window, value)
                move(window, '[data-row-id="video-3"]', .63 if value == 'light' else .68, .48)
                first = data(window, '({frames:yingxuPreview.stats().effects.mist.frames,time:performance.now()})')
                # Normal Qt event loop, without QtTest's coarse wait polling.
                loop = QEventLoop(); QTimer.singleShot(1100, loop.quit); loop.exec()
                last = data(window, '({frames:yingxuPreview.stats().effects.mist.frames,time:performance.now()})')
                results[value] = round((last['frames'] - first['frames']) * 1000 / (last['time'] - first['time']), 1)
                assert window.grab().save(str(ROOT / 'outputs' / f'stage63a_refined_{value}.png'))
            assert not window.page.console_errors, window.page.console_errors
            print(json.dumps({'observedVaporFps': results, 'consoleErrors': window.page.console_errors}, ensure_ascii=False), flush=True)
        finally:
            window.close(); QTest.qWait(150)
