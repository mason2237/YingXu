"""Capture actual Qt window frames for a short, reproducible optics recording."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_lens_preview import js, center
from check_web_foundation import wait_for
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


if __name__ == '__main__':
    folder = ROOT / 'outputs/stage61_motion_frames'
    folder.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    window = WebWindow(effects=True); window.show()
    frames = []
    def grab(delay=65):
        QTest.qWait(delay)
        path = folder / f'{len(frames):03}.png'
        assert window.grab().save(str(path))
        frames.append({'path': path.name, 'time': time.monotonic()})
    try:
        wait_for(lambda: window._loaded and js(window, "document.documentElement.dataset.ready==='true'"), 'Effects page failed')
        QTest.qWait(1000)
        for scene in ['aurora', 'sunset', 'ocean', 'grid', 'workbench']:
            js(window, f"document.getElementById('lab-scene').value='{scene}';document.getElementById('lab-scene').dispatchEvent(new Event('change',{{bubbles:true}}));true")
            QTest.qWait(230)
            expected = 'grid' if scene == 'workbench' else scene
            assert js(window, "document.getElementById('original-stage').dataset.scene") == expected
            if scene == 'ocean':
                assert window.grab().save(str(ROOT / 'outputs/stage61_ocean.png'))
        for _ in range(6): grab()
        point = center(window, '#enhanced-stage .lg-button')
        QTest.mousePress(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=point)
        for i in range(9):
            QTest.mouseMove(window.view.focusProxy(), point + QPoint(i * 3, i), delay=30); grab(45)
        QTest.mouseRelease(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=point + QPoint(24, 8))
        for _ in range(8): grab()
        js(window, "document.getElementById('gallery').scrollIntoView({behavior:'instant'});document.querySelector('button[data-component=\"drop-select\"]').click();true")
        QTest.qWait(700)
        for _ in range(5): grab()
        point = center(window, '.lg-drop-selector')
        target = center(window, '.lg-drop-option:last-child')
        QTest.mousePress(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=point)
        for i in range(1, 13):
            position = point + (target - point) * (i / 12)
            QTest.mouseMove(window.view.focusProxy(), position, delay=35); grab(40)
        QTest.mouseRelease(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=target)
        for _ in range(14): grab()
        assert js(window, 'globalThis.yingxuEffectsLab.stats().value') == 'both'
        assert not window.page.console_errors, window.page.console_errors
        (folder / 'frames.json').write_text(json.dumps(frames, indent=2), encoding='utf-8')
        print(json.dumps({'frames': len(frames), 'folder': str(folder), 'source': 'actual WebEngine window grabs; native Qt input; no CUA'}, ensure_ascii=False))
    finally:
        window.close(); QTest.qWait(120)
