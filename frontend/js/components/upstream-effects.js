import {bindChoiceGroup} from '../../vendor/design-systems/lens/components.js';
import {LensRuntime, ENHANCED_MATERIAL, LENS_ORIGIN, drawApplicationArtwork, drawToolbarArtwork} from './lens-runtime.js';
import {ParticleFeedback} from './particle-feedback.js';
import {appearance} from '../appearance.js';
import {LiquidActions, ModalLiquidActions} from './liquid-actions.js';
import {GlassControls} from './glass-controls.js';
import {ListMist} from './list-mist.js';
import {desktopHost, isDesktopHost} from '../channel.js';

const TOOLBAR_MATERIAL = Object.freeze({refraction: .48, blur: .08, dispersion: .12});
const TOOLBAR_STANDARD = Object.freeze({refraction: .32, blur: .10, dispersion: .06});
const materialKey = state => [state.resolvedTheme,state.glassEnabled,state.particlesEnabled,state.reducedMotion,state.strength,state.mistEnabled].join('|');

export class Effects {
  constructor(host, canvas) {
    this.appearanceKey = materialKey(appearance.state);
    Object.assign(this, {glassEnabled: appearance.state.glassEnabled, particlesEnabled: appearance.state.particlesEnabled,
      manualReduced: appearance.state.reducedMotion, strength: appearance.state.strength, mistEnabled: appearance.state.mistEnabled});
    this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.abort = new AbortController();
    this.runtimes = [];
    this.particles = new ParticleFeedback(canvas, () => this.reduced);

    const stage = document.createElement('div'); stage.className = 'workspace-lens-stage';
    host.before(stage); stage.append(host);
    host.classList.add('lg-surface'); host.dataset.glass = 'panel';
    host.querySelectorAll('button').forEach(button => {
      button.classList.add('lg-surface'); button.dataset.glass = 'button'; button.dataset.lgDrag = 'tether';
    });
    this.runtimes.push(new LensRuntime(stage, {material: TOOLBAR_MATERIAL, elasticity: .62, artwork: drawToolbarArtwork}));

    const filters = document.querySelector('.status-filters');
    const filterStage = document.createElement('div'); filterStage.className = 'filter-lens-stage';
    filters.before(filterStage); filterStage.append(filters);
    filters.querySelectorAll('[data-filter]').forEach(button => {
      button.dataset.choice = button.dataset.filter;
      button.dataset.glass = 'chip'; button.dataset.lgDrag = 'tether'; button.classList.add('lg-surface');
    });
    this.choice = bindChoiceGroup(filters, {value: 'all', selectionColor: 'green', onChange: value => this.onFilter?.(value)});
    this.activeFilter = 'all';
    this.runtimes.push(new LensRuntime(filterStage, {elasticity: .68, artwork: drawApplicationArtwork}));
    this.actions = [document.getElementById('inspector-actions'), document.querySelector('.work-footer')].map(host => new LiquidActions(host, () => ({enabled:this.glassEnabled,reduced:this.reduced,strength:this.strength})));
    this.mist = new ListMist(document.getElementById('file-list'));
    const options = () => ({enabled:this.glassEnabled,reduced:this.reduced,strength:this.strength});
    this.modalActions = new ModalLiquidActions(options);this.buttons = new GlassControls(options);this.taskBusy = false;
    document.addEventListener('yingxu:overlay', () => {
      this.modalActions.sync();this.updateSuspension();this.buttons.schedule();
    }, {signal:this.abort.signal});

    this.motion.addEventListener('change', () => this.configure(), {signal: this.abort.signal});
    appearance.addEventListener('change', () => {
      const state = appearance.state;
      const key = materialKey(state);
      if (key === this.appearanceKey) {this.onChange?.();return;}
      this.appearanceKey = key;
      Object.assign(this, {glassEnabled: state.glassEnabled, particlesEnabled: state.particlesEnabled,
        manualReduced: state.reducedMotion, strength: state.strength, mistEnabled: state.mistEnabled});
      this.allRuntimes.forEach(runtime => runtime.setTheme(state.resolvedTheme));
      this.configure();
    }, {signal: this.abort.signal});
    document.addEventListener('visibilitychange', () => {if (document.hidden) this.particles.stop();}, {signal: this.abort.signal});
    window.addEventListener('pagehide', () => this.destroy(), {once: true, signal: this.abort.signal});
    this.configure();
    desktopHost().then(host => {
      if (this.abort.signal.aborted) return;
      this.setOverlayActive = host.setOverlayActive;
      this.updateSuspension();
    }).catch(()=>{});
  }
  get reduced() {return this.motion.matches || this.manualReduced;}
  get allRuntimes() {return [...this.runtimes,...this.actions.map(action => action.runtime),this.modalActions?.runtime,this.progressRuntime].filter(Boolean);}
  updateSuspension() {
    const overlay = Boolean(document.querySelector('dialog[open]'));
    const native = isDesktopHost();
    if (overlay) {clearTimeout(this.resumeTimer);this.overlaySettling = false;}
    else if (native && this.hadOverlay) {
      this.overlaySettling = true;
      clearTimeout(this.resumeTimer);
      this.resumeTimer = setTimeout(()=>{this.overlaySettling=false;this.updateSuspension();},120);
    }
    this.hadOverlay = overlay;
    const held = overlay || Boolean(this.overlaySettling);
    this.setOverlayActive?.(held);
    [...this.runtimes,...this.actions.map(action=>action.runtime),this.progressRuntime].filter(Boolean)
      .forEach(runtime=>runtime.setOccluded(native && held));
    this.mist.suspended = this.taskBusy || held;
    if (this.mist.suspended) {this.mist.stop();this.particles.stop();}else this.mist.wake(450);
  }
  setTaskBusy(value) {if (this.taskBusy === value) return;this.taskBusy = value;this.updateSuspension();}
  syncFilter(status) {
    if (status !== this.activeFilter) {this.activeFilter = status; this.choice.setValue(status);}
  }
  configure() {
    document.documentElement.dataset.reduced = String(this.reduced);
    for (const runtime of this.allRuntimes) {
      runtime.setReduced(this.manualReduced);
      runtime.setMaterial(runtime === this.runtimes[0]
        ? (this.strength === 'standard' ? TOOLBAR_STANDARD : TOOLBAR_MATERIAL)
        : (this.strength === 'standard' ? 'thick' : ENHANCED_MATERIAL));
      if (this.glassEnabled) runtime.start(); else runtime.stop();
    }
    this.particles.enabled = this.particlesEnabled;
    if (!this.particlesEnabled || this.reduced) this.particles.stop();
    this.mist.configure({enabled:this.mistEnabled,reduced:this.reduced});
    this.buttons.configure();this.buttons.schedule();
    this.onChange?.();
  }
  burst(element) {this.particles.burst(element);}
  stats() {
    const entries = this.allRuntimes.map(runtime => runtime.stats());
    return {
      glassMode: entries.some(item => item.mode === 'webgl2') ? 'webgl2' : 'fallback',
      glassEnabled: this.glassEnabled, reduced: this.reduced, strength: this.strength,
      glassFrames: entries.reduce((sum, item) => sum + item.frames, 0),
      glassRunning: entries.some(item => item.running),
      particleFrames: this.particles.frames, particleRunning: Boolean(this.particles.raf),
      origin: LENS_ORIGIN, surfaces: entries.reduce((sum, item) => sum + item.surfaces, 0),
      actions: this.actions.map(action => action.stats()),buttons:this.buttons.stats(),dialog:this.modalActions.actions?.stats() || null,mist: this.mist.stats(),
    };
  }
  destroy() {clearTimeout(this.resumeTimer);this.particles.stop();this.buttons.destroy();this.modalActions.destroy();this.progressRuntime?.destroy(); this.choice.destroy(); this.runtimes.forEach(runtime => runtime.destroy()); this.actions.forEach(action => action.destroy()); this.mist.destroy(); this.abort.abort();}
}
