"""Focused optical/jelly/progress check, using only disposable real media."""
import json
from pathlib import Path
import sys
import tempfile
import time
from threading import Event
from unittest.mock import patch

from check_local_workspace import ROOT, js, wait_for, click, ready, settled, files
from PySide6.QtCore import QSettings, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore, _move_without_overwrite
from yingxu.web_ui.window import WebWindow


def capture(window,name):
    QTest.qWait(180);assert window.grab().save(str(ROOT/'outputs'/f'stage8a_{name}.png'))


def point(window,identifier):
    position = json.loads(js(window,f"JSON.stringify((()=>{{const r=document.getElementById({json.dumps(identifier)}).getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})())"))
    return QPoint(round(position['x']),round(position['y']))


def pose(window,identifier):
    return json.loads(js(window,f"JSON.stringify((()=>{{const el=document.getElementById({json.dumps(identifier)}),m=new DOMMatrix(getComputedStyle(el).transform);return {{x:m.e,y:m.f,held:el.dataset.held==='true'}}}})())"))


def drag(window,identifier,*,reduced=False,capture_name=None):
    widget = window.view.focusProxy() or window.view;start = point(window,identifier)
    sequence = 0
    def record():
        nonlocal sequence
        if capture_name != 'jelly_drag':return
        left=max(0,start.x()-150);top=max(0,start.y()-50)
        image=window.grab().copy(QRect(left,top,min(300,window.width()-left),min(110,window.height()-top)))
        assert image.save(str(ROOT/'outputs'/f'stage8a_jelly_frame_{sequence:02}.png'));sequence+=1
    QTest.mouseMove(widget,start);QTest.qWait(40)
    record()
    QTest.mousePress(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start);QTest.qWait(70)
    record()
    for offset in (QPoint(-18,-4),QPoint(-43,-10),QPoint(-68,-16)):QTest.mouseMove(widget,start+offset,30);QTest.qWait(60);record()
    value = pose(window,identifier)
    if reduced:assert abs(value['x'])<.5 and abs(value['y'])<.5,value
    else:assert abs(value['x'])+abs(value['y'])>3 and value['held'],value
    if capture_name:capture(window,capture_name)
    QTest.mouseRelease(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start+QPoint(-68,-16))
    for frame in range(6):QTest.qWait(60);record()
    wait_for(lambda:abs(pose(window,identifier)['x'])+abs(pose(window,identifier)['y'])<.7,'Spring did not settle')
    QTest.qWait(430)
    return value


def coverage(window):
    wait_for(lambda:js(window,"[...document.querySelectorAll('button')].every(b=>b.classList.contains('liquid-button'))"),'A dynamic button missed glass coverage')
    return json.loads(js(window,"JSON.stringify({buttons:document.querySelectorAll('button').length,gpuButtons:document.querySelectorAll('button[data-liquid-renderer=webgl]').length,glassCanvases:document.querySelectorAll('canvas.lg-canvas').length})"))


