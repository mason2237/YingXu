// File authority stays in Python and the trusted main process.
const {app,BrowserWindow,ipcMain,protocol,nativeTheme,screen,dialog,shell,clipboard}=require('electron');
const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const fs=require('node:fs');
const path=require('node:path');

const ROOT=app.isPackaged?path.dirname(process.execPath):path.resolve(__dirname,'../..');
const FRONTEND=app.isPackaged?path.join(ROOT,'python/_internal/frontend'):path.join(ROOT,'frontend');
const ICON=app.isPackaged?path.join(ROOT,'python/_internal/subtitle_organizer.ico'):path.join(ROOT,'assets/subtitle_organizer.ico');
const argument=key=>process.argv.find(item=>item.startsWith(`--${key}=`))?.slice(key.length+3);
const defaultProfile=app.isPackaged?path.join(process.env.LOCALAPPDATA||app.getPath('appData'),'YingXu','Electron'):path.join(ROOT,'work/electron-profile');
const profile=path.resolve(argument('profile')||defaultProfile);
const diagnostics=process.argv.includes('--diagnostics');
const preview=process.argv.includes('--preview');
const fixture=diagnostics?argument('test-folder'):null;
const effectProfile=argument('effects')==='moderate'?'moderate':'full';
const defaults={theme:'system',glassEnabled:true,strength:'enhanced',particlesEnabled:true,
  reducedMotion:false,mistEnabled:true,lighting:'enhanced',nativeHdr:true};
