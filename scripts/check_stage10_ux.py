"""Focused real Qt checks for startup, typography, guidance and automatic preparation."""
from contextlib import ExitStack
from dataclasses import replace
from io import BytesIO
import json
import os
import re
import faulthandler
from pathlib import Path
import sys
import tempfile
from threading import Thread
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QPoint,QSettings,Qt,QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from scripts.check_subtitle_browser import wait_for,javascript
from scripts.check_subtitle_recommendations import Handler,clicked,settled
import yingxu.web_ui.subtitle_browser as browser
import yingxu.subtitle_sources.candidates as candidates
from yingxu.subtitle_sources.websites import website_for
from yingxu.web_ui.window import WebWindow
from yingxu.operations import HistoryStore


class DownloadHandler(Handler):
    package=b''
    def do_GET(self):
        path=urlsplit(self.path).path
        if path not in {'/bundle.zip','/broken.rar','/files'}:
            return super().do_GET()
        if path=='/files':
            body=b'<a id="zip" href="/bundle.zip">download</a><a id="bad" href="/broken.rar">invalid</a>'
        else:
            body=self.package if path.endswith('zip') else b'Rar!\x1a\x07\x01\x00invalid'
        self.send_response(200)
        self.send_header('Content-Type','text/html' if path=='/files' else 'application/octet-stream')
        if path!='/files': self.send_header('Content-Disposition',f'attachment; filename="{path[1:]}"')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


