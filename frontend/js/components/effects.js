// Local optical material: refract a controlled procedural backdrop, never file text.
const VERTEX = `#version 300 es
in vec2 position;
void main(){gl_Position=vec4(position,0.,1.);}`;
const FRAGMENT = `#version 300 es
precision highp float;
uniform vec2 resolution;
uniform vec2 pointer;
uniform float press;
out vec4 color;
vec3 scene(vec2 uv){
  vec3 base=vec3(.937,.953,.978);
  float band=exp(-pow((uv.x-.07)*9.,2.));
  base=mix(base,vec3(.85,.9,.979),band*.42);
  base+=vec3(.026)*smoothstep(.2,.9,uv.y);
  base+=.012*sin(uv.x*9.+uv.y*1.4);
  return base;
}
void main(){
  vec2 p=gl_FragCoord.xy;
  float r=min(12.,resolution.y*.2);
  vec2 center=resolution*.5;
  vec2 q=abs(p-center)-(center-vec2(r+1.));
  float d=length(max(q,0.))+min(max(q.x,q.y),0.)-r;
  vec2 inner=clamp(p,vec2(r+1.),resolution-vec2(r+1.));
  vec2 n=normalize(p-inner+vec2(.0001));
  float edge=exp(-max(-d,0.)/7.);
  vec2 uv=p/resolution;
  vec2 sampleUV=uv+n*edge*vec2(.015,.24)*(1.+press*.32);
  vec3 glass=scene(sampleUV);
  float rim=exp(-abs(d+1.2)*1.7);
  glass=mix(glass,vec3(1.),rim*.72);
  float highlight=exp(-pow((uv.x-pointer.x)*4.,2.))*exp(-pow((uv.y-pointer.y)*1.4,2.));
  glass+=vec3(.015+press*.018)*highlight;
  color=vec4(glass,1.-smoothstep(-.4,.6,d));
}`;

class GlassSurface {
  constructor(host, notify) {
    this.host = host; this.notify = notify; this.frames = 0; this.pointer = [.5, .8]; this.enabled = true; this.reduced = false; this.raf = 0; this.pressedAt = 0; this.press = 0;
    this.canvas = document.createElement('canvas'); this.canvas.className = 'glass-canvas'; this.canvas.setAttribute('aria-hidden', 'true'); host.prepend(this.canvas);
    try {
      const gl = this.canvas.getContext('webgl2', {alpha: true, antialias: false, powerPreference: 'low-power', depth: false, preserveDrawingBuffer: true});
      if (!gl) throw new Error('WebGL unavailable');
      this.gl = gl;
      const shader = (type, code) => {const value = gl.createShader(type); gl.shaderSource(value, code); gl.compileShader(value); if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw new Error('Shader unavailable'); return value;};
      this.program = gl.createProgram(); gl.attachShader(this.program, shader(gl.VERTEX_SHADER, VERTEX)); gl.attachShader(this.program, shader(gl.FRAGMENT_SHADER, FRAGMENT)); gl.linkProgram(this.program);
      if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) throw new Error('Program unavailable');
      gl.useProgram(this.program); const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(this.program, 'position'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      this.mode = 'webgl2';
    } catch {this.fallback();}
    this.canvas.addEventListener('webglcontextlost', event => {event.preventDefault(); this.fallback(); this.notify();});
    this.resize = new ResizeObserver(() => this.draw()); this.resize.observe(host);
    host.addEventListener('pointermove', event => {if (this.reduced || !this.enabled || document.hidden) return; this.point(event); this.schedule();});
    host.addEventListener('pointerdown', event => {if (event.button || this.reduced || !this.enabled || document.hidden) return; this.point(event); this.pressedAt = performance.now(); this.schedule();});
    host.addEventListener('pointerleave', () => {this.pointer = [.5, .8]; this.schedule();});
  }
  point(event) {const r = this.host.getBoundingClientRect(); this.pointer = [(event.clientX-r.left)/r.width, 1-(event.clientY-r.top)/r.height];}
  schedule() {
    if (this.raf || !this.enabled || !this.gl || document.hidden) return;
    this.raf = requestAnimationFrame(now => {
      this.raf = 0;
      const t = (now-this.pressedAt)/180;
      this.press = this.pressedAt && t < 1 ? Math.sin(Math.PI*Math.max(0,t)) : 0;
      this.draw();
      if (this.press) this.schedule(); else this.pressedAt = 0;
    });
  }
  stop() {cancelAnimationFrame(this.raf); this.raf = 0; this.pressedAt = 0; this.press = 0;}
  fallback() {this.stop(); this.mode = 'fallback'; this.canvas.hidden = true; this.gl = null; this.host.dataset.glass = 'fallback';}
  draw() {
    if (!this.enabled || !this.gl || document.hidden) return;
    const gl = this.gl, dpr = Math.min(devicePixelRatio || 1, 1.5), r = this.host.getBoundingClientRect();
    const width = Math.round(r.width*dpr), height = Math.round(r.height*dpr);
    if (!width || !height) return;
    if (this.canvas.width !== width || this.canvas.height !== height) {this.canvas.width = width; this.canvas.height = height;}
    gl.viewport(0, 0, width, height); gl.useProgram(this.program);
    gl.uniform2f(gl.getUniformLocation(this.program, 'resolution'), width, height);
    gl.uniform2f(gl.getUniformLocation(this.program, 'pointer'), ...this.pointer);
    gl.uniform1f(gl.getUniformLocation(this.program, 'press'), this.press);
    gl.drawArrays(gl.TRIANGLES, 0, 6); this.frames++;
  }
  configure(enabled, reduced) {this.stop(); this.enabled = enabled; this.reduced = reduced; this.canvas.hidden = !enabled || !this.gl; this.draw();}
}

