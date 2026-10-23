"""Record the actual WebEngine iris; temporary appearance settings, no CUA."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from check_theme_preview import ready, select, js, ROOT
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    output = ROOT / 'outputs/stage62_motion_frames'
    output.mkdir(exist_ok=True)
    frames, images = [], []
    with TemporaryDirectory(prefix='yingxu-theme-record-') as directory:
        settings = QSettings(str(Path(directory) / 'appearance.ini'), QSettings.Format.IniFormat)
        settings.setValue('appearance/v1', '{"theme":"light"}')
        window = WebWindow(preview=True, appearance_settings=settings)
        window.show()
        try:
            ready(window); QTest.qWait(1000)
            started = perf_counter()
            def grab():
                name = f'{len(frames):03d}.png'
                stamp = (perf_counter() - started) * 1000
                images.append(window.grab())
                frames.append({'file': name, 'atMs': round(stamp, 2)})
            grab(); QTest.qWait(450)
            for theme in ('dark', 'light', 'dark'):
                select(window, '#theme-quick', theme)
                for _ in range(13): grab(); QTest.qWait(18)
                QTest.qWait(450)
            grab()
            assert js(window, "document.documentElement.dataset.themeTransition==='iris'")
            assert not window.page.console_errors, window.page.console_errors
            for record, image in zip(frames, images):
                assert image.save(str(output / record['file']))
            (output / 'frames.json').write_text(json.dumps(frames), encoding='utf-8')
            print(json.dumps({'frames': len(frames), 'elapsedMs': round((perf_counter()-started)*1000), 'source':'real Qt/WebEngine captures'}))
        finally:
            window.close(); QTest.qWait(150)
