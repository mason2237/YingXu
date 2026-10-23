"""Phase 6.2: actual Qt/WebEngine, temporary INI, no OS-setting/CUA automation."""
import json
import os
import re
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_web_foundation import javascript, wait_for
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.appearance import SETTINGS_KEY, DEFAULTS
from yingxu.web_ui.window import WebWindow


def js(window, source): return javascript(window.page, source)
def data(window, source): return json.loads(js(window, 'JSON.stringify(' + source + ')'))


def ready(window):
    wait_for(lambda: window._loaded and js(window, "document.documentElement.dataset.ready==='true' && document.documentElement.dataset.appearanceReady==='true'"), 'Theme page did not initialize')
    assert not window.page.console_errors, window.page.console_errors
    assert set(window.channel.registeredObjects()) == {'appearance'}
    assert window.bridge.service.job is None


def select(window, selector, value):
    js(window, f"(() => {{const el=document.querySelector({json.dumps(selector)});el.focus({{preventScroll:true}});el.value={json.dumps(value)};el.dispatchEvent(new Event('change',{{bubbles:true}}));}})();true")


def theme(window, value, selector='#theme-quick'):
    select(window, selector, value)
    wait_for(lambda: window.appearance.state()['theme'] == value and js(window, f"document.documentElement.dataset.themePreference === {json.dumps(value)} && !document.documentElement.classList.contains('ov-vt')"), 'Theme transition did not settle')
    QTest.qWait(100)


def click(window, selector):
    js(window, f"document.querySelector({json.dumps(selector)}).focus({{preventScroll:true}});document.querySelector({json.dumps(selector)}).click();true")
    QTest.qWait(220)


def capture(window, name):
    QTest.qWait(150)
    prefix=os.environ.get('YINGXU_CAPTURE_PREFIX','stage62')
    assert window.grab().save(str(ROOT / 'outputs' / f'{prefix}_{name}.png'))
    if name in ('workspace_dark', 'workspace_light_final'):
        window.activateWindow(); QTest.qWait(100)
        if window.isActiveWindow():
            frame = window.frameGeometry()
            assert window.screen().grabWindow(0, frame.x(), frame.y(), frame.width(), frame.height()).save(str(ROOT / 'outputs' / f'{prefix}_native_{name}.png'))


def colors(window):
    return data(window, "({theme:document.documentElement.dataset.theme, root:getComputedStyle(document.documentElement).backgroundColor, surface:getComputedStyle(document.querySelector('.collection')).backgroundColor, ink:getComputedStyle(document.querySelector('.file-name')).color, glass:document.querySelector('.workspace-lens-stage').dataset.scene, transition:document.documentElement.dataset.themeTransition})")


def contrast_samples(window):
    samples = data(window, """(() => {
      const selectors=['.page-heading p','.list-caption','.file-name','.file-extension','.file-subtitle','.match-score','.badge.review','.detail-label','.detail-video','.basis-list','.footer-state'];
      return selectors.map(selector => {const el=document.querySelector(selector);if(!el)return null;let node=el;const backgrounds=[];while(node){backgrounds.push(getComputedStyle(node).backgroundColor);node=node.parentElement;}return {selector,color:getComputedStyle(el).color,backgrounds};}).filter(Boolean);
    })()""")
    def rgba(value):
        parts = [float(part) for part in re.findall(r'[\d.]+', value)]
        if value.startswith('color(srgb'):parts[:3]=[part*255 for part in parts[:3]]
        return parts[:3] + [parts[3] if len(parts) == 4 else 1]
    def luminance(rgb):
        values = [v / 255 for v in rgb]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))
    ratios = {}
    for sample in samples:
        background = [255, 255, 255]
        for value in reversed(sample['backgrounds']):
            color = rgba(value)
            background = [color[i] * color[3] + background[i] * (1 - color[3]) for i in range(3)]
        foreground = rgba(sample['color'])
        lum = sorted((luminance(foreground[:3]), luminance(background)))
        ratio = (lum[1] + .05) / (lum[0] + .05)
        ratios[sample['selector']] = round(ratio, 2)
        assert ratio >= 4.5, (sample, ratio)
    return ratios


