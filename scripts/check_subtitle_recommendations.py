"""Focused Qt verification of stage 9b, with disposable media/settings.

Default: controlled website + real local workspace. --live: one ordinary SubHD
search and bounded DOM read, with no subtitle download or CAPTCHA automation.
The loopback policy substitutions exist only in this test process.
"""
import argparse
from contextlib import ExitStack
from dataclasses import replace
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from scripts.check_subtitle_browser import wait_for, javascript
import yingxu.web_ui.subtitle_browser as browser
import yingxu.subtitle_sources.candidates as candidates
from yingxu.subtitle_sources.websites import website_for
from yingxu.web_ui.subtitle_browser import SubtitleBrowser
from yingxu.web_ui.window import WebWindow
from yingxu.operations import HistoryStore


class Handler(BaseHTTPRequestHandler):
    requests = []
    challenge = True
    subtitle = b"1\n00:00:01,000 --> 00:00:02,000\nTest subtitle\n"

    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        self.requests.append(unquote(path))
        if path == "/file.srt":
            body = self.subtitle
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="fixture.srt"')
        else:
            code = 200
            controls = '''<input id="sn" name="subhd_search" type="search"><button id="searchbutton"
              onclick="location.href='/search/'+encodeURIComponent(document.getElementById('sn').value)">搜索</button>'''
            if path.startswith("/search/"):
                query = unquote(path[8:])
                if "Challenge" in query and self.challenge:
                    code = 404
                    content = "<title>网站防火墙</title>网站访问认证页面 请输入验证码后继续访问"
                else:
                    release = query.replace(" ", ".")
                    content = "<title>搜索结果</title>共 4 条"
                    for key, name, metadata in [("Good", release, "双语 简体 英语 ASS"),
                                                ("Traditional", release, "繁体 SRT"),
                                                ("Bad", "Other.S02E99.2020", "双语 简体 英语 SRT")]:
                        content += f'''<div class="clearfix"><div class="float-start"><a href="/a/{key}">Example</a></div>
                          <div class="view-text"><a href="/a/{key}">{escape(name)}.1080p.BluRay</a></div>
                          <div class="text-truncate">{metadata}</div></div>'''
                    content += '<div class="view-text"><a href="https://example.com/a/Fake">Do not include</a></div>'
            elif path.startswith("/a/"):
                content = '<title>字幕详情</title><a id="download" href="/file.srt">下载受控测试字幕</a>'
            else:
                content = "<title>字幕搜索</title>" + controls
            body = ('<!doctype html><meta charset="utf-8">' + content).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def clicked(window, selector):
    return javascript(window.page, f"document.querySelector({json.dumps(selector)}).click();true")


def settled(window):
    return not window.bridge.service.busy and javascript(window.page,
        "document.documentElement.dataset.ready==='true' && document.documentElement.dataset.loading==='false'")


