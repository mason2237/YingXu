// Project-owned procedural vapor. Original Lens is used for buttons, not this
// shader. One low-resolution canvas under all virtual rows, never over text.
const VERTEX = `#version 300 es
in vec2 aPosition; out vec2 uv;
void main(){uv=vec2(aPosition.x*.5+.5,.5-aPosition.y*.5);gl_Position=vec4(aPosition,0.,1.);}`;
const FRAGMENT = `#version 300 es
precision highp float;
in vec2 uv; out vec4 color;
uniform vec2 uSize,uPointer,uSelection;
uniform float uTime,uHover,uScroll,uDark;
float hash(vec2 p){vec2 q=fract(p*vec2(.1031,.11369));q+=dot(q,q.yx+19.19);return fract(q.x*q.y*95.37);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<3;i++){v+=a*noise(p);p=p*2.03+3.4;a*=.5;}return v;}
void main(){
  vec2 scale=vec2(uSize.x/uSize.y,1.)*2.8;
  vec2 p=uv*scale; p.y+=uScroll/500.;
  vec2 delta=(uv-uPointer)*scale;
  float light=uHover*exp(-dot(delta*vec2(1.,1.3),delta*vec2(1.,1.3))*1.6);
  // Long, rising strands: no rotating blob, opaque cloud fill or row seams.
  float bend=noise(p*vec2(.9,.8)+vec2(uTime*.06,uTime*.11))-.5;
  vec2 flow=vec2(p.x*2.7+bend*.8+light*delta.x*.08,p.y*.7+uTime*.28);
  float vapor=fbm(flow);
  float breakup=noise(flow*vec2(1.45,3.6)+vec2(-uTime*.09,uTime*.15));
  float strand=exp(-pow((vapor-.48)*15.,2.))*smoothstep(.28,.72,breakup);
  float haze=smoothstep(.48,.78,vapor)*.018;
  float selected=uSelection.x<0.?0.:exp(-pow((uv.y-uSelection.x)/max(uSelection.y*.9,.03),2.));
  // Fine light threads share the vapor pass; no extra canvas or blur layer.
  float thread=exp(-pow((vapor-.50)*75.,2.))*smoothstep(.42,.78,breakup);
  float glow=light*smoothstep(.25,.7,vapor)*.035;
  float edge=smoothstep(0.,.06,uv.y)*(1.-smoothstep(.92,1.,uv.y));
  float opacity=(haze+strand*(.065+selected*.035+light*.055)+thread*(.018+light*.13)+glow)*edge;
  vec3 tint=mix(vec3(.25,.54,.86),vec3(.37,.65,.98),uDark);
  tint=mix(tint,vec3(.64,.86,1.),uDark*clamp(thread+light*.35,0.,.75));
  color=vec4(tint,min(opacity,mix(.15,.19,uDark)));
}`;

