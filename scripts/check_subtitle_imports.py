"""Stage 9c: real Qt downloads, native import, reviewed execution in disposable media.

Loopback allowances only exist as test-process patches. No live website/download,
personal video, desktop automation, or release-policy changes are involved.
"""
from contextlib import ExitStack
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import faulthandler
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from scripts.check_subtitle_browser import wait_for, javascript
from scripts.check_subtitle_recommendations import clicked, settled
from yingxu.operations import HistoryStore
from yingxu.subtitle_sources.websites import website_for
import yingxu.web_ui.subtitle_browser as browser_module
from yingxu.web_ui.subtitle_browser import SubtitleBrowser
from yingxu.web_ui.window import WebWindow

SRT = b"1\n00:00:01,000 --> 00:00:02,000\nControlled subtitle\n"


class Handler(BaseHTTPRequestHandler):
    package = b""

    def log_message(self,*_args): pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in {"/bundle.zip","/single.srt"}:
            content = self.package if path.endswith("zip") else SRT
            self.send_response(200)
            self.send_header("Content-Type","application/octet-stream")
            self.send_header("Content-Disposition",f'attachment; filename="{path[1:]}"')
        else:
            content = b'<!doctype html><meta charset="utf-8"><a id="zip" href="/bundle.zip">ZIP</a><a id="single" href="/single.srt">SRT</a>'
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(content)))
        self.end_headers();self.wfile.write(content)


