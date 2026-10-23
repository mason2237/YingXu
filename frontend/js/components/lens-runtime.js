import {createGlassSystem} from '../../vendor/design-systems/lens/runtime.js';

export const LENS_ORIGIN = Object.freeze({
  repository: 'ruiqichenbiec/design-systems',
  commit: '7a424c93b9be13cf835b91ea67495fec2ec0584e',
  version: '1.1.0-showcase.1',
});

export const ENHANCED_MATERIAL = Object.freeze({refraction: .98, blur: .12, dispersion: .45});

// This draws only application-owned decoration; no DOM/desktop/file capture.
export function drawWorkbenchArtwork(ctx, {width, height, dpr}) {
  const dark = document.documentElement.dataset.theme === 'dark';
  ctx.fillStyle = dark ? '#1e3049' : '#e5edf8';
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = dark ? '#41618c' : '#b3c6e3';
  ctx.lineWidth = Math.max(1, dpr);
  const step = 34 * dpr;
  for (let x = -height; x < width; x += step) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + height, height); ctx.stroke();
  }
  ctx.fillStyle = dark ? '#3c639a' : '#8baeea';
  ctx.beginPath(); ctx.arc(width * .16, height * 1.1, height * .95, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = dark ? '#2c466b' : '#c9dbf6';
  ctx.beginPath(); ctx.arc(width * .81, -height * .25, height * 1.05, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = dark ? '#b4d3ff99' : '#ffffffbc';
  ctx.lineWidth = 3 * dpr;
  ctx.beginPath(); ctx.moveTo(0, height * .67); ctx.lineTo(width, height * .24); ctx.stroke();
}

export function drawApplicationArtwork(ctx, {width, height, dpr}) {
  const dark = document.documentElement.dataset.theme === 'dark';
  ctx.fillStyle = dark ? '#20334e' : '#e7effb'; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = dark ? '#3d6094' : '#b8ceee';
  ctx.beginPath(); ctx.moveTo(0, height * .3);
  ctx.bezierCurveTo(width * .16, height * 1.25, width * .35, -height * .3, width * .55, height * .72);
  ctx.lineTo(width * .55, height); ctx.lineTo(0, height); ctx.closePath(); ctx.fill();
  ctx.fillStyle = dark ? '#2b466b' : '#d4e2f7';
  ctx.beginPath(); ctx.moveTo(width * .45, 0);
  ctx.bezierCurveTo(width * .65, height * 1.2, width * .8, -height * .4, width, height * .3);
  ctx.lineTo(width, 0); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = dark ? '#a6c7f78a' : '#ffffff9a'; ctx.lineWidth = 2 * dpr;
  ctx.beginPath(); ctx.moveTo(0, height * .8); ctx.quadraticCurveTo(width * .6, height * .8, width, height * .12); ctx.stroke();
}

// A quieter backing for the wide toolbar; action buttons keep enhanced optics.
export function drawToolbarArtwork(ctx, {width, height, dpr}) {
  const dark = document.documentElement.dataset.theme === 'dark';
  ctx.fillStyle = dark ? '#1d2b3e' : '#f3f7fc'; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = dark ? '#25384f' : '#e8eff9';
  ctx.beginPath(); ctx.moveTo(0, height * .76);
  ctx.bezierCurveTo(width * .25, height * .35, width * .65, height * 1.1, width, height * .46);
  ctx.lineTo(width, height); ctx.lineTo(0, height); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = dark ? '#a6c7f737' : '#ffffffb0'; ctx.lineWidth = Math.max(1, dpr);
  ctx.beginPath(); ctx.moveTo(0, height * .74);
  ctx.bezierCurveTo(width * .3, height * .4, width * .68, height, width, height * .45); ctx.stroke();
}

// All optics, compositing and gestures come from unchanged Lens files.
// This adapter only owns lifecycle, application preferences and diagnostics.
export class LensRuntime {
  constructor(stage, {material = ENHANCED_MATERIAL, artwork = drawWorkbenchArtwork,
    elasticity = .42, reduced = false, audio = false} = {}) {
    this.stage = stage;
    this.material = material;
    this.artwork = artwork;
    this.theme = document.documentElement.dataset.theme || 'light';
    this.backdrop = 'workbench';
    this.elasticity = elasticity;
    this.manualReduced = reduced;
    this.audioEnabled = audio;
    this.frames = 0;
    this.enabled = true;
    this.restoreTimer = 0;
    this.system = null;
    this.destroyed = false;
    this.media = matchMedia('(prefers-reduced-motion: reduce)');
    this.abort = new AbortController();
    this.media.addEventListener('change', () => this.applyMotion(), {signal: this.abort.signal});
    this.start();
    document.addEventListener('visibilitychange', () => {
      const system = this.system;
      if (!system) return;
      if (document.hidden) {
        system.sound.stop();
        cancelAnimationFrame(system.jelly.frame); system.jelly.frame = 0;
        if (system.renderer) {cancelAnimationFrame(system.renderer.frame); system.renderer.frame = 0;}
      } else {
        system.jelly.wake();
        if (system.renderer?.lost && system.renderer.gpuLease?.active) system.renderer.resumeGPU();
        system.renderer?.invalidate();
      }
    }, {signal: this.abort.signal});
  }

  get reduced() {return this.manualReduced || this.media.matches;}

  start() {
    if (this.destroyed) return;
    this.enabled = true; this.stage.classList.remove('opaque');
    if (this.system) {this.system.renderer?.set({opaque: false}); if (this.system.renderer?.lost) this.system.renderer.resumeGPU(); return;}
    this.system = createGlassSystem(this.stage, {
      material: this.material, scene: this.theme === 'dark' ? 'ocean' : 'grid', artwork: this.artwork,
      motion: false, elasticity: this.elasticity,
      audio: {enabled: this.audioEnabled, storage: null},
    });
    // Removed/reparented controls must not retain an old controller's gesture.
    // Keep upstream physics unchanged; reduced motion disables pointer travel.
    const jelly = this.system.jelly, grab = jelly.grab.bind(jelly);
    jelly.grab = (body,event) => {
      if (this.reduced || !this.enabled || jelly.bodies.get(body.element) !== body) return;
      grab(body,event);
    };
    for (const body of jelly.bodies.values()) if (body.element.matches('button')) body.maxTravel = 12;
    const renderer = this.system.renderer;
    if (renderer) {
      // Qt's native compositor can keep references to a canvas mailbox. Keep
      // these few contexts on ordinary viewport suspension; release on destroy.
      // This changes lifecycle only, never upstream optical/rendering math.
      const resume = renderer.resumeGPU.bind(renderer);
      renderer.suspendGPU = () => {
        renderer.suspended = true; cancelAnimationFrame(renderer.frame); renderer.frame = 0;
        renderer.canvas.hidden = true; renderer.canvas.dataset.gpuState = 'suspended';
        this.stage.classList.remove('webgl-ready'); this.stage.classList.add('fallback');
      };
      renderer.resumeGPU = () => {
        if (renderer.gl?.isContextLost()) {
          // Chromium/Qt requires restoration after the loss event has returned.
          // Keep the extension acquired before loss; getExtension is null now.
          if (renderer.lossObserved && !this.restoreTimer && !this.destroyed) {
            this.restoreTimer = setTimeout(() => {
              this.restoreTimer = 0;
              if (!this.destroyed && this.enabled && !document.hidden && renderer.gl?.isContextLost()) renderer.contextExtension?.restoreContext();
            }, 150);
          }
          return;
        }
        if (!renderer.gl || !renderer.programs) {resume(); return;}
        renderer.suspended = false; renderer.lost = false; renderer.resize();
        renderer.canvas.hidden = false; renderer.canvas.dataset.gpuState = 'active';
        this.stage.classList.add('webgl-ready'); this.stage.classList.remove('fallback');
        renderer.lastTime = 0; renderer.invalidate(150);
      };
      // Same resource cleanup as upstream, with native canvas destruction left
      // to WebEngine. Forcing loseContext while Qt retains a mailbox produces
      // stale shared-image warnings. All programs/textures/buffers are deleted.
      renderer.destroy = () => {
        renderer.destroyed = true; cancelAnimationFrame(renderer.frame); renderer.frame = 0;
        renderer.abort.abort(); renderer.resizeObserver.disconnect();
        renderer.mutationObserver.disconnect(); renderer.intersectionObserver.disconnect();
        renderer.gpuLease?.destroy();
        const gl = renderer.gl;
        if (!gl) return;
        Object.values(renderer.programs || {}).forEach(program => gl.deleteProgram(program.p));
        Object.values(renderer.textures || {}).forEach(texture => gl.deleteTexture(texture));
        (renderer.targets || []).forEach(target => gl.deleteFramebuffer(target.framebuffer));
        gl.deleteBuffer(renderer.buffer); gl.deleteVertexArray(renderer.vao);
      };
      const render = renderer.render.bind(renderer);
      renderer.render = now => {this.frames++; render(now);};
    }
    this.applyMotion();
  }

  applyMotion() {
    if (!this.system) return;
    this.stage.dataset.lensReduced = String(this.reduced);
    this.system.jelly.reduced = this.reduced;
    this.system.jelly.setIntensity(this.reduced ? 0 : this.elasticity);
    if (this.reduced) this.system.jelly.cancel(true);
    if (this.system.renderer) {
      this.system.renderer.reducedMotion = this.reduced;
      this.system.renderer.invalidate();
    }
  }

  setReduced(value) {this.manualReduced = Boolean(value); this.applyMotion();}
  setMaterial(value) {this.material = value; this.system?.setMaterial(value);}
  setBackdrop(name) {
    if (!['workbench', 'aurora', 'sunset', 'ocean', 'grid'].includes(name)) throw new TypeError('Unknown backdrop');
    this.backdrop = name;
    if (!this.system?.renderer) return;
    this.system.renderer.artwork = name === 'workbench' ? this.artwork : null;
    this.system.setScene(name === 'workbench' ? this.theme === 'dark' ? 'ocean' : 'grid' : name);
  }
  setTheme(theme) {
    this.theme = theme; this.setBackdrop(this.backdrop);
    const renderer = this.system?.renderer;
    if (this.enabled && renderer?.gl && !renderer.suspended && !renderer.lost && !document.hidden) {
      // View Transition DOM updates suspend rAF. Paint the new artwork before
      // its snapshot without waiting on a frame that cannot run yet.
      cancelAnimationFrame(renderer.frame); renderer.frame = 0;
      renderer.render(performance.now()); renderer.gl.flush();
    }
  }
  setAudio(value) {this.audioEnabled = Boolean(value); this.system?.sound.set({enabled: this.audioEnabled});}

  stop() {
    if (!this.system) return;
    this.enabled = false; this.stage.classList.add('opaque');
    this.system.renderer?.set({opaque: true});
  }

  stats() {
    const renderer = this.system?.renderer;
    const active = this.enabled && this.stage.classList.contains('webgl-ready') && !renderer?.suspended;
    return {
      mode: active ? 'webgl2' : 'fallback', frames: this.frames,
      running: Boolean(renderer?.frame || this.system?.jelly.frame),
      surfaces: this.stage.querySelectorAll('[data-glass]').length,
      gpuState: renderer?.canvas.dataset.gpuState || 'off',
      reduced: this.reduced, destroyed: this.destroyed,
      sound: this.system?.sound.snapshot() || {enabled: false, played: 0},
    };
  }

  destroy() {
    if (this.destroyed) return;
    clearTimeout(this.restoreTimer); this.restoreTimer = 0;
    this.system?.destroy(); this.system = null;
    this.abort.abort(); this.destroyed = true;
  }
}
