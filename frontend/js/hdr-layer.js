// Local HDR highlights only. No full-page readback or copy of the HTML scene.
import {appearance} from './appearance.js';

const shader = `
struct Params {size:vec2f,pointer:vec2f,intensity:f32,calibration:f32,pad:vec2f};
@group(0) @binding(0) var<uniform> u:Params;
@vertex fn vertex(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
  var p=array<vec2f,3>(vec2f(-1.,-1.),vec2f(3.,-1.),vec2f(-1.,3.));return vec4f(p[i],0.,1.);
}
@fragment fn fragment(@builtin(position) p:vec4f)->@location(0) vec4f {
  if(u.calibration>0.) {
    let section=u32(p.x/(u.size.x/3.));
    let value=select(select(1.,2.,section==1u),4.,section>=2u);
    return vec4f(vec3f(value),1.);
  }
  let q=abs(p.xy-u.size*.5)-(u.size*.5-vec2f(18.));
  let distance=length(max(q,vec2f(0.)))+min(max(q.x,q.y),0.)-9.;
  let edge=exp(-abs(distance)*1.8);
  let glow=exp(-abs(distance)*.22)*.055;
  let pointer=exp(-length(p.xy-u.pointer)*.012);
  let alpha=(edge*(.14+pointer*.56)+glow*pointer)*u.intensity;
  return vec4f(vec3f(.72,.87,1.)*(1.4+pointer*2.)*alpha,alpha);
}`;

export let hdrLayer;
export function startHdrLayer() {
  if (!hdrLayer) hdrLayer = new HdrLayer();
  return hdrLayer;
}

class HdrLayer {
  constructor() {
    this.abort = new AbortController();this.frames = 0;this.raf = 0;this.until = 0;
    this.pointer = [-500,-500];this.calibration = false;
    this.canvas = document.createElement('canvas');this.canvas.id = 'electron-hdr-highlights';
    this.canvas.setAttribute('aria-hidden','true');
    Object.assign(this.canvas.style,{position:'fixed',pointerEvents:'none',zIndex:'8'});
    document.body.append(this.canvas);
    this.observer = new ResizeObserver(() => {this.layout();this.wake();});
    this.observer.observe(document.getElementById('glass-toolbar'));
    window.addEventListener('resize', () => {this.layout();this.wake();},{signal:this.abort.signal});
    window.addEventListener('pointermove', event => {
      if (!this.rect) return;
      this.pointer = [(event.clientX-this.rect.left)*this.scale,(event.clientY-this.rect.top)*this.scale];
      if (event.clientY >= this.rect.top-40 && event.clientY <= this.rect.bottom+40) this.wake(160);
    },{passive:true,signal:this.abort.signal});
    document.addEventListener('yingxu:overlay', () => this.wake(),{signal:this.abort.signal});
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {cancelAnimationFrame(this.raf);this.raf=0;} else this.wake();
    },{signal:this.abort.signal});
    appearance.addEventListener('change', () => this.configure(),{signal:this.abort.signal});
    window.addEventListener('pagehide', () => this.destroy(),{once:true,signal:this.abort.signal});
    this.configure();
  }
  async configure() {
    const state = appearance.state;
    this.enabled = state.nativeHdr && state.displayOutput?.systemHdrEnabled === true;
    this.intensity = state.lighting === 'off' ? 0 : state.lighting === 'soft' ? .4 : 1;
    this.canvas.hidden = !this.enabled;
    if (this.enabled && !this.device && !this.initializing) await this.initialize();
    this.wake();
  }
  async initialize() {
    this.initializing = true;
    try {
      if (!navigator.gpu) throw Error('WebGPU 不可用');
      const adapter = await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
      if (!adapter) throw Error('未找到硬件 WebGPU 适配器');
      const device = await adapter.requestDevice();
      if (this.abort.signal.aborted) {device.destroy();return;}
      this.device = device;this.context = this.canvas.getContext('webgpu');
      this.context.configure({device,format:'rgba16float',alphaMode:'premultiplied',toneMapping:{mode:'extended'}});
      const configured = this.context.getConfiguration();
      if (configured.format !== 'rgba16float' || configured.toneMapping?.mode !== 'extended') throw Error('扩展浮点画布未生效');
      this.uniform = device.createBuffer({size:32,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
      const module = device.createShaderModule({code:shader});
      this.pipeline = await device.createRenderPipelineAsync({layout:'auto',vertex:{module,entryPoint:'vertex'},
        fragment:{module,entryPoint:'fragment',targets:[{format:'rgba16float'}]},primitive:{topology:'triangle-list'}});
      this.group = device.createBindGroup({layout:this.pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:{buffer:this.uniform}}]});
      await globalThis.yingxuHost.hdr.report({configured:true,format:configured.format,toneMapping:configured.toneMapping.mode,
        adapter:[adapter.info?.vendor,adapter.info?.architecture,adapter.info?.description].filter(Boolean).join(' ')});
      device.lost.then(info => {if (!this.abort.signal.aborted) this.fail(info.message);});
      this.layout();this.wake();
    } catch (error) {this.fail(error.message);}
    finally {this.initializing = false;}
  }
  fail(reason) {
    this.canvas.hidden = true;
    globalThis.yingxuHost.hdr.report({configured:false,reason}).catch(()=>{});
  }
  layout() {
    if (!this.device) return;
    const rect = document.getElementById('glass-toolbar').getBoundingClientRect();
    this.rect = {left:rect.left-10,top:rect.top-10,right:rect.right+10,bottom:rect.bottom+10};
    this.scale = Math.min(devicePixelRatio,2);
    Object.assign(this.canvas.style,{left:`${this.rect.left}px`,top:`${this.rect.top}px`,width:`${rect.width+20}px`,height:`${rect.height+20}px`});
    this.canvas.width = Math.round((rect.width+20)*this.scale);this.canvas.height = Math.round((rect.height+20)*this.scale);
  }
  wake(duration = 0) {
    if (!this.pipeline || !this.enabled || document.hidden || this.abort.signal.aborted) return;
    this.until = Math.max(this.until,performance.now()+duration);
    if (!this.raf) this.raf=requestAnimationFrame(now => this.draw(now));
  }
  draw(now) {
    this.raf = 0;
    if (document.hidden || !this.enabled || this.abort.signal.aborted) return;
    const overlay = Boolean(document.querySelector('dialog[open]'));
    this.device.queue.writeBuffer(this.uniform,0,new Float32Array([this.canvas.width,this.canvas.height,...this.pointer,
      overlay ? 0 : this.intensity,this.calibration ? 1 : 0,0,0]));
    const commands=this.device.createCommandEncoder();
    const pass=commands.beginRenderPass({colorAttachments:[{view:this.context.getCurrentTexture().createView(),
      clearValue:{r:0,g:0,b:0,a:0},loadOp:'clear',storeOp:'store'}]});
    pass.setPipeline(this.pipeline);pass.setBindGroup(0,this.group);pass.draw(3);pass.end();
    this.device.queue.submit([commands.finish()]);this.frames++;
    if (now<this.until) this.raf=requestAnimationFrame(time=>this.draw(time));
  }
  // Isolated diagnostic capture of 1x, 2x and 4x paper white. Never touches files.
  setCalibration(value) {this.calibration=Boolean(value);this.wake(value ? 3000 : 0);}
  destroy() {cancelAnimationFrame(this.raf);this.observer.disconnect();this.abort.abort();this.device?.destroy();this.canvas.remove();}
}