def fixture(output):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    original_public = browser.public_https
    original_search = browser.submit_subhd_search_script
    original_candidates = candidates.candidates_script
    def local_url(url, hosts=None):
        u = urlsplit(url)
        return u.scheme == "http" and u.netloc == f"127.0.0.1:{server.server_port}"
    def local_js(script, hosts):
        return (script.replace(json.dumps(sorted(hosts)), json.dumps(["127.0.0.1"]))
                .replace("u.protocol !== 'https:'", "u.protocol !== 'http:'")
                .replace("u.port !== '443'", f"u.port !== '{server.server_port}'"))
    result = {"mode": "controlled-workspace", "checks": []}
    window = online = None
    Handler.requests = []
    Handler.challenge = True
    try:
        with tempfile.TemporaryDirectory(prefix="stage9b-", dir=output.parent) as directory, ExitStack() as patches:
            root = Path(directory)
            media = root / "中文 视频 & test"
            media.mkdir()
            for name in ("Example.S01E01.1080p.mkv", "Example.S01E02.1080p.mkv", "Challenge.S01E03.mkv"):
                (media / name).write_bytes(b"original-video")
            before = {path.name: path.read_bytes() for path in media.iterdir()}
            settings = QSettings(str(root / "subtitles.ini"), QSettings.Format.IniFormat)
            settings.setValue('autoImport',False)
            def create_browser(parent=None):
                return SubtitleBrowser(parent, website="subhd", settings=settings, download_root=root / "inbox")
            for owner, name, value in [
                (browser, "source_url", local_url),
                (browser, "public_https", lambda url: local_url(url) or original_public(url)),
                (browser, "website_for", lambda key: replace(website_for(key), home=origin + "/")),
                (browser, "submit_subhd_search_script", lambda query, hosts: local_js(original_search(query, hosts), hosts)),
                (browser, "candidates_script", lambda site, query: local_js(original_candidates(site, query), site.hosts)),
                (candidates, "source_url", local_url),
                (browser, "SubtitleBrowser", create_browser),
            ]:
                patches.enter_context(patch.object(owner, name, value))
            patches.enter_context(patch("yingxu.web_ui.window.QFileDialog.getExistingDirectory", return_value=str(media)))
            appearance = QSettings(str(root / "appearance.ini"), QSettings.Format.IniFormat)
            window = WebWindow( appearance_settings=appearance, history=HistoryStore(root / "history.jsonl"))
            window.show()
            wait_for(lambda: window._loaded and settled(window), "Workspace startup failed")
            assert javascript(window.page, "document.getElementById('online-subtitles-button').disabled")
            clicked(window, "#dataset-button")
            wait_for(lambda: window.bridge.service.data is not None and settled(window), "Scan did not finish")
            clicked(window, "#online-subtitles-button")
            wait_for(lambda: window.subtitle_browser is not None and not window.bridge.service.native_busy, "Native subtitle entry failed")
            online = window.subtitle_browser
            assert len(online.tasks) == 3 and not Handler.requests
            assert online.page.webChannel() is None and online.profile is not window.profile
            assert all(task.scan_id == window.bridge.service.data.scan_id and task.row_id for task in online.tasks)
            clicked(window, "#online-subtitles-button")
            wait_for(lambda: not window.bridge.service.native_busy, "Duplicate native open did not finish")
            assert window.subtitle_browser is online and len(online.tasks) == 3
            result["checks"].append("main_entry_stable_ids_no_network_until_search_no_duplicates")
            # Challenge task stays unchecked on the first batch.
            third = next(i for i, task in enumerate(online.tasks) if "Challenge" in task.video.name)
            online.queue.item(third).setCheckState(Qt.CheckState.Unchecked)
            QTest.mouseClick(online.batch_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: online.batch_done == 1 and online.batch_timer.isActive(), "First batch result missing")
            QTest.mouseClick(online.stop_batch_button, Qt.MouseButton.LeftButton)
            QTest.qWait(1700)
            assert not online.batch_running and len(online.results) == 1
            assert len([p for p in Handler.requests if p.startswith("/search/")]) == 1
            QTest.mouseClick(online.batch_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: not online.batch_running and len(online.results) == 2, "Batch resume failed")
            assert all(len(entry["rows"]) == 3 for entry in online.results.values())
            assert not any("Challenge" in p for p in Handler.requests)
            result["checks"].append("sequential_batch_stop_resume_unchecked_skip_bounded_real_dom_read")
            first = next(i for i, task in enumerate(online.tasks) if "S01E01" in task.video.name)
            online.queue.setCurrentRow(first)
            assert online.recommendations.rows[0]["url"].endswith("/Good")
            online.language_picker.setCurrentIndex(online.language_picker.findData("zh-Hant"))
            assert online.recommendations.rows[0]["url"].endswith("/Traditional")
            reloaded = QSettings(str(root / "subtitles.ini"), QSettings.Format.IniFormat)
            assert reloaded.value("language") == "zh-Hant"
            online.language_picker.setCurrentIndex(online.language_picker.findData("bilingual"))
            bad = next(i for i, row in enumerate(online.recommendations.rows) if row["url"].endswith("/Bad"))
            online.recommendations.list.setCurrentRow(bad)
            assert not online.recommendations.choose_button.isEnabled()
            online.recommendations.ack.setFocus()
            QTest.keyClick(online.recommendations.ack, Qt.Key.Key_Space)
            assert online.recommendations.ack.isChecked() and online.recommendations.choose_button.isEnabled()
            QTest.mouseClick(online.recommendations.choose_button, Qt.MouseButton.LeftButton)
            key = online.result_key(online.current_task())
            assert online.choices[key]["url"].endswith("/Bad")
            online.recommendations.list.setCurrentRow(0)
            # Title-only searches may return a release without year/episode
            # metadata. Switching the choice still requires its own review.
            if online.recommendations.rows[0]['needsReview']:
                QTest.keyClick(online.recommendations.ack, Qt.Key.Key_Space)
            QTest.mouseClick(online.recommendations.choose_button, Qt.MouseButton.LeftButton)
            assert online.choices[key]["url"].endswith("/Good")
            result["checks"].append("saved_language_rerank_low_confidence_ack_and_replace_choice")
            online.set_theme("light")
            QTest.qWait(180)
            online.grab().save(str(output.with_name("stage9b-recommendations-light.png")))
            QTest.mouseClick(online.recommendations.open_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: online.page.url().path().startswith("/a/") and not online.load_timer.isActive()
                     and javascript(online.page, "Boolean(document.getElementById('download'))"), "Candidate detail did not open")
            clicked(online, "#download")
            wait_for(lambda: len(online.downloads) == 1 and not online.busy_downloads(), "Candidate download did not stage")
            entry = next(iter(online.downloads.values()))
            receipt = json.loads(entry["path"].with_name("receipt.json").read_text(encoding="utf-8"))
            assert receipt["scanId"] == online.current_task().scan_id and receipt["rowId"] == online.current_task().row_id
            assert receipt["chosenCandidate"]["url"].endswith("/Good") and not receipt["matchConfirmed"]
            result["checks"].append("candidate_detail_download_context_and_unconfirmed_receipt")
            for i in range(online.queue.count()):
                online.queue.item(i).setCheckState(Qt.CheckState.Checked if i == third else Qt.CheckState.Unchecked)
            QTest.mouseClick(online.batch_button, Qt.MouseButton.LeftButton)
            wait_for(lambda: online.verification_required and not online.batch_running, "CAPTCHA did not pause batch")
            assert online.query.text() == online.active_task["query"] and len(online.results) == 2
            Handler.challenge = False
            online.source_picker.setCurrentIndex(online.source_picker.findData("subhd-one"))
            wait_for(lambda: len(online.results) == 3 and not online.search_pending, "Backup source did not recover search")
            assert online.current_task().row_id == online.tasks[third].row_id
            assert len(online.choices) == 1
            result["checks"].append("captcha_pause_query_retention_backup_source_preserves_task_and_old_results")
            window.resize(940, 700)
            assert javascript(window.page, "document.documentElement.scrollWidth<=innerWidth && document.getElementById('online-subtitles-button').getBoundingClientRect().right<=innerWidth")
            javascript(window.page, "document.getElementById('theme-quick').value='dark';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
            wait_for(lambda: javascript(window.page, "document.documentElement.dataset.theme==='dark'"), "Dark theme failed")
            online.resize(940, 700)
            QTest.qWait(220)
            online.grab().save(str(output.with_name("stage9b-recommendations-dark.png")))
            window.grab().save(str(output.with_name("stage9b-workspace-dark.png")))
            assert not window.page.console_errors, window.page.console_errors
            assert before == {path.name: path.read_bytes() for path in media.iterdir()}
            result["checks"].append("real_workspace_narrow_dark_theme_no_js_errors_media_unchanged")
            window.close()
            QTest.qWait(200)
            assert online.closing
            online = window = None
            result["checks"].append("parent_closes_owned_browser_and_profile")
            result["passed"] = True
    except Exception:
        if online is not None:
            result["diagnostic"] = {"status": online.status.text(), "batch": online.batch_status.text(),
                "running": online.batch_running, "done": online.batch_done,
                "pending": online.pending_query, "searchPending": online.search_pending,
                "path": online.page.url().path(), "requests": Handler.requests,
                "dom": javascript(online.page, "document.body?.innerText.slice(0,2000)")}
            online.grab().save(str(output.with_name("stage9b-fixture-failure.png")))
            print(json.dumps(result, ensure_ascii=True), flush=True)
        raise
    finally:
        if window is not None:
            window.close()
        elif online is not None:
            online.close()
        QTest.qWait(200)
        server.shutdown()
        server.server_close()
    return result


def live(output, site):
    result = {"mode": "live-read-only", "site": site, "query": "Interstellar 2014"}
    with tempfile.TemporaryDirectory(prefix="live-recommend-", dir=output.parent) as directory:
        settings = QSettings(str(Path(directory) / "preferences.ini"), QSettings.Format.IniFormat)
        window = SubtitleBrowser(website=site, settings=settings)
        try:
            window.set_theme("light")
            window.show()
            window.query.setText(result["query"])
            window.start_search()
            wait_for(lambda: bool(window.results) or window.verification_required, "No real results or challenge", 55)
            rows = window.recommendations.rows
            result.update(candidateCount=len(rows), status=window.status.text(), challenge=window.verification_required,
                          sample=rows[:3], noWebChannel=window.page.webChannel() is None,
                          downloads=len(window.downloads))
            window.grab().save(str(output.with_suffix(".png")))
            assert rows and not window.downloads and window.page.webChannel() is None
            result["passed"] = True
        finally:
            window.close()
            QTest.qWait(200)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--site", choices=["subhd", "subhd-one"], default="subhd")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / f"work/test-results/stage9b-{'live-' + args.site if args.live else 'fixture'}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    errors = []
    sys.excepthook = lambda kind, error, trace: (errors.append(f"{kind.__name__}: {error}"), sys.__excepthook__(kind, error, trace))
    result = {}
    try:
        result = live(output, args.site) if args.live else fixture(output)
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        result["pythonErrors"] = errors
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=True), flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
