"""Export notices from the installed renderer's internal credits page, offline.

Build-time helper only. It is never imported by or shipped in the desktop app.
"""
from pathlib import Path
import hashlib
import json
import sys

from PySide6 import __version__
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor


class OfflineOnly(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        if info.requestUrl().scheme() not in {"chrome", "qrc", "data"}:
            info.block(True)


def main():
    destination = Path(__file__).resolve().parents[1] / "release" / "licenses"
    app = QApplication(sys.argv)
    profile = QWebEngineProfile(app)
    interceptor = OfflineOnly(profile)
    profile.setUrlRequestInterceptor(interceptor)
    page = QWebEnginePage(profile)
    result = []

    def accept(text):
        if text and len(text) > 10000:
            result.append(text)
            app.quit()

    def loaded(ok):
        print(f"Internal credits loaded={ok}, url={page.url().toString()}", flush=True)
        if ok:
            # License sections are collapsed by default; innerText omits them.
            page.runJavaScript("document.body.textContent", accept)

    page.loadFinished.connect(loaded)
    QTimer.singleShot(30000, app.quit)
    page.setUrl(QUrl("chrome://credits/"))
    app.exec()
    if not result:
        raise RuntimeError("Internal Chromium credits did not load; no substitute generated")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "Chromium-credits.txt"
    target.write_text(result[0], encoding="utf-8")
    metadata = {"origin": "chrome://credits/ (offline, installed Qt WebEngine)",
                "PySide6": __version__, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (destination / "Chromium-credits-origin.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({**metadata, "bytes": target.stat().st_size}))
    page.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
