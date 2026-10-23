"""6.3b: one focused real-window check, temporary settings and fixture data only."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from check_theme_preview import ROOT, ready, js, data, theme, click
from check_web_foundation import wait_for
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


def capture(window, name):
    QTest.qWait(250)  # Let the short entrance and native compositor finish.
    assert window.grab().save(str(ROOT / 'outputs' / f'stage63b_{name}.png'))


def command(window, text):
    QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    wait_for(lambda: js(window, "document.getElementById('command-dialog').open"), 'Command palette did not open')
    js(window, f"document.getElementById('command-search').value={json.dumps(text)};document.getElementById('command-search').dispatchEvent(new Event('input'));true")


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    with TemporaryDirectory(prefix='yingxu-feedback-') as directory:
        settings = QSettings(str(Path(directory) / 'appearance.ini'), QSettings.Format.IniFormat)
        settings.setValue('appearance/v1', '{"theme":"light"}')
        window = WebWindow(preview=True, appearance_settings=settings); window.show(); window.activateWindow()
        try:
            ready(window)
            command(window, ''); capture(window, 'commands_light')
            assert js(window, '!yingxuPreview.stats().effects.mist.running')
            js(window, "const field=document.getElementById('command-search');field.value='预览';field.dispatchEvent(new Event('input'));field.dispatchEvent(new CompositionEvent('compositionstart'));field.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,isComposing:true}));true")
            assert js(window, "!document.getElementById('preview-dialog').open")
            js(window, "document.getElementById('command-search').dispatchEvent(new CompositionEvent('compositionend'));true")
            QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Return)
            wait_for(lambda: js(window, "document.getElementById('preview-dialog').open"), 'Command did not open real preview')
            assert js(window, "document.getElementById('execute-button').disabled && document.querySelector('[data-workflow=\"3\"]').getAttribute('aria-current')==='step'")
            click(window, '#preview-dialog [data-close]')
            command(window, '候选'); QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Return)
            wait_for(lambda: js(window, "document.getElementById('candidate-dialog').open"), 'Candidate command failed')
            capture(window, 'candidates_light')
            js(window, "globalThis.__noticeParents=[];document.getElementById('toast').addEventListener('beforetoggle',event=>{if(event.newState==='open')__noticeParents.push(document.getElementById('toast').closest('dialog')?.id||'body');});true")
            click(window, '.candidate-card:first-child button')
            assert js(window, "document.getElementById('toast').dataset.tone==='success' && document.getElementById('toast').matches(':popover-open') && __noticeParents.includes('candidate-dialog')")
            # QtTest did not hit this native popover by mouse coordinates.
            # Check its pointer handler and keyboard focus directly instead.
            js(window, "document.getElementById('toast').dispatchEvent(new PointerEvent('pointerenter'));true")
            pause = data(window, "({paused:yingxuPreview.stats().notice.paused,meter:document.querySelector('[data-notice-timer]').getAnimations()[0]?.playState})")
            assert pause['paused'] and pause['meter'] == 'paused', pause
            js(window, "document.getElementById('toast-close').focus();document.getElementById('toast').dispatchEvent(new PointerEvent('pointerleave'));true")
            assert js(window, 'yingxuPreview.stats().notice.paused')
            capture(window, 'notice_light')
            click(window, '#toast-close')
            click(window, '#history-button'); capture(window, 'results_light')
            assert js(window, "document.querySelectorAll('.history-item').length===3 && document.querySelectorAll('.result-distribution span').length===3")
            click(window, '#history-dialog [data-close]')
            js(window, "globalThis.__progress=[];new MutationObserver(()=>__progress.push(Number(document.querySelector('#loading-progress [role=progressbar]').getAttribute('aria-valuenow')))).observe(document.querySelector('#loading-progress [role=progressbar]'),{attributes:true,attributeFilter:['aria-valuenow']});true")
            click(window, '#dataset-button'); click(window, '[data-scenario=large]')
            wait_for(lambda: js(window, "yingxuPreview.stats().total===10000 && document.getElementById('loading-state').hidden"), 'Large fixture load failed')
            assert js(window, '__progress.length>0 && __progress.every(value=>value>=0&&value<=100) && __progress.includes(100)')
            js(window, "document.getElementById('search-input').value='不存在的字幕XYZ';document.getElementById('search-input').dispatchEvent(new Event('input'));true")
            wait_for(lambda: js(window, "document.getElementById('empty-state').dataset.state==='filtered' && !document.getElementById('empty-state').hidden"), 'Filtered empty state failed')
            click(window, '#empty-action')
            wait_for(lambda: js(window, 'yingxuPreview.stats().total===10000'), 'Clear filter failed')
            theme(window, 'dark');window.resize(900,620);QTest.qWait(120)
            click(window, '#detail-toggle')
            assert js(window, "document.getElementById('inspector-dialog').open && document.getElementById('inspector').parentElement.id==='inspector-dialog' && document.documentElement.scrollWidth<=innerWidth")
            QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Tab)
            assert js(window, "Boolean(document.activeElement.closest('#inspector-dialog'))")
            capture(window, 'drawer_dark')
            QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Escape);QTest.qWait(180)
            assert js(window, "!document.getElementById('inspector-dialog').open && document.getElementById('inspector').parentElement.id==='review-body'")
            js(window, "document.getElementById('appearance-button').focus();true");QTest.qWait(220)
            assert js(window, "document.getElementById('workspace-tooltip').matches(':popover-open')")
            click(window, '#appearance-button');click(window, '#motion-setting');click(window, '#appearance-dialog [data-close]')
            command(window, '外观');QTest.qWait(50)
            assert js(window, "document.getElementById('command-dialog').getAnimations().every(animation=>animation.playState==='finished') && !yingxuPreview.stats().effects.mist.running")
            assert set(window.channel.registeredObjects()) == {'appearance'}
            assert not window.page.console_errors, window.page.console_errors
            print(json.dumps({'result':'PASS','progressUpdates':data(window,'__progress.length'),'consoleErrors':window.page.console_errors,'nativeInterfaces':list(window.channel.registeredObjects())},ensure_ascii=False),flush=True)
        finally:
            window.close();QTest.qWait(150)