def main():
    faulthandler.dump_traceback_later(25,repeat=True)
    prefix=os.environ.get('YINGXU_UX_CHECK_PREFIX','stage10')
    if not re.fullmatch(r'[a-z0-9_-]+',prefix): raise ValueError('Invalid artifact prefix')
    output=ROOT/f'work/test-results/{prefix}-ux.json';output.parent.mkdir(parents=True,exist_ok=True)
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion')
    errors=[]
    sys.excepthook=lambda kind,error,trace:(errors.append(f'{kind.__name__}: {error}'),sys.__excepthook__(kind,error,trace))
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        archive.writestr('字幕/sample.chs.srt',Handler.subtitle)
        archive.writestr('readme.txt','not a subtitle')
    DownloadHandler.package=buffer.getvalue()
    server=ThreadingHTTPServer(('127.0.0.1',0),DownloadHandler);server.daemon_threads=True
    Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    result={'checks':[],'passed':False};window=None
    original_public=browser.public_https;original_script=browser.submit_subhd_search_script
    original_candidates=candidates.candidates_script
    def local_url(url,hosts=None):
        u=urlsplit(url);return u.scheme=='http' and u.netloc==f'127.0.0.1:{server.server_port}'
    def local_js(script,hosts):
        return script.replace(json.dumps(sorted(hosts)),json.dumps(['127.0.0.1'])).replace("u.protocol !== 'https:'","u.protocol !== 'http:'").replace("u.port !== '443'",f"u.port !== '{server.server_port}'")
    try:
        with tempfile.TemporaryDirectory(prefix='stage10-',dir=output.parent) as directory,ExitStack() as patches:
            root=Path(directory);media=root/'media';media.mkdir()
            video=media/'Example.Show.S01E02.2024.2160p.WEB-DL.mkv';video.write_bytes(b'unchanged-video')
            if prefix in {'stage11','stage12'}:
                for episode in range(3,12):
                    (media/f'Example.Show.S01E{episode:02}.2024.2160p.WEB-DL.mkv').write_bytes(b'unchanged-video')
            preferences=QSettings(str(root/'preferences.ini'),QSettings.Format.IniFormat)
            def create_browser(parent=None):
                return browser_original(parent,website='subhd',download_root=root/'cache',settings=preferences)
            browser_original=browser.SubtitleBrowser
            for owner,name,value in [(browser,'source_url',local_url),(browser,'public_https',lambda u:local_url(u) or original_public(u)),
                (browser,'website_for',lambda key:replace(website_for(key),home=origin+'/')),
                (browser,'submit_subhd_search_script',lambda query,hosts:local_js(original_script(query,hosts),hosts)),
                (browser,'candidates_script',lambda site,query:local_js(original_candidates(site,query),site.hosts)),
                (candidates,'source_url',local_url),(browser,'SubtitleBrowser',create_browser)]:
                patches.enter_context(patch.object(owner,name,value))
            patches.enter_context(patch('yingxu.web_ui.window.QFileDialog.getExistingDirectory',return_value=str(media)))
            appearance=QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
            appearance.setValue('appearance/v1',json.dumps({'theme':'dark'}))
            window=WebWindow(history=HistoryStore(root/'history.jsonl'),appearance_settings=appearance)
            window.show()
            print('stage10: startup cover',flush=True)
            assert window.loading_cover.isVisible()
            cover_color=window.loading_cover.palette().color(window.loading_cover.backgroundRole()).name()
            assert cover_color=='#0c1422',cover_color
            window.grab().save(str(output.with_name(f'{prefix}-startup-cover.png')))
            wait_for(lambda:window._loaded and settled(window),'Initial frame/font readiness',20)
            print('stage10: first frame ready',flush=True)
            assert not window.loading_cover.isVisible()
            assert javascript(window.page,"document.documentElement.dataset.desktopBoot==='ready' && document.fonts.check('15px \"YingXu Sans\"')")
            assert 'Noto Sans SC' in window.font().family(),window.font().family()
            assert javascript(window.page,"getComputedStyle(document.body).opacity==='1'")
            for _ in range(2):
                window.reload_page();assert window.loading_cover.isVisible()
                wait_for(lambda:window._loaded and settled(window),'Reload coherent frame',20)
            result['checks'].append('dark_startup_cover_font_loaded_two_reloads_no_unprepared_frame')
            print('stage10: reloads completed',flush=True)
            clicked(window,'#dataset-button');wait_for(lambda:window.bridge.service.data is not None and settled(window),'Scan')
            clicked(window,'#online-subtitles-button');wait_for(lambda:window.subtitle_browser is not None and not window.bridge.service.native_busy,'Online entry')
            online=window.subtitle_browser
            print('stage10: online guidance',flush=True)
            assert online.query.text()=='Example Show',online.query.text()
            assert online.recommendations.empty.isVisible() and online.guide_steps[0].property('active')
            assert online.inbox_button.isEnabled() and online.auto_import.isChecked()
            opened=[]
            with patch.object(browser.QDesktopServices,'openUrl',side_effect=lambda url:opened.append(url.toLocalFile()) or True):
                QTest.mouseClick(online.inbox_button,Qt.MouseButton.LeftButton)
            assert len(opened)==1 and Path(opened[0])==online.cache_root and online.cache_root.is_dir(),opened
            online.resize(1280 if prefix in {'stage11','stage12'} else 1000,900 if prefix in {'stage11','stage12'} else 800);QTest.qWait(120)
            if prefix in {'stage11','stage12'}:
                rect=online.queue.visualItemRect(online.queue.item(0))
                QTest.mouseClick(online.queue.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(rect.left()+22,rect.center().y()))
                assert online.queue.item(0).checkState()==Qt.CheckState.Unchecked
                online.queue.setFocus();QTest.keyClick(online.queue,Qt.Key.Key_Space)
                assert online.queue.item(0).checkState()==Qt.CheckState.Checked
                assert online.queue.count()==10
                result['checks'].append('styled_queue_mouse_keyboard_selection_preserves_batch_flags')
            online.grab().save(str(output.with_name(f'{prefix}-search-guide.png')))
            if prefix=='stage12':
                for mode in ('off','soft','enhanced'):
                    window.appearance.update(json.dumps({'lighting':mode}))
                    wait_for(lambda:online._lighting==mode and javascript(window.page,f"document.documentElement.dataset.lighting==='{mode}'"),'Native/Web lighting sync')
                    assert online.centralWidget().lighting==mode
                    QTest.qWait(100)
                    if mode!='soft': online.grab().save(str(output.with_name(f'{prefix}-online-{mode}.png')))
                assert javascript(window.page,"!document.getElementById('sort-score').classList.contains('liquid-button')")
                result['checks'].append('three_lighting_modes_synchronize_native_and_web_flat_sort_heading')
            result['checks'].append('title_only_query_visual_steps_empty_state_bundled_native_font_visible_cache_button')
            QTest.mouseClick(online.recommendations.search_button,Qt.MouseButton.LeftButton)
            wait_for(lambda:bool(online.results),'Guided actual search')
            assert online.guide_steps[1].property('active')
            task=online.current_task();online.prepare_context(task,online.query.text())
            online.pages.setCurrentIndex(1);online.view.setUrl(QUrl(origin+'/files'))
            wait_for(lambda:javascript(online.page,"Boolean(document.getElementById('zip'))") and not online.load_timer.isActive(),'Download page')
            clicked(online,'#zip')
            service=window.bridge.service
            wait_for(lambda:service.data.rows[0]['state']=='需确认' and not service.busy and not online.import_busy and settled(window),'Automatic ZIP extraction and review refresh',20)
            entry=next(iter(online.downloads.values()))
            assert entry.get('imported') and online.isVisible()
            assert online.guide_steps[2].property('active')
            source=service.data.review.rows[0].matches[0].source
            assert source.read_bytes()==Handler.subtitle and source.suffix=='.srt'
            assert video.read_bytes()==b'unchanged-video' and not list(media.glob('*.srt'))
            QTest.mouseClick(online.review_button,Qt.MouseButton.LeftButton)
            assert not online.isVisible()
            wait_for(lambda:settled(window),'Review display')
            window.grab().save(str(output.with_name(f'{prefix}-auto-extracted-review.png')))
            result['checks'].append('download_automatically_unzips_registers_pending_match_no_media_changes_review_button')
            print('stage10: auto import completed',flush=True)
            online.show();online.pages.setCurrentIndex(1)
            clicked(online,'#bad')
            wait_for(lambda:len(online.downloads)==2 and not online.import_busy and not service.busy
                     and list(online.downloads.values())[-1].get('auto_attempted'),'Invalid archive attempt',20)
            revision=service.revision;QTest.qWait(850)
            assert service.revision==revision,'Failed automatic import retried indefinitely'
            assert service.data.rows[0]['state']=='需确认'
            result['checks'].append('invalid_archive_reports_error_once_without_auto_retry_loop')
            window.appearance.update(json.dumps({'theme':'light'}));QTest.qWait(250)
            online.resize(940,700);QTest.qWait(100);online.grab().save(str(output.with_name(f'{prefix}-online-light.png')))
            window.grab().save(str(output.with_name(f'{prefix}-workspace-light.png')))
            assert not window.page.console_errors,window.page.console_errors
            assert not errors,errors
            result['checks'].append('light_theme_narrow_window_and_no_python_or_js_errors')
            if prefix in {'stage11','stage12'}:
                online.theme_picker.setCurrentIndex(online.theme_picker.findData('dark'))
                wait_for(lambda:online._theme=='dark' and javascript(window.page,"document.documentElement.dataset.theme==='dark'"),'Native theme picker sync')
                QTest.mouseClick(online.clear_button,Qt.MouseButton.LeftButton)
                assert online.queue.count()==0 and not online.tasks and online.active_task is None
                assert entry['path'].is_file() and video.read_bytes()==b'unchanged-video'
                assert not list(media.glob('*.srt'))
                result['checks'].append('native_theme_picker_sync_and_clear_queue_preserves_downloads_and_media')
            window.close();QTest.qWait(200);window=None
            result['passed']=True
    except Exception as error:
        result['failure']=f'{type(error).__name__}: {error}'
        if window is not None: window.grab().save(str(output.with_name(f'{prefix}-failure.png')))
        raise
    finally:
        if window is not None: window.close()
        QTest.qWait(200);server.shutdown();server.server_close()
        result['pythonErrors']=errors
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True),flush=True)
        faulthandler.cancel_dump_traceback_later()


if __name__=='__main__':main()
