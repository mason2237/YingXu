"""Stage 6 real WebEngine UI checks; adapter fixtures never touch user files."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_web_foundation import javascript, wait_for
from PySide6.QtCore import QMimeData, QPoint, Qt, QSettings, QTemporaryDir
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


def js(window, source):
    return javascript(window.page, source)


def click(window, selector):
    js(window, f"document.querySelector({json.dumps(selector)}).focus({{preventScroll:true}}); document.querySelector({json.dumps(selector)}).click(); true")
    QTest.qWait(190)


def native_click(window, selector):
    js(window, f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'nearest'}}); true")
    QTest.qWait(70)
    point = json.loads(js(window, f"JSON.stringify((() => {{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2];}})())"))
    QTest.mouseClick(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=QPoint(round(point[0]), round(point[1])))
    QTest.qWait(200)


def stats(window):
    return js(window, "JSON.stringify(globalThis.yingxuPreview?.stats())")


def snapshot(window):
    return json.loads(stats(window))


def capture(window, name):
    QTest.qWait(140)
    prefix=os.environ.get('YINGXU_CAPTURE_PREFIX','stage62_regression')
    stem = f'{prefix}_workspace' if name == 'workspace' else f'{prefix}_{name}'
    assert window.grab().save(str(ROOT / 'outputs' / f'{stem}.png'))


def choose(window, name):
    click(window, '#dataset-button')
    click(window, f'[data-scenario="{name}"]')
    wait_for(lambda: js(window, "document.documentElement.dataset.loading === 'false'"), f'{name} did not load')


def search(window, text):
    js(window, f"document.getElementById('search-input').value={json.dumps(text)}; document.getElementById('search-input').dispatchEvent(new Event('input',{{bubbles:true}})); true")
    QTest.qWait(180)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind,value,tb: (errors.append(str(value)),sys.__excepthook__(kind,value,tb))
    temporary = QTemporaryDir()
    appearance_settings = QSettings(str(Path(temporary.path()) / 'appearance.ini'), QSettings.Format.IniFormat)
    appearance_settings.setValue('appearance/v1', '{"theme":"light"}')
    window = WebWindow(preview=True, appearance_settings=appearance_settings)
    window.show()
    metrics = {}
    try:
        wait_for(lambda: window._loaded, 'Workspace HTML did not load')
        wait_for(lambda: js(window, "document.documentElement.dataset.ready === 'true'"), 'Workspace did not initialize')
        assert snapshot(window)['total'] == 12
        assert set(window.channel.registeredObjects()) == {'appearance'}
        assert window.bridge.service.job is None
        assert not window.page.console_errors, window.page.console_errors
        wait_for(lambda: snapshot(window)['effects']['glassMode'] == 'webgl2', 'Original Lens did not activate')
        assert snapshot(window)['effects']['origin']['commit'] == '7a424c93b9be13cf835b91ea67495fec2ec0584e'
        capture(window, 'workspace')
        click(window, '.path-details summary')
        old_clipboard = QMimeData()
        for fmt in app.clipboard().mimeData().formats():
            old_clipboard.setData(fmt, app.clipboard().mimeData().data(fmt))
        try:
            native_click(window, '.path-details button')
            assert app.clipboard().text() == js(window, "document.querySelector('.detail-video').textContent")
        finally:
            app.clipboard().setMimeData(old_clipboard)
        js(window, "document.querySelector('[data-filter=all]').focus();true")
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Right)
        QTest.qWait(120)
        assert snapshot(window)['total'] == 6
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Right)
        QTest.qWait(120)
        assert snapshot(window)['selectedId'] == 'video-3'
        click(window, '[data-filter="需确认"]')
        assert snapshot(window)['selectedId'] == 'video-3'
        click(window, '.detail-section-title button')
        assert js(window, "document.getElementById('candidate-dialog').open")
        assert js(window, "document.querySelectorAll('.candidate-card').length") == 3
        capture(window, 'candidates')
        click(window, '.candidate-card.recommended button')
        wait_for(lambda: not js(window, "document.getElementById('candidate-dialog').open"), 'Candidate modal did not close')
        QTest.qWait(40)
        assert js(window, "document.activeElement.id") == 'file-list'
        assert '人工指定' in js(window, "document.getElementById('inspector-content').textContent")
        assert snapshot(window)['total'] == 1
        click(window, '.detail-actions .primary')
        assert snapshot(window)['total'] == 0
        click(window, '[data-filter="all"]')
        click(window, '[data-row-id="video-3"]')
        assert '82%' in js(window, "document.querySelector('[data-row-id=\"video-3\"]').textContent")
        click(window, '.detail-actions .secondary:last-child')
        assert '已跳过' in js(window, "document.getElementById('inspector-content').textContent")
        click(window, '.detail-actions .secondary:last-child')
        assert '已匹配' in js(window, "document.getElementById('inspector-content').textContent")
        js(window, "const input=document.getElementById('search-input'); input.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true})); input.value='导演'; input.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true})); true")
        QTest.qWait(180)
        assert snapshot(window)['total'] == 12
        js(window, "document.getElementById('search-input').dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'导演'})); true")
        QTest.qWait(100)
        assert snapshot(window)['total'] == 1
        search(window, '导演特别')
        assert snapshot(window)['total'] == 1 and snapshot(window)['selectedId'] == 'video-8'
        search(window, 'does-not-exist')
        assert not js(window, "document.getElementById('empty-state').hidden")
        click(window, '#empty-action')
        assert snapshot(window)['total'] == 12
        selected = snapshot(window)['selectedId']
        click(window, '#sort-score')
        assert snapshot(window)['selectedId'] == selected
        click(window, '#preview-button')
        assert js(window, "document.getElementById('preview-dialog').open")
        assert not js(window, "document.getElementById('preview-warning').hidden")
        click(window, '#preview-ack')
        assert js(window, "document.getElementById('execute-button').disabled")
        capture(window, 'preview')
        click(window, '#preview-dialog [data-close]')
        click(window, '#history-button')
        assert '18' in js(window, "document.getElementById('history-content').textContent")
        capture(window, 'history')
        click(window, '#history-dialog [data-close]')
        window.resize(1000, 700)
        QTest.qWait(150)
        assert js(window, "document.documentElement.scrollWidth <= innerWidth")
        click(window, '#detail-toggle')
        assert js(window, "getComputedStyle(document.getElementById('inspector')).display !== 'none'")
        assert js(window, "document.getElementById('inspector-actions').getBoundingClientRect().bottom <= document.getElementById('inspector').getBoundingClientRect().bottom")
        capture(window, 'narrow')
        click(window, '#close-details')
        window.resize(900, 620)
        QTest.qWait(120)
        assert js(window, "document.documentElement.scrollWidth <= innerWidth")
        capture(window, 'minimum')
        click(window, '#preview-button')
        assert js(window, "document.getElementById('execute-button').getBoundingClientRect().bottom < innerHeight")
        capture(window, 'preview_minimum')
        click(window, '#preview-dialog [data-close]')
        window.resize(1280, 860)
        window.showMaximized()
        QTest.qWait(200)
        assert js(window, "document.documentElement.scrollWidth <= innerWidth")
        capture(window, 'maximized')
        window.showNormal()
        window.resize(1280, 860)
        choose(window, 'large')
        assert snapshot(window)['total'] == 10000
        assert snapshot(window)['renderedRows'] <= 30
        js(window, "document.getElementById('file-list').focus(); true")
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_End)
        QTest.qWait(180)
        assert js(window, "Number(document.querySelector('#list-items .file-row:last-child').getAttribute('aria-rowindex'))") == 10000
        metrics['large'] = snapshot(window)
        metrics['heapBytes'] = js(window, "performance.memory?.usedJSHeapSize || null")
        capture(window, 'large')
        started = time.monotonic()
        search(window, 'S01E9999')
        assert snapshot(window)['total'] == 1 and snapshot(window)['selectedId'] == 'video-9999'
        metrics['searchObservedMs'] = round((time.monotonic()-started)*1000, 1)
        choose(window, 'empty')
        assert snapshot(window)['total'] == 0
        capture(window, 'empty')
        choose(window, 'no-subs')
        assert snapshot(window)['total'] == 12 and js(window, "document.getElementById('preview-button').disabled")
        capture(window, 'no_subtitles')
        choose(window, 'error')
        assert '暂时无法读取' in js(window, "document.getElementById('empty-title').textContent")
        capture(window, 'error')
        choose(window, 'matched')
        click(window, '#appearance-button')
        capture(window, 'appearance')
        click(window, '#glass-setting')
        assert not snapshot(window)['effects']['glassEnabled']
        click(window, '#particle-setting')
        assert not snapshot(window)['effects']['particleRunning']
        click(window, '#motion-setting')
        assert snapshot(window)['effects']['reduced']
        assert js(window, "document.getElementById('particle-preview').disabled")
        click(window, '#appearance-dialog [data-close]')
        wait_for(lambda: not snapshot(window)['effects']['glassRunning'], 'Plain material did not settle')
        frames = snapshot(window)['effects']['particleFrames']
        glass_frames = snapshot(window)['effects']['glassFrames']
        QTest.qWait(800)
        assert snapshot(window)['effects']['particleFrames'] == frames
        assert snapshot(window)['effects']['glassFrames'] == glass_frames
        assert not snapshot(window)['effects']['glassRunning']
        click(window, '#appearance-button')
        click(window, '#motion-setting')
        click(window, '#glass-setting')
        click(window, '#particle-setting')
        click(window, '#appearance-dialog [data-close]')
        native_click(window, '.folder-copy')
        QTest.qWait(700)
        assert not snapshot(window)['effects']['glassRunning']
        assert not snapshot(window)['effects']['particleRunning']
        idle_frames = snapshot(window)['effects']['glassFrames']
        QTest.qWait(250)
        assert snapshot(window)['effects']['glassFrames'] == idle_frames
        click(window, '#appearance-button')
        click(window, '#particle-preview')
        assert snapshot(window)['effects']['particleRunning']
        window.showMinimized()
        QTest.qWait(180)
        assert js(window, "document.hidden")
        assert not snapshot(window)['effects']['particleRunning']
        window.showNormal()
        QTest.qWait(180)
        click(window, '#appearance-dialog [data-close]')
        # Ask WebGL to lose a real context, then verify upstream recovery.
        js(window, "document.querySelector('.workspace-lens-stage canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext();true")
        QTest.qWait(250)
        wait_for(lambda: js(window, "document.querySelector('.workspace-lens-stage').classList.contains('webgl-ready') && !document.querySelector('.workspace-lens-stage canvas').getContext('webgl2').isContextLost()"), 'Upstream context recovery failed')
        click(window, '#appearance-button')
        click(window, '#glass-setting')
        assert '玻璃效果已关闭' in js(window, "document.getElementById('effect-status').textContent")
        capture(window, 'fallback')
        click(window, '#appearance-dialog [data-close]')
        window.reload_page()
        wait_for(lambda: window._loaded and js(window, "document.documentElement.dataset.ready === 'true'"), 'Preview refresh failed')
        assert snapshot(window)['total'] == 12
        assert set(window.channel.registeredObjects()) == {'appearance'}
        assert not window.page.console_errors, window.page.console_errors
        assert not errors, errors
        assert not snapshot(window)['effects']['glassEnabled'], 'Reload lost saved appearance'
        print(json.dumps({'result':'PASS','metrics':metrics,'safety':'explicit fixture page; appearance-only QWebChannel'},ensure_ascii=False))
    finally:
        window.close()
        QTest.qWait(180)
