import {windowInactive,onWindowVisibility} from '../visibility.js';
// Existing project particle feedback, retained separately from upstream optics.
export class ParticleFeedback {
  constructor(canvas, reduced) {
    this.canvas = canvas; this.reduced = reduced;
    this.context = canvas.getContext('2d'); this.raf = 0; this.frames = 0; this.enabled = true;
  }
  stop() {
    cancelAnimationFrame(this.raf); this.raf = 0;
    this.context?.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
  burst(element) {
    this.stop();
    if (!this.enabled || this.reduced() || windowInactive() || !this.context) return;
    const box = element.getBoundingClientRect(), x = box.left + box.width / 2, y = box.top + box.height / 2;
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    this.canvas.width = innerWidth * dpr; this.canvas.height = innerHeight * dpr;
    const start = performance.now();
    const palette = getComputedStyle(document.documentElement);
    const colors = [palette.getPropertyValue('--blue').trim(), palette.getPropertyValue('--soft').trim()];
    const frame = now => {
      const t = (now - start) / 650, ctx = this.context;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, innerWidth, innerHeight);
      if (t >= 1 || windowInactive() || this.reduced() || !this.enabled) {this.stop(); return;}
      for (let i = 0; i < 16; i++) {
        const angle = i * Math.PI * 2 / 16, distance = 10 + 38 * t;
        ctx.globalAlpha = (1 - t) * .7; ctx.fillStyle = colors[i % 3 ? 0 : 1];
        ctx.beginPath(); ctx.arc(x + Math.cos(angle) * distance, y + Math.sin(angle) * distance * .55 - 9 * t, 1.2 + (i % 2) * .6, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1; this.frames++; this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }
}
