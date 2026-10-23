"""6.3a: real vapor/action optics, bounded rendering and original behavior."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from check_theme_preview import ready, js, data, theme, click, select, ROOT
from check_web_foundation import wait_for
from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineScript
from yingxu.web_ui.window import WebWindow


def stats(window): return data(window, 'globalThis.yingxuPreview.stats().effects')


def capture(window, name):
    QTest.qWait(100)
    assert window.grab().save(str(ROOT / 'outputs' / f'stage63a_{name}.png'))


def move(window, selector, x=.5, y=.5):
    values = data(window, f"(() => {{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return [r.x+r.width*{x},r.y+r.height*{y}];}})()")
    QTest.mouseMove(window.view.focusProxy(), QPoint(round(values[0]),round(values[1])))
    QTest.qWait(100)
    return QPoint(round(values[0]),round(values[1]))


def changed(first, second):
    a,b=first.toImage(),second.toImage()
    return sum(a.pixel(x,y)!=b.pixel(x,y) for y in range(0,a.height(),2) for x in range(0,a.width(),2))


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind,value,tb: (errors.append(str(value)),sys.__excepthook__(kind,value,tb))
    with TemporaryDirectory(prefix='yingxu-materials-') as directory:
        settings=QSettings(str(Path(directory)/'appearance.ini'),QSettings.Format.IniFormat)
        settings.setValue('appearance/v1','{"theme":"light"}')
        window=WebWindow(preview=True,appearance_settings=settings);window.show()
        metrics={}
        try:
            ready(window)
            wait_for(lambda: stats(window)['mist']['mode']=='webgl2' and all(item['mode']=='webgl2' for item in stats(window)['actions']), 'New materials did not initialize')
            assert [item['buttons'] for item in stats(window)['actions']]==[2,1]
            print('CHECK: vapor and three original Lens action surfaces',flush=True)
            assert js(window,"document.querySelectorAll('.list-mist').length===1 && document.querySelectorAll('.liquid-action').length===3")
            move(window,'[data-row-id="video-3"]',.42,.6);QTest.qWait(220)
            assert stats(window)['mist']['running']
            capture(window,'vapor_light')
            point=move(window,'#preview-button',.7,.5)
            QTest.mousePress(window.view.focusProxy(),Qt.MouseButton.LeftButton,pos=point)
            QTest.qWait(100);capture(window,'liquid_press_light')
            QTest.mouseRelease(window.view.focusProxy(),Qt.MouseButton.LeftButton,pos=point)
            QTest.qWait(200)
            assert js(window,"document.getElementById('preview-dialog').open"),'Native liquid button did not open preview'
            click(window,'#preview-dialog [data-close]')
            theme(window,'dark');move(window,'[data-row-id="video-3"]',.38,.55);QTest.qWait(250)
            capture(window,'vapor_dark')
            click(window,'#appearance-button');click(window,'#motion-setting');click(window,'#appearance-dialog [data-close]')
            wait_for(lambda:not stats(window)['mist']['running'] and not stats(window)['glassRunning'],'Reduced materials did not stop')
            original=window.grab()
            js(window,"document.querySelector('.list-mist').style.visibility='hidden';true");QTest.qWait(90)
            metrics['vaporChangedQuarterPixels']=changed(original,window.grab())
            assert metrics['vaporChangedQuarterPixels']>500
            js(window,"document.querySelector('.list-mist').style.visibility='';true");QTest.qWait(90)
            original=window.grab()
            js(window,"document.querySelectorAll('.liquid-actions-stage .lg-canvas').forEach(el=>el.style.visibility='hidden');true");QTest.qWait(90)
            metrics['buttonsChangedQuarterPixels']=changed(original,window.grab())
            assert metrics['buttonsChangedQuarterPixels']>300
            js(window,"document.querySelectorAll('.liquid-actions-stage .lg-canvas').forEach(el=>el.style.visibility='');globalThis.__stableActions=[...document.querySelectorAll('.detail-actions button')];document.getElementById('file-list').focus();true")
            for i in range(25):
                QTest.keyClick(window.view.focusProxy(),Qt.Key.Key_Home if i%6==0 else Qt.Key.Key_Down);QTest.qWait(25)
            assert js(window,"globalThis.__stableActions.every((el,i)=>el===document.querySelectorAll('.detail-actions button')[i])")
            assert stats(window)['actions'][0]['bodies']==2
            click(window,'#appearance-button');click(window,'#mist-setting')
            assert stats(window)['mist']['mode']=='off' and stats(window)['glassEnabled']
            click(window,'#mist-setting');click(window,'#glass-setting')
            assert stats(window)['mist']['enabled'] and not stats(window)['glassEnabled']
            assert all(item['mode']=='fallback' for item in stats(window)['actions'])
            capture(window,'plain_buttons_dark')
            click(window,'#glass-setting');click(window,'#motion-setting')
            click(window,'#appearance-dialog [data-close]')
            move(window,'.page-heading')
            wait_for(lambda:not stats(window)['mist']['running'] and not stats(window)['glassRunning'],'Idle drawing did not stop')
            first=stats(window);QTest.qWait(400);second=stats(window)
            assert first['mist']['frames']==second['mist']['frames']
            assert first['glassFrames']==second['glassFrames']
            window.showMinimized();QTest.qWait(150)
            assert not stats(window)['mist']['running']
            window.showNormal();QTest.qWait(150)
            js(window,"document.querySelector('.list-mist').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext();true")
            QTest.qWait(250)
            wait_for(lambda:stats(window)['mist']['mode']=='webgl2','Vapor context did not recover')
            window.resize(900,620);QTest.qWait(150)
            assert js(window,"document.documentElement.scrollWidth<=innerWidth")
            capture(window,'minimum_dark')
            window.resize(1280,860);QTest.qWait(100)
            click(window,'#dataset-button');click(window,'[data-scenario="large"]')
            wait_for(lambda:js(window,"globalThis.yingxuPreview.stats().total===10000"),'Large fixture failed')
            assert js(window,"document.querySelectorAll('.file-row').length<30 && document.querySelectorAll('.list-mist').length===1")
            metrics['large']=data(window,'globalThis.yingxuPreview.stats()')
            click(window,'#dataset-button');click(window,'[data-scenario="empty"]')
            wait_for(lambda:js(window,"document.getElementById('file-list').hidden"),'Empty state failed')
            assert not stats(window)['mist']['running']
            click(window,'#dataset-button');click(window,'[data-scenario="matched"]')
            wait_for(lambda:js(window,"globalThis.yingxuPreview.stats().total===12"),'Reload fixture failed')
            theme(window,'light');move(window,'[data-row-id="video-1"]',.4,.55);QTest.qWait(200);capture(window,'final_light')
            theme(window,'dark');move(window,'[data-row-id="video-1"]',.4,.55);QTest.qWait(200);capture(window,'final_dark')
            assert not window.page.console_errors,window.page.console_errors
            js(window,"window.dispatchEvent(new Event('pagehide'));true")
            assert stats(window)['mist']['destroyed'] and stats(window)['mist']['canvases']==0
            assert js(window,"globalThis[Symbol.for('lens.viewport-gpu-budget.v1')].budget.clients.size===0")
            window.close();QTest.qWait(200)
            window=WebWindow(preview=True,appearance_settings=settings)
            script=QWebEngineScript();script.setName('test-no-webgl');script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation);script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            script.setSourceCode("(() => {const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};})();")
            window.page.scripts().insert(script);window.reload_page();window.show();ready(window)
            assert stats(window)['mist']['mode']=='fallback' and all(item['mode']=='fallback' for item in stats(window)['actions'])
            capture(window,'no_webgl_dark')
            assert not window.page.console_errors,window.page.console_errors
            js(window,"window.dispatchEvent(new Event('pagehide'));true")
            assert stats(window)['mist']['destroyed'] and stats(window)['mist']['canvases']==0
            assert js(window,"globalThis[Symbol.for('lens.viewport-gpu-budget.v1')].budget.clients.size===0")
            assert not errors,errors
            print(json.dumps({'result':'PASS','metrics':metrics,'computerControlCalls':0},ensure_ascii=False),flush=True)
        finally:
            window.close();QTest.qWait(150)
