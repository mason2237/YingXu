"""Bounded HDR/SDR and redraw smoke test using isolated settings and no media."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.web_ui.native_window import NativeWindow, configure_graphics
from yingxu.web_ui.resources import register_scheme
from yingxu.operations import HistoryStore
from scripts.check_subtitle_browser import javascript, wait_for
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineQuick import QtWebEngineQuick


def main():
    configure_graphics();register_scheme()
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    sdr = '--sdr' in sys.argv
    result = {'passed':False, 'checks':[], 'requestedHdr':not sdr, 'physicalPeakMeasured':False}
    output = ROOT / f"work/test-results/stage13-{'sdr' if sdr else 'hdr'}-stability.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    errors, graph_errors, frames = [], [], []
    original_hook = sys.excepthook
    sys.excepthook = lambda kind,error,trace: errors.append(f'{kind.__name__}: {error}')
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='native-', dir=output.parent) as folder:
            settings = QSettings(str(Path(folder)/'appearance.ini'), QSettings.Format.IniFormat)
            settings.setValue('appearance/v1', json.dumps({'theme':'dark', 'nativeHdr':not sdr}))
            window = NativeWindow(appearance_settings=settings, history=HistoryStore(Path(folder)/'history.jsonl'))
            window.sceneGraphError.connect(lambda code,message: graph_errors.append(message))
            window.frameSwapped.connect(lambda: frames.append(True))
            window.show();wait_for(lambda:window._loaded, 'Native workspace startup')
            assert set(window.channel.registeredObjects()) == {'bridge','appearance','compositor'}
            assert javascript(window.page,"typeof globalThis.nativeHost==='undefined'")
            result['checks'].append('local_channel_only_no_native_host_exposure')
            print('stability: theme changes',flush=True)
            for theme in ('light', 'dark', 'light', 'dark'):
                javascript(window.page,f"document.querySelector('#theme-quick').value='{theme}';document.querySelector('#theme-quick').dispatchEvent(new Event('change',{{bubbles:true}}));true")
                wait_for(lambda:window.appearance.state()['resolvedTheme']==theme,'Theme change')
                QTest.qWait(120)
            assert javascript(window.page,"document.documentElement.dataset.themeTransitionReason==='desktop-stability'")
            print('stability: resize',flush=True)
            for width,height in ((940,700),(1280,860),(980,740)):
                window.resize(width,height);QTest.qWait(150)
                assert javascript(window.page,'document.documentElement.scrollWidth<=innerWidth')
            print('stability: minimize/restore',flush=True)
            window.showMinimized();QTest.qWait(200);window.showNormal();QTest.qWait(400)
            result['checks'].append('theme_changes_resize_minimize_restore')
            for _ in range(2):
                print('stability: reload',flush=True)
                window.reloadPage();wait_for(lambda:window._loaded,'Reload recovery');QTest.qWait(250)
            javascript(window.page,"document.querySelector('#appearance-button').click();true")
            wait_for(lambda:javascript(window.page,"document.querySelector('#appearance-dialog').open"),'Appearance dialog')
            result['displayOutput'] = window.appearance.output_status
            if sdr:
                assert result['displayOutput']['swapchain'] == 'SDR'
                assert result['displayOutput']['nativeHdrActive'] is False
            elif result['displayOutput']['systemHdrEnabled'] is True:
                assert result['displayOutput']['swapchain'] == 'HDRExtendedSrgbLinear'
                assert result['displayOutput']['nativeHdrActive'] is True
            assert result['displayOutput']['osSettingsChanged'] is False
            assert not errors and not graph_errors and not window.page.console_errors
            assert len(frames)>20
            result['presentedFrames'] = len(frames)
            result['checks'].append('two_reload_recoveries_settings_actual_swapchain_no_graph_or_js_errors')
            window.close();QTest.qWait(200);window = None
            assert not errors
            result['passed'] = True
    except Exception as error:
        result['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        if window is not None: window.close()
        result.update(pythonErrors=errors, sceneGraphErrors=graph_errors)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True),flush=True)
        sys.excepthook = original_hook


if __name__ == '__main__': main()