export class Effects {
  constructor(host, canvas) {
    this.canvas = canvas; this.context = canvas.getContext('2d'); this.raf = 0; this.particleFrames = 0;
    this.glassEnabled = true; this.particlesEnabled = true; this.manualReduced = false; this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.glass = new GlassSurface(host, () => this.onChange?.());
    this.motion.addEventListener('change', () => this.configure());
    document.addEventListener('visibilitychange', () => {if (document.hidden) this.stop(); else this.glass.draw();});
    window.addEventListener('pagehide', () => this.stop());
    this.configure();
  }
  get reduced() {return this.motion.matches || this.manualReduced;}
  configure() {document.documentElement.dataset.reduced = String(this.reduced); this.glass.configure(this.glassEnabled, this.reduced); if (this.reduced || !this.particlesEnabled) this.stop(); this.onChange?.();}
  stop() {cancelAnimationFrame(this.raf); this.raf = 0; this.glass.stop(); if (this.context) this.context.clearRect(0,0,this.canvas.width,this.canvas.height);}
  burst(element) {
    this.stop(); if (!this.particlesEnabled || this.reduced || document.hidden || !this.context) return;
    const box = element.getBoundingClientRect(), x = box.left+box.width/2, y = box.top+box.height/2;
    const dpr = Math.min(devicePixelRatio || 1, 1.5); this.canvas.width = innerWidth*dpr; this.canvas.height = innerHeight*dpr;
    const start = performance.now();
    const frame = now => {
      const t = (now-start)/650, ctx = this.context;
      ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,innerWidth,innerHeight);
      if (t >= 1 || document.hidden || this.reduced || !this.particlesEnabled) {this.stop(); return;}
      for (let i=0;i<16;i++) {const a = i*Math.PI*2/16; const distance = 10+38*t; ctx.globalAlpha = (1-t)*.7; ctx.fillStyle = i%3 ? '#8caee9' : '#bcc9df'; ctx.beginPath(); ctx.arc(x+Math.cos(a)*distance,y+Math.sin(a)*distance*.55-9*t,1.2+(i%2)*.6,0,Math.PI*2); ctx.fill();}
      ctx.globalAlpha = 1; this.particleFrames++; this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }
  stats() {return {glassMode: this.glass.mode, glassEnabled: this.glassEnabled, reduced: this.reduced, glassFrames: this.glass.frames, glassRunning: Boolean(this.glass.raf), particleFrames: this.particleFrames, particleRunning: Boolean(this.raf)};}
}
