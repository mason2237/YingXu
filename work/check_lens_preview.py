"""Stage 6.1: real WebEngine optics/factory/lifecycle checks, without CUA."""
import json
import faulthandler
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_web_foundation import javascript, wait_for
from PySide6.QtCore import QPoint, Qt, QSettings, QTemporaryDir
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow


def js(window, source):
    return javascript(window.page, source)


def click(window, selector, delay=130):
    js(window, f'document.querySelector({json.dumps(selector)}).click(); true')
    QTest.qWait(delay)


def state(window):
    return json.loads(js(window, 'JSON.stringify(globalThis.yingxuEffectsLab?.stats())'))


def capture(window, name):
    QTest.qWait(130)
    assert window.grab().save(str(ROOT / 'outputs' / f'stage62_lab_{name}.png'))


def select(window, name):
    click(window, f'button[data-component="{name}"]')
    assert state(window)['active'] == name


def center(window, selector):
    point = json.loads(js(window, f'JSON.stringify((()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2];}})())'))
    return QPoint(round(point[0]), round(point[1]))


if __name__ == '__main__':
    faulthandler.dump_traceback_later(60)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind, value, tb: (errors.append(str(value)), sys.__excepthook__(kind, value, tb))
    temporary = QTemporaryDir()
    appearance_settings = QSettings(str(Path(temporary.path()) / 'appearance.ini'), QSettings.Format.IniFormat)
    appearance_settings.setValue('appearance/v1', '{"theme":"light"}')
    window = WebWindow(effects=True, appearance_settings=appearance_settings)
    window.show()
    metrics = {}
    try:
        print('CHECK: loading local effects page', flush=True)
        wait_for(lambda: window._loaded, 'Effects HTML failed')
        print('CHECK: HTML loaded; waiting for module', flush=True)
        wait_for(lambda: js(window, "document.documentElement.dataset.ready==='true'"), 'Effects module failed')
        print('CHECK: module initialized; waiting for compositors', flush=True)
        assert set(window.channel.registeredObjects()) == {'appearance'}
        assert window.bridge.service.job is None
        wait_for(lambda: all(entry['mode'] == 'webgl2' for entry in state(window)['comparisons']), 'Original compositors did not activate')
        print('CHECK: compositors ready', flush=True)
        QTest.qWait(900)
        capture(window, 'comparison')
        metrics['initial'] = state(window)
        click(window, '#original-stage .lg-button')
        assert '原版材质' in js(window, "document.getElementById('comparison-feedback').textContent")
        # The compositor actually changes pixels when lens geometry is removed.
        js(window, "globalThis.savedGeometry=[...document.querySelectorAll('#original-stage [data-glass]')].map(el=>[el,el.dataset.glass]); const c=document.querySelector('#original-stage canvas');const copy=document.createElement('canvas');copy.width=c.width;copy.height=c.height;copy.getContext('2d').drawImage(c,0,0);globalThis.beforePixels=copy.getContext('2d').getImageData(0,0,c.width,c.height).data; savedGeometry.forEach(([el])=>el.removeAttribute('data-glass'));window.dispatchEvent(new Event('resize'));true")
        QTest.qWait(450)
        metrics['changedPixels'] = js(window, "(()=>{const c=document.querySelector('#original-stage canvas'),copy=document.createElement('canvas');copy.width=c.width;copy.height=c.height;copy.getContext('2d').drawImage(c,0,0);const data=copy.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<data.length;i+=4)if(Math.abs(data[i]-beforePixels[i])+Math.abs(data[i+1]-beforePixels[i+1])+Math.abs(data[i+2]-beforePixels[i+2])>20)n++;return n;})()")
        assert metrics['changedPixels'] > 1000, metrics
        js(window, "savedGeometry.forEach(([el,kind])=>el.dataset.glass=kind);delete globalThis.beforePixels;delete globalThis.savedGeometry;window.dispatchEvent(new Event('resize'));document.getElementById('gallery').scrollIntoView();true")
        QTest.qWait(300)
        names = json.loads(js(window, "JSON.stringify([...document.querySelectorAll('#component-nav button')].map(button=>button.dataset.component))"))
        assert len(names) == 18
        for name in names:
            select(window, name)
            assert js(window, "document.getElementById('gallery-stage').children.length") >= 1
            click(window, '#demo-run')
            assert not window.page.console_errors, (name, window.page.console_errors)
        print('CHECK: 18 original factories passed', flush=True)
        assert js(window, "globalThis[Symbol.for('lens.viewport-gpu-budget.v1')].budget.clients.size") == 3
        select(window, 'drop-select')
        click(window, '#demo-run')
        assert state(window)['value'] == 'eng'
        click(window, '#demo-variant')
        assert js(window, "document.querySelector('.lg-drop-select').dataset.variant") == 'capsule'
        click(window, '#demo-variant')
        capture(window, 'drop_select')
        js(window, "document.querySelector('.lg-drop-option').focus();true")
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_End)
        QTest.qWait(150)
        assert state(window)['value'] == 'both'
        select(window, 'xy-slider')
        js(window, "document.querySelector('.lg-xy-pad').focus();true")
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_End)
        QTest.qWait(120)
        assert state(window)['value'] == {'x': 100, 'y': 100}
        capture(window, 'xy_lens')
        select(window, 'lens')
        point = center(window, '.lg-lens')
        QTest.mousePress(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(window.view.focusProxy(), point + QPoint(32, 12), delay=100)
        QTest.mouseRelease(window.view.focusProxy(), Qt.MouseButton.LeftButton, pos=point + QPoint(32, 12))
        QTest.qWait(700)
        metrics['freeLensPosition'] = js(window, "document.querySelector('.lg-lens').getAttribute('aria-valuetext')")
        assert metrics['freeLensPosition'] != 'X 50%, Y 50%'
        select(window, 'progress')
        click(window, '#demo-run')
        QTest.qWait(500)
        capture(window, 'progress')
        QTest.qWait(2600)
        assert state(window)['value'] == 100
        assert js(window, "document.querySelector('.lg-progress').dataset.motion") == 'off'
        select(window, 'menu')
        click(window, '#demo-run')
        assert not js(window, "document.querySelector('.lg-menu-popover').hidden")
        QTest.keyClick(window.view.focusProxy(), Qt.Key.Key_Escape)
        QTest.qWait(350)
        assert js(window, "document.querySelector('.lg-menu-popover').hidden")
        click(window, '#open-lens-dialog')
        wait_for(lambda: (state(window)['dialog'] or {}).get('mode') == 'webgl2', 'Top-layer compositor did not activate')
        capture(window, 'dialog')
        click(window, '#lens-dialog [data-close]')
        QTest.qWait(220)
        assert state(window)['dialog'] is None
        assert js(window, "globalThis[Symbol.for('lens.viewport-gpu-budget.v1')].budget.clients.size") == 3
        js(window, "document.getElementById('comparison').scrollIntoView();true")
        QTest.qWait(250)
        click(window, '#lab-enabled')
        assert all(entry['mode'] == 'fallback' for entry in state(window)['comparisons'])
        capture(window, 'fallback')
        click(window, '#lab-enabled')
        wait_for(lambda: all(entry['mode'] == 'webgl2' for entry in state(window)['comparisons']), 'Re-enable failed')
        click(window, '#lab-reduced')
        QTest.qWait(1700)
        baseline = [item['frames'] for item in state(window)['comparisons']]
        QTest.qWait(450)
        assert [item['frames'] for item in state(window)['comparisons']] == baseline
        metrics['idleFrames'] = baseline
        window.showMinimized()
        QTest.qWait(220)
        assert js(window, 'document.hidden')
        assert not any(item['running'] for item in state(window)['comparisons'])
        window.showNormal()
        QTest.qWait(280)
        window.resize(900, 650)
        QTest.qWait(250)
        assert js(window, 'document.documentElement.scrollWidth <= innerWidth')
        capture(window, 'narrow')
        # Simulate genuinely unavailable WebGL for a newly mounted instance.
        js(window, "globalThis.savedGetContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl2'?null:savedGetContext.call(this,kind,...args)};globalThis.failureReady=false;Promise.all([import('yingxu://app/js/components/lens-runtime.js'),import('yingxu://app/vendor/design-systems/lens/components.js')]).then(([{LensRuntime},{createComponent}])=>{globalThis.failureStage=document.createElement('div');failureStage.className='dialog-stage';document.body.append(failureStage);globalThis.failurePanel=createComponent('panel',{label:'兼容材质',motion:'none',children:['WebGL 不可用时，原版 CSS 材质与文字仍可用。']});failureStage.append(failurePanel.element);failureStage.scrollIntoView();globalThis.failureRuntime=new LensRuntime(failureStage);globalThis.failureReady=true;});true")
        wait_for(lambda: js(window, 'globalThis.failureReady'), 'Unavailable test did not mount')
        QTest.qWait(180)
        assert js(window, 'failureRuntime.stats().mode') == 'fallback'
        capture(window, 'unavailable')
        js(window, "HTMLCanvasElement.prototype.getContext=savedGetContext;delete globalThis.savedGetContext;failureRuntime.destroy();failurePanel.destroy();failureStage.remove();document.getElementById('gallery').scrollIntoView();true")
        wait_for(lambda: state(window)['gallery']['mode'] == 'webgl2', 'Viewport context resume failed')
        QTest.qWait(1700)
        gallery_frames = state(window)['gallery']['frames']
        QTest.qWait(350)
        assert state(window)['gallery']['frames'] == gallery_frames, 'Gallery did not become idle'
        assert not state(window)['gallery']['running']
        metrics['final'] = state(window)
        js(window, "window.dispatchEvent(new Event('pagehide'));true")
        assert state(window)['destroyed']
        assert js(window, "globalThis[Symbol.for('lens.viewport-gpu-budget.v1')].budget.clients.size") == 0
        assert not errors, errors
        assert not window.page.console_errors, window.page.console_errors
        print(json.dumps({'result': 'PASS', 'components': names, 'metrics': metrics, 'computerControlCalls': 0}, ensure_ascii=False))
    finally:
        faulthandler.cancel_dump_traceback_later()
        window.close()
        QTest.qWait(150)
