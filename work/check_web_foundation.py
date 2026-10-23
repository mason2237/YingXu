"""Real WebEngine integration check. All diagnostic files are temporary fixtures."""
import json
from pathlib import Path
import sys
import time
from threading import Event
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yingxu.web_ui.resources import APP_URL, register_scheme
register_scheme()
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow
from yingxu.web_ui.workers import inspect_sample


def wait_for(check, message, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        QTest.qWait(25)
    raise AssertionError(message)


def javascript(page, source):
    values = []
    page.runJavaScript(source, lambda value: values.append(value))
    wait_for(lambda: bool(values), "JavaScript callback timed out", 5)
    return values[0]


def dom_ready(window):
    return javascript(window.page, "document.getElementById('connection')?.dataset.ready === 'true'")


def capture(window, name):
    QTest.qWait(120)
    pixmap = window.grab()
    assert not pixmap.isNull()
    assert pixmap.save(str(ROOT / "outputs" / f"stage5_{name}.png"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind, value, tb: (errors.append(str(value)), sys.__excepthook__(kind, value, tb))
    window = WebWindow()
    window.show()
    try:
        wait_for(lambda: window._loaded, "Local HTML did not load")
        wait_for(lambda: dom_ready(window), "QWebChannel handshake failed")
        capture(window, "initial")
        first_session = window.bridge.session_id
        assert window.profile.isOffTheRecord()
        assert not window.page.console_errors, window.page.console_errors
        javascript(window.page, "document.getElementById('ping-input').value = '中文路径 & <测试> 😀'; document.getElementById('ping-button').click(); true")
        wait_for(lambda: javascript(window.page, "document.getElementById('echo-output').dataset.received === 'true'"), "Python reply did not reach DOM")
        assert "中文路径 & <测试> 😀" in javascript(window.page, "document.getElementById('echo-output').textContent")
        assert javascript(window.page, "document.getElementById('echo-output').children.length") == 0
        javascript(window.page, "document.getElementById('sample-button').click(); true")
        wait_for(lambda: window.bridge.service.job and window.bridge.service.job["status"] == "completed" and window.bridge.service.worker is None, "Core fixture did not complete")
        wait_for(lambda: javascript(window.page, "document.querySelectorAll('#sample-rows tr').length === 3"), "Python status/result signal not rendered")
        assert window.bridge.service.job["result"]["unchanged"]
        assert javascript(window.page, "Number(document.getElementById('connection').dataset.sequence)") >= 2
        assert not window.page.console_errors, window.page.console_errors
        capture(window, "sample")
        window.resize(860, 650)
        QTest.qWait(100)
        assert javascript(window.page, "document.documentElement.scrollWidth <= innerWidth"), "Narrow page overflows horizontally"
        capture(window, "narrow")
        window.reload_page()
        wait_for(lambda: window.bridge.session_id and window.bridge.session_id != first_session and dom_ready(window), "Reload did not renew page session")
        assert javascript(window.page, "document.querySelectorAll('#sample-rows tr').length") == 3, "Reload lost Python state"
        assert window.bridge.service.job["result"]["unchanged"]
        # A different top-level document must not acquire the bridge.
        window.view.setUrl(QUrl("https://example.com/"))
        QTest.qWait(150)
        assert window.page.url().toString() == APP_URL
        assert not window.page.console_errors, window.page.console_errors
        # Hold a real worker to check refresh and deferred close deterministically.
        gate = Event()
        def held_sample(report):
            gate.wait(5)
            return inspect_sample(report)
        with patch("yingxu.web_ui.workers.inspect_sample", held_sample):
            try:
                job_id = window.bridge.service.start_sample()["jobId"]
                old_session = window.bridge.session_id
                window.reload_page()
                wait_for(lambda: window.bridge.session_id and window.bridge.session_id != old_session and dom_ready(window), "Active task reload failed")
                assert window.bridge.service.job["jobId"] == job_id
                assert javascript(window.page, "document.getElementById('sample-button').disabled")
                window.close()
                assert window.isVisible(), "Window destroyed a running worker"
            finally:
                gate.set()
            wait_for(lambda: not window.isVisible(), "Deferred close did not finish")
            assert window.bridge.service.worker is None
        assert not errors, errors
        print(json.dumps({"result": "PASS", "runtime": window.bridge.service.state()["runtime"],
                          "checks": ["local ESM/CSS", "JS-Python reply", "background events",
                                     "fixture unchanged", "3 subtitle targets", "reload/state", "external navigation denied", "narrow layout", "active task reload", "deferred close"]}, ensure_ascii=False))
    finally:
        if window.isVisible():
            window.close()
        QTest.qWait(250)
