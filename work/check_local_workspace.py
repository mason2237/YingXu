"""Focused real Web workspace flow; media/history/settings/export are disposable.

The actual Qt WebEngine page calls the published bridge through DOM controls.
Native pickers are patched to choose only our fixture directory/export path.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore
from yingxu.core import ScanCancelled
from yingxu.web_ui.window import WebWindow


def wait_for(check,message,timeout=20):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        if check():return
        QTest.qWait(30)
    raise AssertionError(message)


def js(window,source):
    values = [];window.page.runJavaScript(source,lambda value:values.append(value))
    wait_for(lambda:bool(values),'JS callback timeout',5)
    return values[0]


def click(window,identifier):
    assert js(window,f"Boolean(document.getElementById({json.dumps(identifier)}))"),identifier
    js(window,f"document.getElementById({json.dumps(identifier)}).click();true")


def ready(window):
    return js(window,"document.documentElement.dataset.ready === 'true' && document.documentElement.dataset.loading === 'false'")


def settled(window):
    return not window.bridge.service.busy and ready(window)


def files(folder):
    return {str(path.relative_to(folder)):path.read_bytes() for path in folder.rglob('*') if path.is_file()}


def capture(window,name):
    QTest.qWait(260)
    assert window.grab().save(str(ROOT/'outputs'/f'stage7_{name}.png'))


if __name__ == '__main__':
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    class Checks(list):
        def append(self,value):
            super().append(value);print('PASS: '+value,flush=True)
    checks = Checks();opened = [];errors = []
    sys.excepthook = lambda kind,value,tb:(errors.append(str(value)),sys.__excepthook__(kind,value,tb))
    with tempfile.TemporaryDirectory(prefix='stage7-e2e-',dir=ROOT/'work'/'test-results') as directory:
        root = Path(directory);media = root/"映序剧集 中文 & '测试'";media.mkdir();extras = media/'其他候选';extras.mkdir()
        for number in range(1,4):
            (media/f'映序.S01E{number:02}.1080p.mkv').write_bytes(f'video-{number}'.encode())
            (media/f'映序.S01E{number:02}.chs.srt').write_bytes(f'字幕原文 {number}'.encode())
        for number in range(1,9): (extras/f'其他.S02E{number:02}.en.srt').write_bytes(f'other-{number}'.encode())
        original = files(media);report = root/'整理记录.json'
        history = HistoryStore(root/'history'/'history.jsonl')
        settings = QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
        print('Creating real workspace window',flush=True)
        window = WebWindow(appearance_settings=settings,history=history)
        service = window.bridge.service
        with patch('yingxu.web_ui.window.QFileDialog.getExistingDirectory',return_value=str(media)),patch('yingxu.web_ui.window.QFileDialog.getSaveFileName',return_value=(str(report),'JSON')),patch('yingxu.web_ui.window.QDesktopServices.openUrl',side_effect=lambda url:opened.append(url.toLocalFile()) or True):
            window.show();print('Waiting for local page',flush=True)
            try:
                wait_for(lambda:window._loaded and ready(window),'Local workspace did not start')
                wait_for(lambda:js(window,"!document.getElementById('theme-quick').disabled"),'Theme channel missing')
                js(window,"document.getElementById('theme-quick').value='light';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.documentElement.dataset.theme === 'light'"),'Light theme did not apply')
                assert set(window.channel.registeredObjects()) == {'bridge','appearance'}
                assert js(window,"typeof yingxuPreview === 'undefined' && !document.getElementById('dataset-dialog')")
                assert not service.data and files(media) == original
                checks.append('real entry without fixtures; empty state')
                click(window,'dataset-button')
                wait_for(lambda:service.data is not None and settled(window) and js(window,"document.querySelectorAll('#list-items .file-row').length === 3"),'Folder selection / real scan did not render')
                assert len(service.data.review.subtitles) == 11
                assert files(media) == original
                checks.append('native folder selection; real recursive scan; read-only')
                click(window,'scan-options-button');assert js(window,"document.getElementById('scan-options-dialog').open")
                assert js(window,"document.getElementById('recursive-setting').checked && !document.getElementById('move-setting').checked")
                js(window,"document.querySelector('#scan-options-dialog [data-close]').click();true")
                wait_for(lambda:not js(window,"document.getElementById('scan-options-dialog').open"),'Options did not close')
                click(window,'open-folder-button');wait_for(lambda:len(opened) == 1,'Folder reveal did not call native opener')
                assert Path(opened[0]) == media
                js(window,"document.querySelector('#inspector-content .path-details summary').click();[...document.querySelectorAll('#inspector-content button')].find(b=>b.textContent.includes('复制视频名称')).click();true")
                wait_for(lambda:QApplication.clipboard().text() == service.data.rows[0]['video']['name'],'Native name copy failed')
                checks.append('real options; registered folder reveal; native clipboard')
                first = service.data.rows[0];source_name = first['subtitles'][0]['name'];old_revision = service.data.revision
                js(window,"document.querySelector('#inspector-content .subtitle-detail button').click();true")
                wait_for(lambda:service.data.revision>old_revision and settled(window) and js(window,"document.querySelectorAll('#inspector-content .subtitle-detail').length === 0"),'Remove association failed')
                js(window,"document.querySelector('#inspector-content .detail-section-title button').click();true")
                wait_for(lambda:settled(window) and js(window,"document.getElementById('candidate-dialog').open"),'Real candidates did not open')
                assert js(window,"document.querySelectorAll('#candidate-list .candidate-card').length <= 6")
                click(window,'candidate-next');wait_for(lambda:settled(window) and js(window,"document.getElementById('candidate-page').textContent.includes('第 2')"),'Candidate paging failed')
                click(window,'candidate-previous');wait_for(lambda:settled(window) and js(window,"document.getElementById('candidate-page').textContent.includes('第 1')"),'Candidate previous page failed')
                name = json.dumps(source_name,ensure_ascii=True)
                assert js(window,f"Boolean([...document.querySelectorAll('#candidate-list .candidate-card')].find(card=>card.querySelector('h3').textContent==={name}))")
                js(window,f"[...document.querySelectorAll('#candidate-list .candidate-card')].find(card=>card.querySelector('h3').textContent==={name}).querySelector('button').click();true")
                wait_for(lambda:settled(window) and service.data.rows[0]['state'] == '需确认' and not js(window,"document.getElementById('candidate-dialog').open"),'Manual assignment was not marked pending')
                js(window,"document.querySelector('#inspector-actions .detail-actions button').click();true")
                wait_for(lambda:settled(window) and service.data.rows[0]['subtitles'][0]['confirmed'],'Manual confirmation failed')
                assert js(window,"document.getElementById('file-list').getAttribute('aria-busy') === 'false' && getComputedStyle(document.getElementById('file-list')).opacity === '1'")
                position = json.loads(js(window,"JSON.stringify((()=>{const r=document.querySelectorAll('#list-items .file-row')[1].getBoundingClientRect();return {x:r.x+100,y:r.y+r.height/2}})())"))
                QTest.mouseClick(window.view.focusProxy() or window.view,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(position['x']),round(position['y'])))
                wait_for(lambda:js(window,"document.querySelectorAll('#list-items .file-row')[1].getAttribute('aria-selected') === 'true'"),'Rows remained blocked after review')
                assert files(media) == original
                checks.append('remove/reassign; paged candidates; explicit manual confirmation')
                js(window,"document.getElementById('search-input').value='S01E02';document.getElementById('search-input').dispatchEvent(new Event('input',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.getElementById('list-count').textContent.startsWith('1 /')"),'Real search failed')
                js(window,"document.getElementById('search-input').value='';document.getElementById('search-input').dispatchEvent(new Event('input',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.getElementById('list-count').textContent.startsWith('3 /')"),'Search clear failed')
                click(window,'sort-score');wait_for(lambda:js(window,"document.querySelectorAll('#list-items .file-row').length === 3"),'Sorting failed')
                capture(window,'workspace_light')
                window.resize(940,700);QTest.qWait(200)
                assert js(window,"document.documentElement.scrollWidth <= innerWidth && document.getElementById('scan-button').getBoundingClientRect().right <= document.getElementById('glass-toolbar').getBoundingClientRect().right")
                js(window,"document.getElementById('theme-quick').value='dark';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.documentElement.dataset.theme === 'dark'"),'Dark theme did not apply')
                capture(window,'workspace_narrow_dark');window.resize(1280,860)
                js(window,"document.getElementById('theme-quick').value='light';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.documentElement.dataset.theme === 'light'"),'Theme restore failed')
                checks.append('review releases list interaction; native row click; narrow layout; both themes')
                click(window,'preview-button');wait_for(lambda:js(window,"document.getElementById('preview-dialog').open"),'Preview did not open')
                assert js(window,"document.getElementById('execute-button').disabled && !document.getElementById('preview-ack').checked")
                assert service.snapshot and service.ticket
                changes = tuple(service.snapshot.changes);assert len(changes) == 3
                assert files(media) == original
                capture(window,'preview_light')
                js(window,"document.getElementById('preview-ack').click();true")
                wait_for(lambda:js(window,"!document.getElementById('execute-button').disabled"),'Acknowledgment did not enable execute')
                js(window,"document.getElementById('execute-button').click();document.getElementById('execute-button').click();true")
                wait_for(lambda:settled(window) and js(window,"document.getElementById('history-dialog').open"),'Execution did not display results')
                assert len(history.recent()) == 1
                for change in changes:
                    assert not change.source.exists()
                    assert change.target.read_bytes() == original[str(change.source.relative_to(media))]
                assert all((media/f'映序.S01E{number:02}.1080p.mkv').read_bytes() == f'video-{number}'.encode() for number in range(1,4))
                assert service.record_page(service.last_result_id)['success'] == 3
                checks.append('frozen preview; acknowledgment required; duplicate click applies once; correct results')
                capture(window,'results_light')
                click(window,'export-record');wait_for(lambda:report.exists() and settled(window) and js(window,"!document.getElementById('export-record').disabled"),'Record export failed')
                exported = report.read_bytes();assert json.loads(exported)['run_id'] == service.last_result_id
                click(window,'export-record')
                wait_for(lambda:service.job['kind'] == 'export' and service.job['status'] == 'failed' and settled(window),'Existing export target was not rejected')
                assert report.read_bytes() == exported
                checks.append('real export; existing record file never overwritten')
                js(window,"document.querySelector('#history-dialog [data-close]').click();true")
                wait_for(lambda:not js(window,"document.getElementById('history-dialog').open"),'Result close failed')
                window.reload_page();wait_for(lambda:ready(window),'Page reload did not recover')
                wait_for(lambda:js(window,"document.getElementById('history-dialog').open"),'Reload lost completed result')
                assert len(history.recent()) == 1
                assert not window.page.console_errors,window.page.console_errors
                assert not errors,errors
                checks.append('page reload recovers result without replaying file operations')
                js(window,"document.querySelector('#history-dialog [data-close]').click();true")
                wait_for(lambda:not js(window,"document.getElementById('history-dialog').open"),'Restored result did not close')
                click(window,'history-button')
                wait_for(lambda:settled(window) and js(window,"document.getElementById('history-dialog').open && document.querySelectorAll('#history-record option').length === 1"),'Local history list did not load')
                assert js(window,"document.querySelectorAll('#history-content .history-item').length === 3")
                js(window,"document.querySelector('#history-dialog [data-close]').click();true")
                wait_for(lambda:not js(window,"document.getElementById('history-dialog').open"),'History list did not close')
                def held_scan(folder,recursive,**options):
                    deadline = time.monotonic()+5
                    while time.monotonic()<deadline and not options['should_stop']():time.sleep(.01)
                    raise ScanCancelled()
                with patch('yingxu.web_ui.workspace_service.collect_media',side_effect=held_scan):
                    click(window,'scan-button')
                    wait_for(lambda:service.worker is not None and js(window,"!document.getElementById('stop-task').hidden"),'Cancel control did not appear')
                    click(window,'stop-task')
                    wait_for(lambda:service.job['status'] == 'cancelled' and settled(window),'Cancel did not finish')
                assert len(history.recent()) == 1
                checks.append('real cancel button; cooperative scan stop; no extra file operations')
                print(json.dumps({'result':'PASS','checks':checks,'consoleErrors':window.page.console_errors},ensure_ascii=False))
            except Exception:
                print(json.dumps({'result':'FAIL','checks':checks,'job':service.job,'consoleErrors':window.page.console_errors},ensure_ascii=False,default=str),flush=True)
                raise
            finally:
                window.close();wait_for(lambda:not window.isVisible(),'Test window did not close');QTest.qWait(200)