fs.mkdirSync(profile,{recursive:true});
app.setPath('userData',profile);
app.setPath('sessionData',path.join(profile,'chromium'));
protocol.registerSchemesAsPrivileged([{scheme:'yingxu',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
let win,backend,readyResolve,quitting=false,closed=false;
const backendReady=new Promise(resolve=>{readyResolve=resolve;});
let preferences={...defaults};
try {preferences={...preferences,...validatePatch(JSON.parse(fs.readFileSync(path.join(profile,'appearance.json'),'utf8')))};} catch {}
if(effectProfile==='moderate'){preferences.mistEnabled=false;preferences.particlesEnabled=false;}
let displayOutput={host:'electron',nativeHdrActive:false,hdrConfigured:false,hdrValidation:'pending',osSettingsChanged:false};

function validatePatch(patch) {
  if(!patch||Array.isArray(patch)||typeof patch!=='object'||!Object.keys(patch).length||JSON.stringify(patch).length>2048)throw Error('INVALID_APPEARANCE');
  for(const [key,value] of Object.entries(patch)) {
    if(!Object.hasOwn(defaults,key))throw Error('INVALID_APPEARANCE');
    const valid=key==='theme'?['system','light','dark'].includes(value):key==='strength'?['standard','enhanced'].includes(value):key==='lighting'?['off','soft','enhanced'].includes(value):typeof value==='boolean';
    if(!valid)throw Error('INVALID_APPEARANCE');
  }
  return patch;
}
function appearanceState() {
  const systemTheme=nativeTheme.shouldUseDarkColors?'dark':'light';
  return {...preferences,systemTheme,resolvedTheme:preferences.theme==='system'?systemTheme:preferences.theme,displayOutput};
}
function send(channel,data){if(win&&!win.isDestroyed()&&!win.webContents.isDestroyed())win.webContents.send(channel,data);}
function appearanceChanged() {
  const state=appearanceState();send('yingxu:appearance',state);
  if(backend&&!closed&&backend.stdin.writable)write({type:'appearance',state});
  if(win&&!win.isDestroyed())win.setBackgroundColor(state.resolvedTheme==='dark'?'#0c1422':'#f3f6fb');
}
function write(frame) {
  if(!backend||!backend.stdin.writable||closed)throw Error('BACKEND_DISCONNECTED');
  backend.stdin.write(JSON.stringify(frame)+'\n');
}
function trusted(event) {
  if(!win||event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame||event.senderFrame.origin!=='yingxu://app')throw Error('UNTRUSTED_FRAME');
}
function expose(name,handler){ipcMain.handle(name,(event,...args)=>{trusted(event);return handler(...args);});}
expose('yingxu:request',async raw=>{
  if(typeof raw!=='string'||Buffer.byteLength(raw,'utf8')>8192)throw Error('INVALID_REQUEST');
  await backendReady;write({type:'request',raw});
});
expose('yingxu:drop',async folder=>{
  if(preview||typeof folder!=='string'||!folder||folder.length>32768)throw Error('DROP_UNAVAILABLE');
  await backendReady;write({type:'folder.drop',path:folder});return {accepted:true};
});
expose('yingxu:appearance:get',()=>appearanceState());
expose('yingxu:appearance:update',patch=>{
  try {
    const next={...preferences,...validatePatch(patch)};
    fs.writeFileSync(path.join(profile,'appearance.json'),JSON.stringify(next));preferences=next;appearanceChanged();
    return {ok:true,state:appearanceState()};
  } catch{return {ok:false,state:appearanceState()};}
});
expose('yingxu:hdr:report',report=>{
  if(!report||typeof report!=='object'||Object.keys(report).some(key=>!['configured','format','toneMapping','reason','adapter'].includes(key)))throw Error('INVALID_HDR_REPORT');
  displayOutput={...displayOutput,hdrConfigured:report.configured===true&&report.format==='rgba16float'&&report.toneMapping==='extended',
    canvasFormat:report.format,canvasToneMapping:report.toneMapping,hdrReason:String(report.reason||'').slice(0,200),adapter:String(report.adapter||'').slice(0,200)};
  appearanceChanged();return {ok:true};
});
async function native(frame) {
  const reply={type:'native.result',requestId:frame.requestId,sessionId:frame.sessionId,action:frame.action};
  try {
    if(frame.action==='folder.choose') {
      const result=fixture?{canceled:false,filePaths:[path.resolve(fixture)]}:await dialog.showOpenDialog(win,{title:'选择视频和字幕目录',properties:['openDirectory']});
      reply.cancelled=result.canceled;if(!result.canceled)reply.path=result.filePaths[0];
    } else if(frame.action==='result.export'&&!preview) {
      const result=await dialog.showSaveDialog(win,{title:'导出整理记录',defaultPath:'映序整理记录.json',
        filters:[{name:'JSON 记录',extensions:['json']}],properties:['showOverwriteConfirmation']});
      reply.cancelled=result.canceled;if(!result.canceled)reply.path=result.filePath;
    } else if(frame.action==='file.copyName')clipboard.writeText(path.basename(frame.path));
    else if(frame.action==='file.reveal') {
      if(fs.statSync(frame.path).isDirectory()){const error=await shell.openPath(frame.path);if(error)throw Error(error);}
      else shell.showItemInFolder(frame.path);
    } else throw Error('ACTION_UNAVAILABLE');
  } catch{reply.error='NATIVE_FAILED';}
  if(!closed)write(reply);
}

app.whenReady().then(async()=>{
  const frontend=fs.realpathSync(FRONTEND);
  const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.ttf':'font/ttf'};
  protocol.handle('yingxu',async request=>{
    try {
      const url=new URL(request.url),relative=decodeURIComponent(url.pathname).replace(/^\/+/,''),target=path.resolve(frontend,relative);
      if(request.method!=='GET'||url.hostname!=='app'||url.port||url.username||url.password||url.search||url.hash||!target.startsWith(frontend+path.sep))return new Response('',{status:403});
      // The preload supplies the host API; Qt's loader is not evaluated.
      if(relative==='qt/qwebchannel.js')return new Response('',{headers:{'Content-Type':'text/javascript'}});
      const real=await fs.promises.realpath(target),type=mime[path.extname(real)];
      if(!real.startsWith(frontend+path.sep)||!type)return new Response('',{status:403});
      return new Response(await fs.promises.readFile(real),{headers:{'Content-Type':type,'X-Content-Type-Options':'nosniff'}});
    } catch{return new Response('',{status:404});}
  });
  const python=app.isPackaged?path.join(ROOT,'python/YingXuBackend.exe'):(process.env.YINGXU_PYTHON||path.join(ROOT,'.venv-web/Scripts/python.exe'));
  const backendArguments=app.isPackaged?['--desktop-backend']:['-u','-m','yingxu.desktop_host.backend'];
  backend=spawn(python,[...backendArguments,'--profile',path.join(profile,'python'),...(preview?[]:['--full'])],{
    cwd:ROOT,windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...process.env,PYTHONUTF8:'1'}});
  if(diagnostics)process.stdout.write(JSON.stringify({type:'backend',pid:backend.pid})+'\n');
  backend.stderr.on('data',block=>process.stderr.write(block));
  backend.stdin.on('error',()=>{});
  createInterface({input:backend.stdout,crlfDelay:Infinity}).on('line',line=>{
    try {
      const frame=JSON.parse(line);
      if(frame.type==='ready'){readyResolve();appearanceChanged();}
      else if(frame.type==='reply'||frame.type==='event')send(`yingxu:${frame.type}`,frame.raw);
      else if(frame.type==='native')native(frame).catch(error=>process.stderr.write(String(error)+'\n'));
      else if(frame.type==='online.window'&&diagnostics)process.stdout.write(JSON.stringify(frame)+'\n');
      else if(frame.type==='display'){displayOutput={...displayOutput,...frame.status,systemHdrEnabled:frame.status.hdrEnabled===true};appearanceChanged();}
      else if(frame.type==='online.ui'&&[null,'history-button','appearance-button'].includes(frame.identifier)) {
        if(win&&!win.isDestroyed()){if(win.isMinimized())win.restore();win.show();win.focus();send('yingxu:native-ui',frame.identifier);}
      } else if(frame.type==='online.appearance'&&['system','dark','light'].includes(frame.theme)) {
        preferences={...preferences,theme:frame.theme};fs.writeFileSync(path.join(profile,'appearance.json'),JSON.stringify(preferences));appearanceChanged();
      }
    } catch(error){process.stderr.write('Backend protocol error: '+String(error)+'\n');}
  });
  backend.on('error',error=>{readyResolve();closed=true;send('yingxu:disconnected',String(error));});
  backend.on('exit',code=>{readyResolve();closed=true;if(!quitting)send('yingxu:disconnected',`Python 服务已退出 (${code})；请重新打开映序。`);});
  const state=appearanceState();
  win=new BrowserWindow({title:preview?'映序 · Electron 对比原型':'映序 · 字幕工作台',width:1280,height:860,useContentSize:true,minWidth:940,minHeight:700,show:false,
    backgroundColor:state.resolvedTheme==='dark'?'#0c1422':'#f3f6fb',icon:ICON,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true,
    additionalArguments:[`--yingxu-bootstrap=${encodeURIComponent(JSON.stringify({...state,prototype:preview,effectProfile}))}`]}});
  win.removeMenu();
  const session=win.webContents.session;
  session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  session.setPermissionCheckHandler(()=>false);
  session.webRequest.onBeforeRequest((details,callback)=>callback({cancel:!details.url.startsWith('yingxu://app/')&&!details.url.startsWith('devtools://')}));
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',(event,url)=>{if(url!=='yingxu://app/workspace.html')event.preventDefault();});
  win.webContents.on('did-start-navigation',(_event,_url,_inPlace,isMainFrame)=>{if(isMainFrame&&!closed)write({type:'reset'});});
  win.webContents.on('console-message',event=>{if(event.level==='error')process.stderr.write('JS: '+event.message+'\n');});
  win.webContents.on('render-process-gone',(_event,details)=>process.stderr.write('Renderer stopped: '+details.reason+'\n'));
  await Promise.race([backendReady,new Promise((_,reject)=>setTimeout(()=>reject(Error('Python startup timeout')),10000))]);
  if(closed)throw Error('Python 服务未能启动');
  let displayTimer;
  const queryDisplay=()=>{if(!closed&&!win.isDestroyed())write({type:'display.query',handle:win.getNativeWindowHandle().readBigUInt64LE().toString()});};
  const scheduleDisplay=()=>{clearTimeout(displayTimer);displayTimer=setTimeout(queryDisplay,120);};
  queryDisplay();nativeTheme.on('updated',appearanceChanged);win.on('move',scheduleDisplay);
  screen.on('display-metrics-changed',scheduleDisplay);win.on('closed',()=>clearTimeout(displayTimer));
  win.once('ready-to-show',()=>{win.show();if(diagnostics)win.setAlwaysOnTop(true);win.focus();if(diagnostics)process.stdout.write(JSON.stringify({type:'window',pid:process.pid,handle:win.getNativeWindowHandle().readBigUInt64LE().toString(),effects:effectProfile,visible:win.isVisible()})+'\n');});
  await win.loadURL('yingxu://app/workspace.html');
}).catch(error=>{process.stderr.write(String(error.stack||error)+'\n');app.quit();});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',event=>{
  if(quitting||!backend||closed)return;
  event.preventDefault();quitting=true;write({type:'shutdown'});
  // A slow media operation must finish cooperatively; never kill its Python worker.
  backend.once('exit',()=>app.quit());
});
