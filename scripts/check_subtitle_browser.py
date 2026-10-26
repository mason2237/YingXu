"""Opt-in Qt checks for the subtitle browser; no personal media or credentials.

Use --live for one real Zimuku visit. The default controlled fixture mode is
implemented separately from production policy; it never relaxes release code.
"""
import argparse
from contextlib import ExitStack
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import yingxu.web_ui.subtitle_browser as browser
from yingxu.subtitle_sources.zimuku import SITE_HOSTS, submit_search_script
from yingxu.subtitle_sources.websites import WEBSITES, website_for
from yingxu.web_ui.subtitle_browser import SubtitleBrowser


def wait_for(condition, message, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        QTest.qWait(25)
    raise AssertionError(message)


def javascript(page, source):
    result = []
    page.runJavaScript(source, result.append)
    wait_for(lambda: bool(result), "JavaScript callback timed out", 6)
    return result[0]


def live_check(output, website="zimuku"):
    window = SubtitleBrowser(download_root=output.parent / "live-inbox", website=website)
    window.show()
    events = []
    result = {"mode": "live", "site": window.website.home, "query": "Interstellar 2014"}
    try:
        QTest.qWait(150)
        result["startup"] = window.isVisible()
        result["offTheRecord"] = window.profile.isOffTheRecord()
        result["noWebChannel"] = window.page.webChannel() is None
        window.query.setText(result["query"])
        window.start_search()
        window.page.loadingChanged.connect(lambda info: events.append({
            "status": info.status().name, "code": info.errorCode(),
            "domain": info.errorDomain().name, "error": info.errorString(),
            "host": info.url().host(), "path": info.url().path(),
        }))
        wait_for(lambda: any(row["status"] in {"LoadSucceededStatus", "LoadFailedStatus", "LoadStoppedStatus"}
                             for row in events), "Site load did not finish", 35)
        QTest.qWait(700)
        if window.load_timer.isActive():
            wait_for(lambda: not window.load_timer.isActive(), "Search did not finish", 35)
        result["page"] = json.loads(javascript(window.page, """JSON.stringify({
          title:document.title, host:location.hostname, path:location.pathname,
          text:document.body?.innerText.slice(0,1200),
          forms:Array.from(document.forms).map(f=>({action:f.action,method:f.method,
            fields:Array.from(f.querySelectorAll('input')).map(i=>({name:i.name,type:i.type}))})).slice(0,8),
          inputs:Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=password])'))
            .map(i=>({id:i.id,name:i.name,type:i.type,placeholder:i.placeholder})).slice(0,8),
          buttons:Array.from(document.querySelectorAll('button,[onclick]'))
            .map(b=>({tag:b.tagName,id:b.id,text:b.innerText.slice(0,80),click:b.getAttribute('onclick')})).slice(0,10),
          candidates:Array.from(document.querySelectorAll('a[href^="/a/"]')).slice(0,3)
            .map(a=>({href:a.getAttribute('href'),text:a.textContent,html:a.parentElement.outerHTML.slice(0,2400)}))
        })"""))
        result["statusText"] = window.status.text()
        result["verificationRequired"] = window.verification_required
        result["queryRetained"] = window.pending_query == result["query"]
        result["events"] = events
        result["pageLoaded"] = bool(events and events[-1]["status"] == "LoadSucceededStatus")
        result["screenshot"] = window.grab().save(str(output.with_suffix(".png")))
    finally:
        window.close()
        QTest.qWait(250)
    return result


class FixtureHandler(BaseHTTPRequestHandler):
    requests = []
    subtitle = b"1\n00:00:01,000 --> 00:00:02,000\nSample subtitle\n"

    def log_message(self, *_args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        self.requests.append(self.path)
        if url.path in {"/", "/search"}:
            body = b'''<!doctype html><title>Subtitle fixture</title>
            <form action="/search" method="get"><input type="search" name="q"><button>Search</button></form>
            <a id="subtitle" href="/file.srt">Download subtitle</a>
            <a id="bad" href="/bad.srt">Error content</a>
            <a id="exe" href="/file.exe">Unsupported file</a>
            <a id="slow" href="/slow.srt">Cancellable file</a>
            <a id="huge" href="/huge.srt">Over limit</a>'''
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/challenge":
            body = "<title>网站防火墙</title>网站访问认证页面 请输入验证码后继续访问".encode()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        filename = "file.exe" if url.path == "/file.exe" else "sample.srt"
        body = b"<html>Verification error</html>" if url.path == "/bad.srt" else self.subtitle
        slow = url.path == "/slow.srt"
        total = 1024 * 1024 if slow else 65 * 1024 * 1024 if url.path == "/huge.srt" else len(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(total))
        self.end_headers()
        try:
            if slow:
                for _ in range(total // 4096):
                    self.wfile.write(b"x" * 4096)
                    self.wfile.flush()
                    time.sleep(0.025)
            else:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def fixture_check(output):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    FixtureHandler.requests = []
    original_public = browser.public_https
    def local_source(url, _hosts=None):
        parsed = urlsplit(url)
        return parsed.scheme == "http" and parsed.netloc == f"127.0.0.1:{server.server_port}"
    def local_script(query, hosts=SITE_HOSTS):
        # Only this test process substitutes the fixture origin, including port.
        return (submit_search_script(query, hosts)
                .replace(json.dumps(sorted(hosts)), json.dumps(["127.0.0.1"]))
                .replace("u.protocol === 'https:'", "u.protocol === 'http:'")
                .replace("u.port === '443'", f"u.port === '{server.server_port}'"))
    result = {"mode": "controlled-fixture", "checks": []}
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix="browser-fixture-", dir=output.parent) as folder, ExitStack() as patches:
            for name, value in (("HOME_URL", origin + "/"), ("source_url", local_source),
                                ("public_https", lambda url: local_source(url) or original_public(url)),
                                ("submit_search_script", local_script),
                                ("submit_subhd_search_script", local_script),
                                ("website_for", lambda key: replace(website_for(key), home=origin + "/"))):
                patches.enter_context(patch.object(browser, name, value))
            root = Path(folder)
            media = root / "media"
            media.mkdir()
            first = media / "示例.S01E01.1080p.mkv"
            second = media / "示例.S01E02.1080p.mkv"
            first.write_bytes(b"original-video-one")
            second.write_bytes(b"original-video-two")
            window = SubtitleBrowser(download_root=root / "inbox")
            window.show()
            assert window.profile.isOffTheRecord() and window.page.webChannel() is None
            result["checks"].append("startup_isolated_profile_no_channel")
            patches.enter_context(patch.object(browser.QFileDialog, "getOpenFileNames", return_value=([str(first), str(second)], "")))
            QTest.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: any(urlsplit(path).path == "/search" for path in FixtureHandler.requests), "Search form did not submit")
            wait_for(lambda: not window.load_timer.isActive(), "Search results did not load")
            searched = [parse_qs(urlsplit(path).query)["q"][0] for path in FixtureHandler.requests if urlsplit(path).path == "/search"]
            assert searched == ["示例"], searched
            result["checks"].append("multi_video_selection_auto_search_exact_query")

            def click_link(selector):
                javascript(window.page, f"document.querySelector('{selector}').click();true")

            def receipt(key):
                return json.loads(window.downloads[key]["path"].with_name("receipt.json").read_text(encoding="utf-8"))

            for count in (1, 2):
                click_link("#subtitle")
                wait_for(lambda: len(window.downloads) == count and all(row["finished"] for row in window.downloads.values()), "Download did not finish")
            paths = [row["path"] for row in window.downloads.values()]
            assert paths[0] != paths[1]
            assert all(path.read_bytes() == FixtureHandler.subtitle for path in paths)
            assert all(receipt(key)["status"] == "subtitle_candidate" and not receipt(key)["matchConfirmed"] for key in window.downloads)
            result["checks"].append("actual_download_signal_receipts_no_overwrite")
            click_link("#bad")
            wait_for(lambda: len(window.downloads) == 3 and all(row["finished"] for row in window.downloads.values()), "Invalid content did not finish")
            assert receipt(next(reversed(window.downloads)))["status"] == "rejected"
            result["checks"].append("html_disguised_as_subtitle_rejected")
            before = len(FixtureHandler.requests)
            click_link("#exe")
            wait_for(lambda: len(FixtureHandler.requests) > before, "Executable request did not arrive")
            QTest.qWait(250)
            assert len(window.downloads) == 3 and not list((root / "inbox").rglob("*.exe"))
            result["checks"].append("unsupported_download_rejected")
            click_link("#slow")
            wait_for(window.busy_downloads, "Slow download did not start")
            assert not window.queue.isEnabled() and not window.search_button.isEnabled()
            QTest.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: not window.busy_downloads(), "Cancel did not finish")
            assert receipt(next(reversed(window.downloads)))["status"] == "cancelled"
            result["checks"].append("cancel_and_task_switch_lock")
            before = len(FixtureHandler.requests)
            count = len(window.downloads)
            click_link("#huge")
            wait_for(lambda: len(FixtureHandler.requests) > before, "Oversized request did not arrive")
            QTest.qWait(300)
            assert len(window.downloads) == count
            result["checks"].append("known_oversize_cancelled_before_staging")
            searches_before = len([path for path in FixtureHandler.requests if urlsplit(path).path == "/search"])
            QTest.mouseClick(window.next_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: len([path for path in FixtureHandler.requests if urlsplit(path).path == "/search"]) > searches_before, "Next task did not search")
            wait_for(lambda: not window.load_timer.isActive(), "Next results did not load")
            assert parse_qs(urlsplit([path for path in FixtureHandler.requests if urlsplit(path).path == "/search"][-1]).query)["q"] == ["示例"]
            click_link("#subtitle")
            wait_for(lambda: len(window.downloads) == count + 1 and not window.busy_downloads(), "Second task download did not finish")
            assert receipt(next(reversed(window.downloads)))["videoName"] == second.name
            assert receipt(next(iter(window.downloads)))["videoName"] == first.name
            result["checks"].append("download_task_association_survives_switch")
            previous_searches = len([path for path in FixtureHandler.requests if urlsplit(path).path == "/search"])
            window.source_picker.setCurrentIndex(window.source_picker.findData("subhd"))
            wait_for(lambda: len([path for path in FixtureHandler.requests if urlsplit(path).path == "/search"]) > previous_searches,
                     "Source switch did not preserve and resubmit the query")
            wait_for(lambda: not window.load_timer.isActive(), "Switched source did not load")
            assert window.active_task["source"] == "subhd" and window.active_task["videoName"] == second.name
            assert receipt(next(iter(window.downloads)))["source"] == "zimuku"
            result["checks"].append("source_switch_preserves_query_and_previous_receipts")
            window.pending_query = "retained query"
            window.page.setUrl(browser.QUrl(origin + "/challenge"))
            wait_for(lambda: window.verification_required, "Challenge page was not recognized")
            assert window.pending_query == "retained query" and "验证码" in window.status.text()
            result["checks"].append("404_verification_page_preserves_search")
            assert sorted(path.name for path in media.iterdir()) == sorted([first.name, second.name])
            assert first.read_bytes() == b"original-video-one" and second.read_bytes() == b"original-video-two"
            result["checks"].append("media_files_unchanged")
            window.resize(880, 620)
            QTest.qWait(150)
            result["screenshot"] = window.grab().save(str(output.with_suffix(".png")))
            result["downloads"] = [receipt(key) for key in window.downloads]
            window.close()
            QTest.qWait(250)
            window = None
            result["passed"] = True
    finally:
        if window is not None:
            window.close()
            QTest.qWait(250)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--site", choices=[site.key for site in WEBSITES], default="zimuku")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        args.output = ROOT / f"work/test-results/stage9a-{'live-' + args.site if args.live else 'fixture'}.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("YingXu Subtitle Browser Check")
    app.setStyle("Fusion")
    errors = []
    def hook(kind, error, trace):
        errors.append(f"{kind.__name__}: {error}")
        sys.__excepthook__(kind, error, trace)
    sys.excepthook = hook
    result = {}
    try:
        result = live_check(args.output, args.site) if args.live else fixture_check(args.output)
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        result["pythonErrors"] = errors
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=True), flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