def main():
    native = '--native' in sys.argv
    if native:
        from yingxu.web_ui.native_window import configure_graphics
        configure_graphics()
    faulthandler.dump_traceback_later(25,repeat=True)
    output = ROOT/("work/test-results/stage13-native-workflow.json" if native else "work/test-results/stage9c-fixture.json")
    output.parent.mkdir(parents=True,exist_ok=True)
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setStyle("Fusion")
    if native:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        from yingxu.web_ui.native_window import NativeWindow
    errors = []
    sys.excepthook = lambda kind,error,trace:(errors.append(f"{kind.__name__}: {error}"),sys.__excepthook__(kind,error,trace))
    result = {"checks":[],"passed":False}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("字幕/Feature.S01E01.chs.srt",SRT)
        archive.writestr("字幕/Feature.S01E01.eng.srt",SRT)
        archive.writestr("readme.txt","not a subtitle")
    Handler.package = buffer.getvalue()
    server = ThreadingHTTPServer(("127.0.0.1",0),Handler);server.daemon_threads = True
    Thread(target=server.serve_forever,daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    original_public = browser_module.public_https
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix="stage9c-",dir=output.parent) as directory, ExitStack() as patches:
            root = Path(directory);media = root/"中文 & 视频";media.mkdir()
            for episode in (1,2): (media/f"Feature.S01E{episode:02d}.1080p.mkv").write_bytes(b"original-video")
            before = {path.name:path.read_bytes() for path in media.iterdir()}
            def local_url(url,hosts=None):
                value = urlsplit(url)
                return value.scheme == "http" and value.netloc == f"127.0.0.1:{server.server_port}"
            preferences = QSettings(str(root/"preferences.ini"),QSettings.Format.IniFormat)
            preferences.setValue('autoImport',False)
            def create_browser(parent=None):
                return SubtitleBrowser(parent,download_root=root/"inbox",settings=preferences)
            for owner,name,value in [(browser_module,"source_url",local_url),
                (browser_module,"public_https",lambda url:local_url(url) or original_public(url)),
                (browser_module,"website_for",lambda key:replace(website_for(key),home=origin+"/")),
                (browser_module,"SubtitleBrowser",create_browser)]:
                patches.enter_context(patch.object(owner,name,value))
            patches.enter_context(patch("yingxu.web_ui.window.QFileDialog.getExistingDirectory",return_value=str(media)))
            options = dict(history=HistoryStore(root/"history.jsonl"),
                appearance_settings=QSettings(str(root/"appearance.ini"),QSettings.Format.IniFormat))
            window = NativeWindow(**options) if native else WebWindow( **options)
            window.show()
            print("workspace: waiting for startup",flush=True)
            wait_for(lambda:window._loaded and settled(window),"workspace startup")
            clicked(window,"#dataset-button")
            service = window.bridge.service
            wait_for(lambda:service.data is not None and settled(window),"scan")
            clicked(window,"#online-subtitles-button")
            print("workspace: scan completed, opening online browser",flush=True)
            wait_for(lambda:window.subtitle_browser is not None and not service.native_busy,"online entry")
            online = window.subtitle_browser
            for number,selector in enumerate(("#zip","#single")):
                online.queue.setCurrentRow(number)
                task = online.current_task()
                online.prepare_context(task,task.query)
                online.view.setUrl(QUrl(origin+"/"+str(number)))
                online.pages.setCurrentIndex(1)
                wait_for(lambda:javascript(online.page,"Boolean(document.getElementById('zip'))") and not online.load_timer.isActive(),"download page")
                clicked(online,selector)
                print(f"download: {selector}",flush=True)
                wait_for(lambda:len(online.downloads) == number+1 and not online.busy_downloads(),"download received")
            assert len(service.staged_downloads) == 2 and len(online.import_selection()) == 2
            assert online.page.webChannel() is None
            assert before == {path.name:path.read_bytes() for path in media.iterdir()}
            result["checks"].append("actual_qt_zip_and_direct_downloads_registered_no_media_change_no_remote_channel")
            QTest.mouseClick(online.import_button,Qt.MouseButton.LeftButton)
            print("import: requested",flush=True)
            QTest.mouseClick(online.import_button,Qt.MouseButton.LeftButton)
            wait_for(lambda:not online.import_busy and not service.busy and len(service.data.review.imported) == 3 and settled(window),"native import and frontend refresh")
            assert len(service.data.review.subtitles) == 3
            assert service.data.rows[0]["state"] == "未匹配" and service.data.rows[1]["state"] == "需确认"
            assert before == {path.name:path.read_bytes() for path in media.iterdir()}
            assert not online.import_selection()
            assert javascript(window.page,"document.querySelector('#inspector-content').textContent.includes('已导入 2 份候选')")
            result["checks"].append("batch_import_double_click_dedup_unambiguous_pending_ambiguous_candidates_live_refresh")
            print("import: completed, reviewing candidates",flush=True)
            clicked(window,"#inspector-content .detail-section-title button")
            wait_for(lambda:javascript(window.page,"document.querySelector('#candidate-dialog').open && Boolean(document.querySelector('.candidate-card button'))"),"candidate dialog")
            QTest.qWait(150)
            if not native: window.grab().save(str(output.with_name("stage9c-candidates.png")))
            clicked(window,".candidate-card button")
            wait_for(lambda:service.data.rows[0]["state"] == "需确认" and settled(window) and not javascript(window.page,"document.querySelector('#candidate-dialog').open"),"manual assignment")
            clicked(window,"#inspector-actions .detail-actions button")
            wait_for(lambda:service.data.rows[0]["state"] == "待整理" and settled(window),"first confirmation")
            clicked(window,'[data-row-id="video-2"]')
            wait_for(lambda:javascript(window.page,"document.querySelector('.detail-video').textContent.includes('S01E02')"),"select second")
            clicked(window,"#inspector-actions .detail-actions button")
            wait_for(lambda:service.data.rows[1]["state"] == "待整理" and settled(window),"second confirmation")
            clicked(window,"#preview-button")
            wait_for(lambda:javascript(window.page,"document.querySelector('#preview-dialog').open"),"final preview")
            assert javascript(window.page,"document.querySelector('#execute-button').disabled")
            assert all(item.target.parent == media for item in service.snapshot.changes)
            assert before == {path.name:path.read_bytes() for path in media.iterdir()}
            QTest.qWait(150)
            if not native: window.grab().save(str(output.with_name("stage9c-preview.png")))
            result["checks"].append("actual_candidate_selection_and_two_review_confirmations_final_paths_preview_media_unchanged")
            clicked(window,"#preview-ack")
            wait_for(lambda:not javascript(window.page,"document.querySelector('#execute-button').disabled"),"final acknowledgement")
            javascript(window.page,"document.querySelector('#execute-button').click();document.querySelector('#execute-button').click();true")
            wait_for(lambda:service.last_result_id is not None and settled(window) and javascript(window.page,"document.querySelector('#history-dialog').open"),"organize results")
            record = service.record_page(service.last_result_id)
            assert record["success"] == 2 and not record["errors"]
            assert len(service.history.recent()) == 1
            assert len(list(media.glob("*.srt"))) == 2
            assert all(path.read_bytes() == SRT for path in media.glob("*.srt"))
            assert all((media/name).read_bytes() == content for name,content in before.items())
            assert all(entry["path"].exists() for entry in online.downloads.values())
            result["checks"].append("single_confirmed_execution_correct_files_original_downloads_retained_video_bytes_unchanged_history_recorded")
            window.resize(940,700)
            javascript(window.page,"document.querySelector('#theme-quick').value='dark';document.querySelector('#theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
            QTest.qWait(220)
            assert javascript(window.page,"document.documentElement.scrollWidth<=innerWidth")
            if not native: window.grab().save(str(output.with_name("stage9c-result-dark.png")))
            if native: result['displayOutput'] = window.appearance.output_status
            assert not window.page.console_errors,window.page.console_errors
            result["checks"].append("narrow_dark_result_window_no_js_errors")
            window.close();QTest.qWait(200);window = None
            assert not errors,errors
            result["passed"] = True
    except Exception as error:
        result["failure"] = f"{type(error).__name__}: {error}"
        if window is not None:
            result["job"] = window.bridge.service.job
            result["jsErrors"] = window.page.console_errors
            if not native: window.grab().save(str(output.with_name("stage9c-failure.png")))
        raise
    finally:
        if window is not None: window.close()
        QTest.qWait(150)
        server.shutdown();server.server_close()
        result["pythonErrors"] = errors
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=True),flush=True)
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":main()