if __name__ == '__main__':
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);checks = [];release = Event()
    def passed(message):checks.append(message);print('PASS: '+message,flush=True)
    with tempfile.TemporaryDirectory(prefix='glass-controls-',dir=ROOT/'work'/'test-results') as directory:
        root = Path(directory);media = root/'液态按钮 中文测试';media.mkdir()
        for number in range(1,4):
            (media/f'映序.S01E{number:02}.1080p.mkv').write_bytes(b'video')
            (media/f'映序.S01E{number:02}.chs.srt').write_bytes(f'subtitle-{number}'.encode())
            (media/f'其他.S02E{number:02}.en.srt').write_bytes(b'candidate')
        before = files(media);settings = QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
        history = HistoryStore(root/'history.jsonl');window = WebWindow(workspace=True,appearance_settings=settings,history=history);service = window.bridge.service
        with patch('yingxu.web_ui.window.QFileDialog.getExistingDirectory',return_value=str(media)):
            window.show()
            try:
                wait_for(lambda:window._loaded and ready(window),'Workspace did not become ready')
                wait_for(lambda:js(window,"!document.getElementById('theme-quick').disabled"),'Theme did not connect')
                js(window,"document.getElementById('theme-quick').value='light';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.documentElement.dataset.theme==='light'"),'Light theme missing')
                QTest.qWait(260)
                initial = coverage(window);assert initial['buttons']>30,initial
                drag(window,'command-button',capture_name='jelly_drag');assert not js(window,"document.getElementById('command-dialog').open")
                QTest.mouseClick(window.view.focusProxy() or window.view,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point(window,'command-button'))
                wait_for(lambda:js(window,"document.getElementById('command-dialog').open"),'Native tap stopped working')
                coverage(window);js(window,"document.querySelector('#command-dialog [data-close]').click();true")
                wait_for(lambda:not js(window,"document.getElementById('command-dialog').open"),'Commands did not close')
                passed('all initial/dynamic buttons covered; native jelly drag rebounds and suppresses click; native tap works')
                click(window,'dataset-button');wait_for(lambda:service.data is not None and settled(window),'Real fixture scan failed')
                for iteration in range(3):
                    js(window,"document.querySelector('#inspector-content .detail-section-title button').click();true")
                    wait_for(lambda:js(window,"document.getElementById('candidate-dialog').open"),'Candidates missing')
                    info = coverage(window);assert info['glassCanvases']<=6,info
                    assert js(window,"document.querySelector('#candidate-dialog .dialog-footer').closest('.modal-liquid-dock')!==null")
                    if iteration == 0:capture(window,'candidate_glass')
                    js(window,"document.querySelector('#candidate-dialog [data-close]').click();true")
                    wait_for(lambda:not js(window,"document.getElementById('candidate-dialog').open"),'Candidate close failed')
                    if iteration == 1:
                        js(window,"document.getElementById('theme-quick').value='dark';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                        wait_for(lambda:js(window,"document.documentElement.dataset.theme==='dark'"),'Dark theme missing');QTest.qWait(260);capture(window,'workspace_dark')
                js(window,"document.getElementById('theme-quick').value='light';document.getElementById('theme-quick').dispatchEvent(new Event('change',{bubbles:true}));true")
                wait_for(lambda:js(window,"document.documentElement.dataset.theme==='light'"),'Light restore missing');QTest.qWait(260)
                capture(window,'workspace_light');passed('candidate buttons and reusable optical footer; canvas count bounded across repeated opens')
                click(window,'preview-button');wait_for(lambda:js(window,"document.getElementById('preview-dialog').open"),'Preview missing')
                js(window,"document.getElementById('preview-ack').click();true");wait_for(lambda:js(window,"!document.getElementById('execute-button').disabled"),'Ack failed')
                coverage(window);drag(window,'execute-button',capture_name='confirm_drag')
                assert service.last_result_id is None and service.worker is None and files(media) == before
                assert js(window,"document.getElementById('preview-dialog').open")
                passed('dragging enabled confirmation does not execute or modify any file')
                moved = 0
                def held_move(item):
                    global moved
                    if moved == 1:release.wait(12)
                    _move_without_overwrite(item);moved += 1
                with patch('yingxu.operations._move_without_overwrite',side_effect=held_move):
                    QTest.mouseClick(window.view.focusProxy() or window.view,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point(window,'execute-button'))
                    wait_for(lambda:service.worker is not None and service.job['done'] == 1,'Native confirm / real progress missing')
                    wait_for(lambda:js(window,"!document.getElementById('loading-progress').hidden && document.getElementById('loading-progress').classList.contains('webgl-ready')"),'Optical progress did not activate')
                    assert js(window,"document.querySelector('#loading-progress .lg-progress').dataset.wave==='true' && Number(document.querySelector('#loading-progress [role=progressbar]').getAttribute('aria-valuenow'))>30")
                    assert js(window,"document.querySelector('#loading-progress .lg-progress-track').getBoundingClientRect().height>=28")
                    capture(window,'real_progress');passed('original Lens wave/refraction displays actual 1 / 3 task progress')
                    click(window,'appearance-button');wait_for(lambda:js(window,"document.getElementById('appearance-dialog').open"),'Appearance missing')
                    js(window,"document.getElementById('motion-setting').checked=true;document.getElementById('motion-setting').dispatchEvent(new Event('change',{bubbles:true}));true")
                    wait_for(lambda:js(window,"document.documentElement.dataset.reduced==='true' && document.querySelector('#loading-progress .lg-progress').dataset.wave==='false'"),'Reduced motion did not disable wave')
                    js(window,"document.querySelector('#appearance-dialog [data-close]').click();true")
                    wait_for(lambda:not js(window,"document.getElementById('appearance-dialog').open"),'Appearance close failed')
                    drag(window,'command-button',reduced=True)
                    assert not js(window,"document.getElementById('command-dialog').open")
                    release.set();wait_for(lambda:settled(window) and service.last_result_id is not None,'Fixture execution did not finish')
                wait_for(lambda:js(window,"document.getElementById('history-dialog').open"),'Result missing')
                assert len(history.recent()) == 1 and service.record_page(service.last_result_id)['success'] == 3
                assert not window.page.console_errors,window.page.console_errors
                final = coverage(window);assert final['glassCanvases']<=6,final
                passed('reduced motion stops travel/wave but retains drag safety; normal click executes exactly one real batch')
                print(json.dumps({'result':'PASS','checks':checks,'initial':initial,'final':final,'consoleErrors':[]},ensure_ascii=False),flush=True)
            except Exception:
                print(json.dumps({'result':'FAIL','checks':checks,'job':service.job,'consoleErrors':window.page.console_errors},ensure_ascii=False,default=str),flush=True);raise
            finally:
                release.set();window.close();wait_for(lambda:not window.isVisible(),'Fixture window did not close');QTest.qWait(200)
