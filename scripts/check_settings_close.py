"""Check settings fade/removal lifecycle in the real HDR/SDR desktop host."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from yingxu.web_ui.native_window import configure_graphics, NativeWindow
from yingxu.web_ui.resources import register_scheme
from yingxu.operations import HistoryStore
from scripts.check_subtitle_browser import javascript, wait_for
from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def background_luma(window):
    frame = window.grabWindow()
    scale = frame.width()/window.width()
    x,y = int(10*scale),int(200*scale)
    if window.appearance.output_status['nativeHdrActive']:
        raw = bytes(frame.constBits())
        rgba = struct.unpack_from('<4e',raw,(y*frame.width()+x)*8)
        assert abs(rgba[3]-1.)<.02
        rgb = [max(0.,min(1.,v/window._white_scale)) for v in rgba[:3]]
        rgb = [v*12.92 if v<=.0031308 else 1.055*v**(1/2.4)-.055 for v in rgb]
        return round((rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722)*255,2)
    color = frame.pixelColor(x,y)
    return round(color.red()*.2126+color.green()*.7152+color.blue()*.0722,2)


def main():
    configure_graphics();register_scheme()
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    sdr = '--sdr' in sys.argv
    output = ROOT/f"work/test-results/stage16-{'sdr' if sdr else 'hdr'}-settings.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    result = {'passed':False,'closes':[],'physicalPeakMeasured':False}
    errors,graph_errors = [],[]
    original_hook = sys.excepthook
    sys.excepthook = lambda kind,error,trace:errors.append(f'{kind.__name__}: {error}')
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='settings-close-',dir=output.parent) as folder:
            settings = QSettings(str(Path(folder)/'appearance.ini'),QSettings.Format.IniFormat)
            settings.setValue('appearance/v1',json.dumps({'theme':'dark','nativeHdr':not sdr}))
            window = NativeWindow(appearance_settings=settings,history=HistoryStore(Path(folder)/'history.jsonl'))
            window.sceneGraphError.connect(lambda code,message:graph_errors.append(message))
            window.show();window.requestActivate();wait_for(lambda:window._loaded,'Startup');QTest.qWait(400)
            assert javascript(window.page,"!document.getElementById('command-button') && !document.getElementById('command-dialog')")
            QTest.keyClick(window,Qt.Key.Key_K,Qt.KeyboardModifier.ControlModifier);QTest.qWait(60)
            assert javascript(window.page,"!document.querySelector('dialog[open]')")
            result['quickActionsRemoved'] = True
            javascript(window.page,"window.__settingsEvents=[];for(const name of ['cancel','close'])document.getElementById('appearance-dialog').addEventListener(name,()=>__settingsEvents.push({name,at:performance.now()}));true")
            baseline = background_luma(window)
            for cycle in range(8):
                javascript(window.page,"document.getElementById('appearance-button').click();true")
                wait_for(lambda:javascript(window.page,"document.getElementById('appearance-dialog').open"),'Settings open')
                wait_for(lambda:window.compositor.overlayActive,'Overlay rendering')
                if cycle%2: javascript(window.page,"document.getElementById('appearance-dialog').scrollTop=400;true")
                QTest.qWait(70)
                javascript(window.page,"(()=>{const d=document.getElementById('appearance-dialog');window.__closeFrames=[];const tick=()=>{if(!d.open)return;__closeFrames.push({opacity:Number(getComputedStyle(d).opacity),closing:d.classList.contains('is-closing'),animations:d.getAnimations().filter(a=>a.effect.getKeyframes().some(k=>k.opacity!==undefined)).map(a=>a.effect.getTiming().duration)});requestAnimationFrame(tick)};requestAnimationFrame(tick);return true})()")
                if cycle%3==0: QTest.keyClick(window,Qt.Key.Key_Escape)
                else: javascript(window.page,"document.querySelector('#appearance-dialog [data-close]').click();true")
                wait_for(lambda:not javascript(window.page,"document.getElementById('appearance-dialog').open"),'Close transition finishes',2)
                samples = javascript(window.page,'window.__closeFrames.filter(s=>s.closing)')
                result['lastFadeFrames'] = samples
                result['lastVisibility'] = javascript(window.page,'({hidden:document.hidden,reduced:matchMedia("(prefers-reduced-motion: reduce)").matches})')
                wait_for(lambda:not window.compositor.overlayActive,'Overlay settle')
                assert any(0<s['opacity']<1 for s in samples),'No intermediate fade frame'
                assert any(140 in s['animations'] for s in samples),'Missing 140ms fade'
                assert javascript(window.page,"!document.getElementById('appearance-dialog').classList.contains('is-closing') && document.activeElement.id==='appearance-button'")
                current = background_luma(window)
                assert abs(current-baseline)<5,'Workspace brightness changed after close'
                result['closes'].append({'samples':len(samples),'intermediateFade':True,'backgroundLuma':current})
            # Reopen during an exit: the cancelled older exit must not hide it.
            javascript(window.page,"document.getElementById('appearance-button').click();true")
            QTest.qWait(80)
            javascript(window.page,"document.querySelector('#appearance-dialog [data-close]').click();true")
            QTest.qWait(35)
            javascript(window.page,"document.getElementById('appearance-button').click();true")
            QTest.qWait(300)
            assert javascript(window.page,"document.getElementById('appearance-dialog').open && !document.getElementById('appearance-dialog').classList.contains('is-closing') && getComputedStyle(document.getElementById('appearance-dialog')).opacity==='1'")
            result['reopenDuringExitPassed'] = True
            window.appearance.update('{"reducedMotion":true}')
            wait_for(lambda:javascript(window.page,"document.documentElement.dataset.reduced==='true'"),'Reduced motion')
            javascript(window.page,"document.querySelector('#appearance-dialog [data-close]').click();true")
            wait_for(lambda:not javascript(window.page,"document.getElementById('appearance-dialog').open"),'Reduced close')
            assert javascript(window.page,"document.getElementById('appearance-dialog').getAnimations().length===0")
            result['reducedMotionPassed'] = True
            pump = window.rootObject().findChild(QObject,'modalFramePump')
            wait_for(lambda:not window.compositor.overlayActive and not pump.property('running'),'Idle rendering stops')
            result['idleFramePumpStopped'] = True
            result['displayOutput'] = window.appearance.output_status
            assert not errors and not graph_errors and not window.page.console_errors
            result['passed'] = True
            window.close();QTest.qWait(100);window = None
    except Exception as error:
        result['failure'] = f'{type(error).__name__}: {error}'
        if window is not None:
            result['windowActive'] = window.isActive()
            result['closeEvents'] = javascript(window.page,'window.__settingsEvents || []')
        raise
    finally:
        if window is not None: window.close()
        result.update(pythonErrors=errors,sceneGraphErrors=graph_errors)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True),flush=True)
        sys.excepthook = original_hook


if __name__ == '__main__':main()
