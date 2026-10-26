"""Bounded real-window rendering checks; isolated settings and synthetic data only."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QObject, QPointF, QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore
from yingxu.web_ui.native_window import NativeWindow, configure_graphics
from yingxu.web_ui.resources import register_scheme
from yingxu.web_ui.embedded_settings import EmbeddedSettings
from scripts.check_subtitle_browser import javascript, wait_for


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdr', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    label = ('baseline' if args.baseline else 'updated') + ('-sdr' if args.sdr else '-hdr')
    output = ROOT / f'work/test-results/stage19-{label}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'label': label, 'checks': [], 'physicalHdrMeasured': False}
    print('render check: starting ' + label, flush=True)
    configure_graphics()
    register_scheme()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    errors, frames = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda kind, error, trace: errors.append(f'{kind.__name__}: {error}')
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='render-', dir=output.parent) as folder:
            settings = QSettings(str(Path(folder) / 'appearance.ini'), QSettings.Format.IniFormat)
            settings.setValue('appearance/v1', json.dumps({'theme': 'dark', 'nativeHdr': not args.sdr}))
            window = NativeWindow(appearance_settings=settings, history=HistoryStore(Path(folder) / 'history.jsonl'))
            window.sceneGraphError.connect(lambda code, message: errors.append(message))
            window.frameSwapped.connect(lambda: frames.append(time.perf_counter()))
            window.show()
            window.requestActivate()
            wait_for(lambda: window._loaded, 'Workspace startup')
            print('render check: workspace loaded', flush=True)
            QTest.qWait(1800)
            javascript(window.page, """window.__sample={mutations:0,ids:{}};
              window.__obs=new MutationObserver(rs=>{for(const r of rs){__sample.mutations++;
              const k=r.target.id||r.target.className;__sample.ids[k]=(__sample.ids[k]||0)+1}});
              __obs.observe(document.body,{subtree:true,attributes:true,attributeFilter:['class']});true""")
            first = len(frames)
            QTest.qWait(1000)
            result['idle'] = {'nativeFrames': len(frames) - first,
                              **javascript(window.page, '({...__sample,hidden:document.hidden})')}
            javascript(window.page, '__obs.disconnect();true')
            javascript(window.page, "window.__sampleFrames=[];window.__raf=requestAnimationFrame(function tick(t){__sampleFrames.push(t);__raf=requestAnimationFrame(tick)});true")
            QTest.qWait(600)
            samples = javascript(window.page, 'cancelAnimationFrame(__raf);__sampleFrames')
            result['rafSamples'] = len(samples)
            result['maxRafGapMs'] = round(max((b-a for a,b in zip(samples,samples[1:])), default=0), 2)
            result['displayOutput'] = window.appearance.output_status
            if not args.baseline:
                assert result['idle']['mutations'] < 8, 'Self-triggered class updates continue at idle'
                assert len(samples) >= 8, 'Animation frames did not advance'
                result['checks'].append('idle_mutation_loop_stopped_and_frames_advance')
                javascript(window.page, (ROOT / 'tests/frontend/rendering.js').read_text(encoding='utf-8'))
                wait_for(lambda: javascript(window.page, 'Boolean(window.__renderTests)'), 'List regressions', 8)
                result['list'] = javascript(window.page, 'window.__renderTests')
                assert result['list']['passed'], result['list']
                print('render check: list regressions passed', flush=True)
                pump = window.rootObject().findChild(QObject, 'modalFramePump')
                layer = window.rootObject().findChild(QObject, 'hdrLayer')
                assert bool(layer.property('active')) == window._hdr
                result['hdrTextureAllocated'] = bool(layer.property('active'))
                fades = []
                for cycle in range(4):
                    javascript(window.page, "document.getElementById('appearance-button').click();true")
                    wait_for(lambda: window.compositor.overlayActive, 'Settings open')
                    QTest.qWait(350)
                    assert not pump.property('running'), 'Settings keep a periodic HDR frame pump running'
                    box = javascript(window.page, "(()=>{const r=document.getElementById('appearance-dialog').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
                    point = QPointF(box['x'],box['y'])
                    for delta in (-120,-120,120,120):
                        QTest.wheelEvent(window,point,QPoint(0,delta))
                        QTest.qWait(30)
                    javascript(window.page, "window.__fade=[];requestAnimationFrame(function tick(){const d=document.getElementById('appearance-dialog');if(!d.open)return;__fade.push(Number(getComputedStyle(d).opacity));requestAnimationFrame(tick)});document.querySelector('#appearance-dialog [data-close]').click();true")
                    wait_for(lambda: not window.compositor.overlayActive, 'Settings fade and settle', 3)
                    samples = javascript(window.page, '__fade')
                    assert any(0<v<1 for v in samples), 'Settings fade did not paint an intermediate frame'
                    assert javascript(window.page, "document.activeElement.id==='appearance-button' && !document.querySelector('dialog[open]')")
                    fades.append(len(samples))
                result['settingsFadeSamples'] = fades
                result['checks'].append('real_wheel_settings_close_fade_focus_and_idle_pump')
                # A late close must not hide a dialog reopened during its fade.
                javascript(window.page, "document.getElementById('appearance-button').click();document.querySelector('#appearance-dialog [data-close]').click();setTimeout(()=>document.getElementById('appearance-button').click(),35);true")
                QTest.qWait(400)
                assert javascript(window.page, "document.getElementById('appearance-dialog').open && !document.getElementById('appearance-dialog').classList.contains('is-closing')")
                window.appearance.update('{"reducedMotion":true}')
                QTest.qWait(100)
                javascript(window.page,"document.querySelector('#appearance-dialog [data-close]').click();true")
                wait_for(lambda:not window.compositor.overlayActive,'Reduced close')
                result['checks'].append('reopen_during_fade_and_reduced_motion')
                for theme in ('light','dark'):
                    window.appearance.update(json.dumps({'theme':theme,'reducedMotion':False}))
                    QTest.qWait(150)
                    assert javascript(window.page, f"document.documentElement.dataset.theme==='{theme}'")
                for width,height in ((940,700),(1280,860)):
                    window.resize(width,height);QTest.qWait(180)
                    assert javascript(window.page,'document.documentElement.scrollWidth<=innerWidth')
                window.showMinimized();QTest.qWait(150);assert not pump.property('running')
                window.showNormal();window.requestActivate();QTest.qWait(300)
                window.reloadPage();wait_for(lambda:window._loaded,'Reload recovery')
                assert len(window.page.callbacks) <= 1 and not window.compositor.overlayActive
                result['checks'].append('theme_resize_minimize_restore_reload')
                media = Path(folder) / '字幕整理测试';media.mkdir()
                for index in range(120):
                    (media / f'测试影片.S01E{index+1:03}.mkv').write_bytes(b'rendering fixture')
                language = QSettings(str(Path(folder)/'language.ini'),QSettings.Format.IniFormat)
                language.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}))
                service = window.bridge.service
                service.embedded_settings = EmbeddedSettings(language)
                service.accept_folder(media,dropped=True)
                wait_for(lambda:service.data is not None and not service.busy,'Real scan')
                wait_for(lambda:javascript(window.page,"document.querySelectorAll('#list-items .file-row').length>0"),'Scanned list painted')
                javascript(window.page,"document.getElementById('file-list').focus();true")
                QTest.keyClick(window,Qt.Key.Key_PageDown);QTest.qWait(150)
                box = javascript(window.page,"(()=>{const r=document.getElementById('file-list').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
                point = QPointF(box['x'],box['y'])
                javascript(window.page,"window.__listWheel=0;document.getElementById('file-list').addEventListener('wheel',()=>__listWheel++,{passive:true});true")
                QTest.mouseMove(window,point.toPoint())
                for _ in range(8):
                    QTest.wheelEvent(window,point,QPoint(0,-120));QTest.qWait(45)
                QTest.qWait(200)
                result['realList'] = javascript(window.page,"""(()=>{const v=document.getElementById('file-list'),r=v.getBoundingClientRect(),nodes=[...document.querySelectorAll('#list-items .file-row')];return {total:v.getAttribute('aria-rowcount'),nodes:nodes.length,scrollTop:v.scrollTop,visible:nodes.filter(n=>{const b=n.getBoundingClientRect();return b.bottom>r.top&&b.top<r.bottom}).length}})()""")
                result['realList']['wheelEvents'] = javascript(window.page,'__listWheel')
                assert result['realList']['total']=='120' and result['realList']['visible']>=3 and result['realList']['scrollTop']>336
                assert result['realList']['wheelEvents']>=8
                assert all(p.read_bytes()==b'rendering fixture' for p in media.iterdir())
                assert len(list(media.iterdir()))==120
                result['checks'].append('real_scan_keyboard_wheel_visible_rows_no_media_changes')
                # Capture the composited window once. QQuickWindow.grabWindow
                # mislabels HDR readback as RGBA8888 on this Qt/D3D11 runtime.
                # This desktop SDR image is not a physical HDR measurement.
                QTest.qWait(400)
                frame = window.screen().grabWindow(int(window.winId())).toImage()
                assert not frame.isNull(), 'Native window capture was empty'
                result['screenshotFormat'] = frame.format().name
                result['screenshotMethod'] = 'QScreen window capture'
                screenshot = output.with_suffix('.png')
                assert frame.save(str(screenshot))
                result['screenshot'] = screenshot.name
            result['passed'] = not errors and not window.page.console_errors
            result['consoleErrors'] = window.page.console_errors
            window.close()
            QTest.qWait(150)
            window = None
    except Exception as error:
        result['failure'] = f'{type(error).__name__}: {error}'
        print(result['failure'], flush=True)
    finally:
        if window is not None:
            window.close()
        result['errors'] = errors
        if output.exists():
            output.with_name(f'{output.stem}-{time.time_ns()}.json').write_bytes(output.read_bytes())
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True), flush=True)
        sys.excepthook = old_hook
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
