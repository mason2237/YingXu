import {JellyController} from '../../vendor/design-systems/lens/internal/jelly.js';

const OWNED = '.workspace-lens-stage,.filter-lens-stage,.liquid-actions-stage';

// Every semantic button gets the same optical shell. Small/text/icon controls
// use CSS glass; existing action groups retain original Lens GPU refraction.
// One upstream spring controller covers all remaining controls, including
// dynamically generated candidates, history, commands and popover buttons.
export class GlassControls {
  constructor(options) {
    this.options = options;this.dead = false;this.frame = 0;this.cache = new WeakMap();this.buttons = [];
    this.abort = new AbortController();this.jelly = new JellyController(document.body,null,{intensity:.72});
    const grab = this.jelly.grab.bind(this.jelly);
    this.jelly.grab = (body,event) => {
      if (options().reduced || !options().enabled || this.jelly.bodies.get(body.element) !== body || body.element.closest(OWNED)) return;
      grab(body,event);
    };
    this.observer = new MutationObserver(() => this.schedule());
    this.observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','disabled','hidden','open']});
    // Suppress a real drag even when reduced motion disables the spring.
    const signal = this.abort.signal;
    document.addEventListener('pointerdown',event => {
      const button = event.target.closest?.('button');
      if (event.button === 0 && event.isPrimary && button && !button.disabled) this.pointer = {button,id:event.pointerId,x:event.clientX,y:event.clientY,moved:false};
    },{capture:true,signal});
    window.addEventListener('pointermove',event => {const p = this.pointer;if (p?.id === event.pointerId) p.moved ||= Math.hypot(event.clientX-p.x,event.clientY-p.y)>5;},{capture:true,passive:true,signal});
    const release = event => {const p = this.pointer;if (!p || p.id !== event.pointerId) return;if (p.moved) this.block = {button:p.button,until:performance.now()+400};this.pointer = null;};
    window.addEventListener('pointerup',release,{capture:true,signal});window.addEventListener('pointercancel',release,{capture:true,signal});
    document.addEventListener('click',event => {if (this.block && performance.now()<this.block.until && this.block.button.contains(event.target)) {event.preventDefault();event.stopImmediatePropagation();this.block = null;}},{capture:true,signal});
    document.addEventListener('pointermove',event => {
      if (this.options().reduced) return;
      const button = event.target.closest?.('button.liquid-button');if (!button || button.disabled) return;
      const rect = button.getBoundingClientRect();
      button.style.setProperty('--liquid-light-x',`${Math.round((event.clientX-rect.left)/Math.max(1,rect.width)*100)}%`);
      button.style.setProperty('--liquid-light-y',`${Math.round((event.clientY-rect.top)/Math.max(1,rect.height)*100)}%`);
    },{passive:true,signal:this.abort.signal});
    this.refresh();
  }
  schedule() {if (!this.frame && !this.dead) this.frame = requestAnimationFrame(() => {this.frame = 0;this.refresh();});}
  refresh() {
    if (this.dead) return;
    this.buttons = [...document.querySelectorAll('button')];
    const live = new Set(this.buttons.filter(button => !button.closest(OWNED)));
    for (const [element,body] of this.jelly.bodies) if (!live.has(element)) {
      if (this.jelly.gesture?.body === body) this.jelly.cancel(true);
      this.cache.set(element,body);this.jelly.bodies.delete(element);
    }
    for (const button of this.buttons) {
      if (!button.classList.contains('liquid-button')) button.classList.add('liquid-button');
      const renderer = button.matches('[data-glass]') && button.closest('.webgl-ready:not(.opaque)') ? 'webgl' : 'css';
      if (button.dataset.liquidRenderer !== renderer) button.dataset.liquidRenderer = renderer;
      if (!live.has(button) || this.jelly.bodies.has(button)) continue;
      const body = this.cache.get(button);
      if (body) this.jelly.bodies.set(button,body);
      else this.cache.set(button,this.jelly.register(button,{mode:'tether',maxTravel:12}));
    }
    this.configure();
  }
  configure() {
    const {enabled,reduced} = this.options();
    document.documentElement.dataset.liquidButtons = String(enabled);
    this.jelly.reduced = reduced || !enabled;
    const intensity = reduced || !enabled ? 0 : .72;
    if (this.jelly.intensity !== intensity) {this.jelly.setIntensity(intensity);if (!intensity) this.jelly.cancel(true);}
  }
  stats() {return {buttons:this.buttons.length,bodies:this.jelly.bodies.size,gpu:this.buttons.filter(button => button.dataset.liquidRenderer === 'webgl').length};}
  destroy() {this.dead = true;cancelAnimationFrame(this.frame);this.observer.disconnect();this.abort.abort();this.jelly.destroy();}
}
