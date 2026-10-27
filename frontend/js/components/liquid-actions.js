import {LensRuntime, ENHANCED_MATERIAL} from './lens-runtime.js';

// Shared upstream compositor per action group; the canvas is clipped to the
// real buttons. No screenshot sampling, duplicate controls or new click layer.
export class LiquidActions {
  constructor(host, options) {
    this.host = host; this.options = options; this.runtime = null; this.buttons = [];
    this.signature = ''; this.dead = false; this.refreshing = false;this.bodyCache = new WeakMap();this.original = new WeakMap();
    host.classList.add('liquid-actions-stage');
    this.resize = new ResizeObserver(() => this.refresh(true)); this.resize.observe(host);
    this.observer = new MutationObserver(() => this.refresh());
    this.observer.observe(host, {subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'disabled', 'hidden']});
    this.refresh();
  }
  refresh(force = false) {
    if (this.dead || this.refreshing) return;
    const controls = [...this.host.querySelectorAll('button')];
    const signature = controls.map(button => `${button.classList.contains('primary')}:${button.disabled}:${button.offsetWidth}`).join('|');
    const changed = controls.length !== this.buttons.length || controls.some((button, i) => button !== this.buttons[i]);
    if (!force && !changed && signature === this.signature) return;
    this.refreshing = true; this.signature = signature;
    if (changed) {
      this.release(this.buttons.filter(button => !controls.includes(button)));
      this.buttons.forEach(button => this.resize.unobserve(button)); this.buttons = controls;
      controls.forEach(button => {
        if (!this.original.has(button)) this.original.set(button,{surface:button.classList.contains('lg-surface'),glass:button.getAttribute('data-glass'),drag:button.getAttribute('data-lg-drag')});
        button.classList.add('lg-surface', 'liquid-action'); button.dataset.glass = 'button'; button.dataset.lgDrag = 'tether';
        this.resize.observe(button);
      });
    }
    if (controls.length && !this.runtime) {
      this.runtime = new LensRuntime(this.host, {artwork: (ctx, size) => this.artwork(ctx, size), elasticity: .68});
      const renderer = this.runtime.system?.renderer;
      if (renderer) {
        const render = renderer.render.bind(renderer);
        renderer.render = now => {
          const jelly = this.runtime.system.jelly;
          if (renderer.rectDirty || jelly.frame || jelly.gesture || !this.clipPath) this.clip();
          render(now);
        };
      }
    }
    if (changed && this.runtime) {
      const jelly = this.runtime.system?.jelly;
      for (const button of controls) {
        const body = this.bodyCache.get(button);
        if (body && !jelly.bodies.has(button)) jelly.bodies.set(button,body);
      }
      this.runtime.system?.mount();
      for (const body of jelly.bodies.values()) body.maxTravel = 12;
    }
    this.configure(); this.runtime?.setTheme(document.documentElement.dataset.theme || 'light'); this.clip();
    this.refreshing = false;
  }
  release(buttons = this.buttons) {
    const jelly = this.runtime?.system?.jelly;
    for (const button of buttons) {
      const body = jelly?.bodies.get(button);
      if (body) {if (jelly.gesture?.body === body) jelly.cancel(true);this.bodyCache.set(button,body);jelly.bodies.delete(button);}
      const original = this.original.get(button);if (!original) continue;
      if (!original.surface) button.classList.remove('lg-surface');button.classList.remove('liquid-action');
      for (const [name,value] of [['data-glass',original.glass],['data-lg-drag',original.drag]]) {if (value === null) button.removeAttribute(name);else button.setAttribute(name,value);}
      button.style.removeProperty('--jelly-matrix');button.style.removeProperty('--jelly-base');button.classList.remove('jelly-moving');delete button.dataset.held;
    }
  }
  configure() {
    const options = this.options();
    if (!this.runtime) return;
    this.runtime.setReduced(options.reduced);
    this.runtime.setMaterial(options.strength === 'standard' ? 'thick' : ENHANCED_MATERIAL);
    if (options.enabled) this.runtime.start(); else this.runtime.stop();
  }
  clip() {
    const canvas = this.runtime?.system?.renderer?.canvas;
    if (!canvas) return;
    const parent = this.host.getBoundingClientRect();
    const paths = this.buttons.filter(button => !button.disabled && button.getClientRects().length).map(button => {
      const rect = button.getBoundingClientRect(), x = rect.left - parent.left - 1, y = rect.top - parent.top - 1;
      const w = rect.width + 2, h = rect.height + 2, r = Math.min(10, h / 2);
      return `M${x+r},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h-r}Q${x+w},${y+h} ${x+w-r},${y+h}H${x+r}Q${x},${y+h} ${x},${y+h-r}V${y+r}Q${x},${y} ${x+r},${y}Z`;
    });
    const clip = paths.length ? `path("${paths.join(' ')}")` : 'inset(50%)';
    // The Lens observer also watches this canvas. Writing the same clip on
    // every render must not extend its animation window indefinitely.
    if (this.clipPath !== clip) {this.clipPath = clip;canvas.style.clipPath = clip;}
  }
  artwork(ctx, {width, height, dpr}) {
    const dark = document.documentElement.dataset.theme === 'dark', parent = this.host.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    for (const button of this.buttons) {
      const rect = button.getBoundingClientRect(); if (!rect.width) continue;
      const x = (rect.left - parent.left) * dpr, y = (rect.top - parent.top) * dpr;
      const w = rect.width * dpr, h = rect.height * dpr, primary = button.classList.contains('primary'),danger = button.classList.contains('stop-task');
      // Avoid blue primary artwork leaking into the adjacent red stop action.
      ctx.save(); ctx.beginPath(); ctx.rect(x - 4*dpr, y - 4*dpr, w + 8*dpr, h + 8*dpr); ctx.clip();
      ctx.fillStyle = primary ? '#153d8a' : danger ? dark ? '#4c2936' : '#f4dddd' : dark ? '#20334e' : '#dae6f7';
      ctx.fillRect(x - 28*dpr, y - 12*dpr, w + 56*dpr, h + 24*dpr);
      ctx.fillStyle = primary ? '#255db6' : danger ? '#b66a7a' : dark ? '#40699b' : '#9fbae6';
      ctx.beginPath(); ctx.ellipse(x + w*.25, y + h*1.12, w*.68, h*.92, -.12, 0, Math.PI*2); ctx.fill();
      ctx.fillStyle = primary ? '#3164b6' : dark ? '#2d4b74' : '#edf4ff';
      ctx.beginPath(); ctx.ellipse(x + w*.96, y - h*.18, w*.57, h*.84, -.1, 0, Math.PI*2); ctx.fill();
      ctx.strokeStyle = primary ? '#c4dcff55' : dark ? '#bedaff88' : '#ffffffdd'; ctx.lineWidth = 1.5*dpr;
      ctx.beginPath(); ctx.moveTo(x - 12*dpr, y + h*.85); ctx.quadraticCurveTo(x + w*.5, y + h*.8, x + w + 12*dpr, y + h*.18); ctx.stroke();
      ctx.restore();
    }
  }
  stats() {return {buttons: this.buttons.length, bodies: this.runtime?.system?.jelly.bodies.size || 0, mode: this.runtime?.stats().mode || 'idle'};}
  destroy() {this.dead = true; this.resize.disconnect(); this.observer.disconnect();this.release(); this.runtime?.destroy();}
}

// One reusable optical canvas follows the active dialog's real footer.
// The original footer/buttons return to their original DOM position on close.
export class ModalLiquidActions {
  constructor(options) {this.host = document.createElement('div');this.host.className = 'modal-liquid-dock';this.options = options;this.footer = null;this.actions = null;}
  sync() {
    const active = document.activeElement?.closest('dialog[open]') || [...document.querySelectorAll('dialog[open]')].at(-1);
    const footer = active?.querySelector('.dialog-footer');
    if (footer === this.footer) return;
    this.detach();if (!footer) return;
    this.footer = footer;footer.before(this.host);this.host.append(footer);
    if (!this.actions) this.actions = new LiquidActions(this.host,this.options);else this.actions.refresh(true);
  }
  detach() {
    if (this.footer) {this.actions?.release();this.host.before(this.footer);this.footer = null;}
    this.host.remove();this.actions?.refresh(true);this.runtime?.stop();
  }
  get runtime() {return this.actions?.runtime;}
  destroy() {this.detach();this.actions?.destroy();}
}