export class ListMist {
  constructor(viewport) {
    this.viewport = viewport; this.host = viewport.closest('.list-pane');
    this.canvas = document.createElement('canvas'); this.canvas.className = 'list-mist'; this.canvas.setAttribute('aria-hidden', 'true'); this.host.prepend(this.canvas);
    this.abort = new AbortController(); this.enabled = true; this.reduced = false;
    this.mode = 'fallback'; this.frames = 0; this.raf = 0; this.deadline = 0; this.clock = 0; this.last = 0; this.nextFrame = 0;
    this.pointer = [.5, .5]; this.hover = 0; this.hoverTarget = 0; this.restoreTimer = 0; this.destroyed = false;
    const signal = this.abort.signal;
    this.canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault(); this.stop(); this.mode = 'fallback'; this.syncMode(); this.restore();
    }, {signal});
    this.canvas.addEventListener('webglcontextrestored', () => {this.initialize(); this.resize(); this.wake(900);}, {signal});
    viewport.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch' || this.reduced) return;
      const rect = viewport.getBoundingClientRect();
      this.pointer = [(event.clientX-rect.left)/rect.width,(event.clientY-rect.top)/rect.height];
      this.hoverTarget = 1; this.wake(1800);
    }, {signal, passive: true});
    viewport.addEventListener('pointerleave', () => {this.hoverTarget = 0; if (!this.reduced) this.wake(650);}, {signal});
    viewport.addEventListener('scroll', () => this.wake(450), {signal, passive: true});
    document.addEventListener('visibilitychange', () => {if (document.hidden) this.stop(); else {this.restore(); this.wake(500);}}, {signal});
    this.resizeObserver = new ResizeObserver(() => this.resize()); this.resizeObserver.observe(viewport);
    this.observer = new MutationObserver(() => this.wake(1100));
    this.observer.observe(viewport, {subtree: true, childList: true, attributes: true, attributeFilter: ['hidden','aria-selected','aria-busy']});
    this.initialize(); this.resize();
  }
  initialize() {
    try {
      const gl = this.gl ||= this.canvas.getContext('webgl2', {alpha: true, antialias: false, premultipliedAlpha: false, depth: false});
      if (!gl) {this.mode = 'fallback'; this.syncMode(); return;}
      const shaders = [];
      try {
        for (const [type, source] of [[gl.VERTEX_SHADER,VERTEX],[gl.FRAGMENT_SHADER,FRAGMENT]]) {
          const shader = gl.createShader(type); shaders.push(shader); gl.shaderSource(shader,source); gl.compileShader(shader);
          if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
        }
        this.program = gl.createProgram(); shaders.forEach(shader => gl.attachShader(this.program,shader)); gl.linkProgram(this.program);
        if (!gl.getProgramParameter(this.program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(this.program));
      } finally {shaders.forEach(shader => gl.deleteShader(shader));}
      this.vao = gl.createVertexArray(); gl.bindVertexArray(this.vao); this.buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
      const position = gl.getAttribLocation(this.program,'aPosition'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
      this.uniforms = Object.fromEntries(['uSize','uPointer','uSelection','uTime','uHover','uScroll','uDark'].map(name => [name,gl.getUniformLocation(this.program,name)]));
      this.extension = gl.getExtension('WEBGL_lose_context'); this.mode = 'webgl2';
    } catch (error) {this.mode = 'fallback'; this.canvas.dataset.fallbackReason = String(error.message);}
    this.syncMode();
  }
  syncMode() {
    this.host.dataset.mist = this.enabled ? this.mode : 'off';
    this.canvas.hidden = !this.enabled || this.mode !== 'webgl2' || this.viewport.hidden;
  }
  resize() {
    if (this.destroyed) return;
    const rect = this.viewport.getBoundingClientRect(), parent = this.host.getBoundingClientRect();
    this.width = Math.max(1,this.viewport.clientWidth); this.height = Math.max(1,this.viewport.clientHeight);
    Object.assign(this.canvas.style,{left:`${rect.left-parent.left}px`,top:`${rect.top-parent.top}px`,width:`${this.width}px`,height:`${this.height}px`});
    // Vapor needs soft shapes, not text resolution: 61% fewer pixels than .8x.
    this.canvas.width = Math.ceil(this.width*.5); this.canvas.height = Math.ceil(this.height*.5);
    this.wake(700);
  }
  configure({enabled, reduced}) {
    this.enabled = Boolean(enabled); this.reduced = Boolean(reduced); this.syncMode();
    if (!this.enabled || this.reduced) this.stop();
    if (this.reduced) {this.clock = 0; this.hover = this.hoverTarget = 0;}
    this.restore(); this.draw(); if (!this.reduced) this.wake(1200);
  }
  restore() {
    if (!this.destroyed && this.enabled && !document.hidden && this.gl?.isContextLost() && !this.restoreTimer) {
      this.restoreTimer = setTimeout(() => {this.restoreTimer = 0;if (!this.destroyed && this.enabled && !document.hidden) this.extension?.restoreContext();},150);
    }
  }
  wake(duration = 1000) {
    if (this.destroyed) return;
    this.syncMode();
    if (!this.enabled || this.suspended || this.mode !== 'webgl2' || document.hidden || this.viewport.hidden || this.viewport.getAttribute('aria-busy') === 'true') {this.stop(); return;}
    if (this.reduced) {this.hover = this.hoverTarget; this.draw(); return;}
    this.deadline = performance.now()+duration;
    if (!this.raf) this.raf = requestAnimationFrame(now => this.tick(now));
  }
  tick(now) {
    this.raf = 0;
    if (this.destroyed || this.suspended || document.hidden || !this.enabled || this.reduced || this.viewport.hidden || this.mode !== 'webgl2') {this.stop(); return;}
    // Carry the 60Hz budget across refresh ticks, including 144Hz displays.
    if (!this.last || now+.5 >= this.nextFrame) {
      const elapsed = this.last ? Math.min(now-this.last,60)/1000 : 0;
      this.clock += elapsed; this.last = now;
      this.nextFrame = Math.max((this.nextFrame || now)+1000/60,now+1);
      this.hover += (this.hoverTarget-this.hover)*(1-Math.exp(-elapsed*15)); this.draw();
    }
    if (now < this.deadline) this.raf = requestAnimationFrame(time => this.tick(time));
    else this.last = this.nextFrame = 0;
  }
  draw() {
    const gl = this.gl;
    if (this.destroyed || !this.enabled || document.hidden || this.mode !== 'webgl2' || !gl || gl.isContextLost() || !this.program || this.viewport.hidden) return;
    const row = this.viewport.querySelector('[aria-selected=true]'), rect = row?.getBoundingClientRect(), viewport = this.viewport.getBoundingClientRect();
    const center = rect ? (rect.top-viewport.top+rect.height/2)/this.height : -1;
    const selected = center >= 0 && center <= 1 ? center : -1;
    gl.viewport(0,0,this.canvas.width,this.canvas.height); gl.useProgram(this.program); gl.bindVertexArray(this.vao);
    const u = this.uniforms;
    gl.uniform2f(u.uSize,this.width,this.height); gl.uniform2f(u.uPointer,...this.pointer);
    gl.uniform2f(u.uSelection,selected,(rect?.height || 84)/this.height);
    gl.uniform1f(u.uTime,this.clock); gl.uniform1f(u.uHover,this.reduced ? 0 : this.hover); gl.uniform1f(u.uScroll,this.viewport.scrollTop);
    gl.uniform1f(u.uDark,document.documentElement.dataset.theme === 'dark' ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES,0,3); this.frames++;
  }
  stop() {cancelAnimationFrame(this.raf); this.raf = 0; this.last = this.nextFrame = 0;}
  stats() {return {mode:this.enabled ? this.mode : 'off',enabled:this.enabled,reduced:this.reduced,frames:this.frames,running:Boolean(this.raf),canvases:this.canvas.isConnected ? 1 : 0,destroyed:this.destroyed};}
  destroy() {
    this.destroyed = true; this.stop(); clearTimeout(this.restoreTimer); this.abort.abort(); this.resizeObserver.disconnect(); this.observer.disconnect();
    if (this.gl && !this.gl.isContextLost()) {this.gl.deleteProgram(this.program);this.gl.deleteBuffer(this.buffer);this.gl.deleteVertexArray(this.vao);}
    this.canvas.remove(); this.host.dataset.mist = 'off';
    this.mode = 'off';
  }
}
