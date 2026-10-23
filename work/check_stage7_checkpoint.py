"""Focused startup check for the two still-supported Web entries at checkpoint.

The production workspace draft is deliberately not the default entry yet.
No user folders or user settings are opened or changed.
"""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


def wait_for(check, message, timeout=20):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        if check():return
        QTest.qWait(30)
    raise AssertionError(message)


def js(page, source):
    values = []
    page.runJavaScript(source,lambda value:values.append(value))
    wait_for(lambda:bool(values),"JS callback timeout",5)
    return values[0]


if __name__ == '__main__':
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    results = []
    with tempfile.TemporaryDirectory(prefix='stage7-checkpoint-',dir=ROOT/'work'/'test-results') as directory:
        settings = QSettings(str(Path(directory)/'appearance.ini'),QSettings.Format.IniFormat)
        for preview in (False,True):
            window = WebWindow(preview=preview,appearance_settings=settings);window.show()
            try:
                wait_for(lambda:window._loaded,'Local page did not load')
                expression = "document.documentElement.dataset.ready === 'true'" if preview else "document.getElementById('connection')?.dataset.ready === 'true'"
                wait_for(lambda:js(window.page,expression),'Working entry did not become ready')
                if preview:
                    wait_for(lambda:js(window.page,"![...document.querySelectorAll('[data-theme-select]')].some(control=>control.disabled)"),'Appearance channel did not connect')
                    stats = json.loads(js(window.page,'JSON.stringify(yingxuPreview.stats())'))
                    assert stats['total'] == 12,stats
                    assert js(window.page,"document.getElementById('execute-button').disabled")
                    assert set(window.channel.registeredObjects()) == {'appearance'}
                else:
                    assert window.bridge.session_id
                    assert set(window.channel.registeredObjects()) == {'bridge'}
                    js(window.page,"document.getElementById('ping-input').value='检查点 中文';document.getElementById('ping-button').click();true")
                    wait_for(lambda:js(window.page,"document.getElementById('echo-output').textContent.includes('检查点 中文')"),'Python reply missing')
                assert not window.page.console_errors,window.page.console_errors
                results.append({'mode':'preview' if preview else 'foundation','ready':True,'consoleErrors':[]})
            finally:
                window.close();QTest.qWait(150);window.deleteLater();QTest.qWait(100)
    print(json.dumps({'result':'PASS','entries':results},ensure_ascii=False))
