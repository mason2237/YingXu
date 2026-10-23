import {transitionTheme, cancelThemeTransition} from '../vendor/design-systems/theme-transition.js';
import {desktopChannel} from './channel.js';

const defaults = {theme: 'system', resolvedTheme: 'light', systemTheme: 'light', glassEnabled: true,
  strength: 'enhanced', particlesEnabled: true, reducedMotion: false, mistEnabled: true};
class Appearance extends EventTarget {
  constructor() {
    super();
    this.state = Object.freeze({...defaults, ...globalThis.__yingxuAppearance});
    this.connected = false; this.version = 0; this.pendingOrigin = null;
    this.lastTransition = 'initial'; this.current = Promise.resolve();
    this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.motion.addEventListener('change', () => {if (this.motion.matches) cancelThemeTransition();});
    this.ready = new Promise(resolve => {
      if (!globalThis.qt?.webChannelTransport || !globalThis.QWebChannel) {resolve(false); return;}
      desktopChannel().then(channel => {
        this.bridge = channel.objects.appearance;
        if (!this.bridge) {resolve(false); return;}
        this.bridge.changed.connect(payload => this.receive(JSON.parse(payload), this.pendingOrigin));
        this.bridge.getState(payload => {
          this.connected = true; this.receive(JSON.parse(payload));
          document.documentElement.dataset.appearanceReady = 'true';
          this.dispatchEvent(new Event('connected')); resolve(true);
        });
      }).catch(() => resolve(false));
    });
    window.addEventListener('pagehide', cancelThemeTransition, {once: true});
  }
  get reduced() {return this.state.reducedMotion || this.motion.matches;}
  receive(next, origin) {
    if (JSON.stringify(next) === JSON.stringify(this.state)) return this.current;
    const themeChanged = next.resolvedTheme !== this.state.resolvedTheme;
    this.state = Object.freeze({...next});
    const version = ++this.version;
    const apply = async () => {
      if (version !== this.version) return;
      const root = document.documentElement;
      root.dataset.theme = next.resolvedTheme; root.dataset.themePreference = next.theme;
      root.dataset.reduced = String(this.reduced);
      this.dispatchEvent(new CustomEvent('change', {detail: this.state}));
      // Chromium pauses rAF while taking View Transition snapshots. The Lens
      // adapter flushes its new palette synchronously; never await rAF here.
    };
    this.current = (themeChanged ? transitionTheme(apply, {origin, reduced: this.reduced}) : apply().then(() => 'unchanged'))
      .then(mode => {if (version === this.version) {this.lastTransition = mode; document.documentElement.dataset.themeTransition = mode;}});
    return this.current;
  }
  async update(patch, origin = null) {
    if (!await this.ready) return this.error('外观设置未连接，请重新打开应用。');
    this.pendingOrigin = origin;
    return new Promise(resolve => this.bridge.update(JSON.stringify(patch), async payload => {
      const response = JSON.parse(payload);
      if (!response.ok) {this.pendingOrigin = null; this.error('无法保存外观设置，请检查本地设置的写入权限。'); resolve(false); return;}
      await this.receive(response.state, origin); this.pendingOrigin = null; resolve(true);
    }));
  }
  error(message) {this.dispatchEvent(new CustomEvent('error', {detail: message})); return false;}
}

export const appearance = new Appearance();

export function bindThemeControls() {
  const controls = [...document.querySelectorAll('[data-theme-select]')];
  const labels = {system: '跟随系统', light: '浅色', dark: '深色'};
  const refresh = () => {
    controls.forEach(control => {control.value = appearance.state.theme; control.disabled = !appearance.connected;});
    document.querySelectorAll('[data-theme-status]').forEach(label => {
      label.textContent = appearance.state.theme === 'system' ? `跟随系统 · 当前${labels[appearance.state.resolvedTheme]}` : `${labels[appearance.state.theme]}外观`;
    });
  };
  controls.forEach(control => control.addEventListener('change', () => appearance.update({theme: control.value}, control)));
  appearance.addEventListener('change', refresh); appearance.addEventListener('connected', refresh);
  appearance.addEventListener('error', event => {
    refresh(); document.querySelectorAll('[data-theme-status]').forEach(label => {label.textContent = event.detail;});
  });
  refresh();
}