def check_titlebar(window):
    if sys.platform != 'win32' or not window.titlebar_status.get('captionSupported'): return
    import ctypes
    from ctypes import wintypes
    value = wintypes.DWORD()
    fn = ctypes.WinDLL('dwmapi').DwmGetWindowAttribute
    fn.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    fn.restype = ctypes.c_long
    status = fn(int(window.winId()), 35, ctypes.byref(value), ctypes.sizeof(value))
    window.titlebar_status['captionReadbackSupported'] = status == 0
    if status != 0: return  # Windows may accept the setter but not this readback.
    assert value.value == (0x251d19 if window.appearance.state()['resolvedTheme'] == 'dark' else 0xffffff)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    errors = []
    sys.excepthook = lambda kind, value, tb: (errors.append(str(value)), sys.__excepthook__(kind, value, tb))
    with TemporaryDirectory(prefix='yingxu-theme-') as directory:
        settings = QSettings(str(Path(directory) / 'appearance.ini'), QSettings.Format.IniFormat)
        settings.setValue(SETTINGS_KEY, json.dumps({**DEFAULTS, 'theme': 'dark'}))
        window = WebWindow(preview=True, appearance_settings=settings)
        assert window.page.backgroundColor().name() == '#13161c'
        window.show()
        metrics = {}
        try:
            ready(window)
            assert js(window, "globalThis.__yingxuAppearance.resolvedTheme==='dark' && document.documentElement.dataset.appearanceBootstrapped==='true'")
            wait_for(lambda: js(window, "globalThis.yingxuPreview.stats().effects.glassMode==='webgl2'"), 'Dark glass did not activate')
            metrics['dark'] = colors(window)
            assert metrics['dark']['root'] == 'rgb(19, 22, 28)'
            assert metrics['dark']['glass'] == 'ocean'
            assert window.palette().window().color().name() == '#13161c'
            metrics['titlebar'] = window.titlebar_status
            check_titlebar(window)
            metrics['darkContrast'] = contrast_samples(window)
            capture(window, 'workspace_dark')
            print('CHECK: dark startup/bootstrap/native colors', flush=True)

            click(window, '[data-filter="需确认"]')
            click(window, '.detail-section-title button')
            click(window, '.candidate-card.recommended button')
            js(window, "document.getElementById('search-input').value='S01';document.getElementById('search-input').dispatchEvent(new Event('input',{bubbles:true}));true")
            QTest.qWait(240)
            before = data(window, 'globalThis.yingxuPreview.stats()')
            theme(window, 'light')
            after = data(window, 'globalThis.yingxuPreview.stats()')
            for key in ('total', 'selectedId', 'revision'):
                assert before[key] == after[key], (key, before, after)
            assert js(window, "document.getElementById('search-input').value==='S01' && document.querySelector('[data-filter=\"需确认\"]').getAttribute('aria-pressed')==='true'")
            metrics['light'] = colors(window)
            check_titlebar(window)
            metrics['lightContrast'] = contrast_samples(window)
            assert metrics['light']['root'] == 'rgb(245, 247, 250)'
            assert metrics['light']['glass'] == 'grid'
            assert metrics['light']['transition'] == 'iris'
            capture(window, 'workspace_light')
            print('CHECK: short upstream iris/state preservation', flush=True)

            click(window, '#appearance-button')
            theme(window, 'dark', '#theme-setting')
            assert js(window, "document.getElementById('theme-quick').value==='dark' && document.getElementById('appearance-dialog').open && document.activeElement.id==='theme-setting'")
            capture(window, 'appearance_dark')
            click(window, '#motion-setting')
            wait_for(lambda: window.appearance.state()['reducedMotion'], 'Reduced preference not saved')
            theme(window, 'light', '#theme-setting')
            assert js(window, "document.documentElement.dataset.themeTransition==='instant'")
            theme(window, 'dark', '#theme-setting')
            select(window, '#glass-strength', 'standard')
            click(window, '#glass-setting')
            click(window, '#particle-setting')
            wait_for(lambda: not window.appearance.state()['glassEnabled'] and not window.appearance.state()['particlesEnabled'] and window.appearance.state()['strength']=='standard', 'Effects did not save')
            capture(window, 'fallback_dark')
            click(window, '#appearance-dialog [data-close]')
            window.reload_page(); ready(window)
            restored = data(window, 'globalThis.yingxuPreview.stats().effects')
            assert restored['reduced'] and not restored['glassEnabled'] and restored['strength'] == 'standard'
            assert js(window, "globalThis.__yingxuAppearance.resolvedTheme==='dark'")
            print('CHECK: preferences/refresh/reduced motion', flush=True)

            window.close(); QTest.qWait(200)
            window = WebWindow(preview=True, appearance_settings=settings)
            assert window.page.backgroundColor().name() == '#13161c'
            window.show(); ready(window)
            assert js(window, "document.documentElement.dataset.theme==='dark' && !globalThis.yingxuPreview.stats().effects.glassEnabled")
            # Simulate incoming native system events without changing Windows.
            theme(window, 'light')
            window.appearance.system_changed(Qt.ColorScheme.Dark)
            QTest.qWait(100)
            assert js(window, "document.documentElement.dataset.theme==='light'")
            theme(window, 'system')
            wait_for(lambda: js(window, "document.documentElement.dataset.theme==='dark'"), 'Follow system dark failed')
            window.appearance.system_changed(Qt.ColorScheme.Light)
            wait_for(lambda: js(window, "document.documentElement.dataset.theme==='light'"), 'Follow system light failed')
            assert js(window, "document.querySelector('[data-theme-select]').value==='system'")
            print('CHECK: new window and simulated system events', flush=True)

            click(window, '#appearance-button')
            click(window, '#glass-setting'); click(window, '#particle-setting'); click(window, '#motion-setting')
            select(window, '#glass-strength', 'enhanced')
            click(window, '#appearance-dialog [data-close]')
            theme(window, 'dark'); theme(window, 'light'); theme(window, 'dark')
            js(window, "for(const value of ['light','dark','light','dark']){const el=document.getElementById('theme-quick');el.value=value;el.dispatchEvent(new Event('change'));}true")
            wait_for(lambda: js(window, "document.documentElement.dataset.theme==='dark' && !document.documentElement.classList.contains('ov-vt')"), 'Rapid theme changes failed')
            assert window.appearance.state()['theme'] == 'dark'
            assert not window.page.console_errors, window.page.console_errors
            for width, height in ((900,620),(1000,700),(1280,860)):
                window.resize(width,height); QTest.qWait(150)
                assert js(window, "document.documentElement.scrollWidth<=innerWidth")
                assert js(window, "document.querySelector('.chrome-actions').getBoundingClientRect().right<=innerWidth")
                if width == 900:
                    click(window, '#appearance-button'); capture(window, 'appearance_minimum_dark'); click(window, '#appearance-dialog [data-close]')
                    capture(window, 'minimum_dark')
            wait_for(lambda: not data(window, 'globalThis.yingxuPreview.stats().effects')['glassRunning'], 'Dark glass did not settle')
            frames = data(window, 'globalThis.yingxuPreview.stats().effects')['glassFrames']
            QTest.qWait(350)
            assert data(window, 'globalThis.yingxuPreview.stats().effects')['glassFrames'] == frames
            capture(window, 'workspace_dark_final')
            theme(window, 'light'); capture(window, 'workspace_light_final'); theme(window, 'dark')
            # Keep this test's settings isolated, and inspect the original lab in
            # dark mode too. The legacy column intentionally retains its light baseline.
            window.close(); QTest.qWait(200)
            window = WebWindow(effects=True, appearance_settings=settings)
            window.show(); ready(window)
            wait_for(lambda: js(window, "globalThis.yingxuEffectsLab.stats().comparisons.every(x=>x.mode==='webgl2')"), 'Dark comparison compositors failed')
            assert js(window, "document.getElementById('enhanced-stage').dataset.scene==='ocean'")
            capture(window, 'comparison_dark')
            click(window, '#open-lens-dialog')
            wait_for(lambda: js(window, "globalThis.yingxuEffectsLab.stats().dialog?.mode==='webgl2'"), 'Dark dialog lens failed')
            capture(window, 'lens_dialog_dark')
            click(window, '#lens-dialog [data-close]')
            theme(window, 'light')
            assert js(window, "document.getElementById('enhanced-stage').dataset.scene==='grid'")
            assert not window.page.console_errors, window.page.console_errors
            assert not errors, errors
            metrics['systemEvents'] = 'simulated, OS preferences unchanged'
            metrics['idle'] = 'no additional frames'
            print(json.dumps({'result':'PASS','metrics':metrics},ensure_ascii=False), flush=True)
        finally:
            window.close(); QTest.qWait(200)
