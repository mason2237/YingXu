// Replaceable browser adapter. The remote view has no preload or local IPC API.
const {BrowserWindow,WebContentsView,ipcMain}=require('electron');
const {randomUUID}=require('node:crypto');
const path=require('node:path');
const fs=require('node:fs');

const ACTIONS=new Set(['online.query','online.configure','online.start','online.cancel','online.candidates','online.select','online.openCandidate',
  'online.resumeQueue','online.usePage','online.download','online.downloads','online.retryDownload','online.discardDownload','online.compactDownload','online.import','online.cache']);
function safeHttps(value,hosts=null) {
  try {
    const url=new URL(value),host=url.hostname.toLowerCase();
    return url.protocol==='https:'&&!url.username&&!url.password&&(!url.port||url.port==='443')&&
      !/[\\\r\n\t]/.test(value)&&host.includes('.')&&!/^[0-9.]+$/.test(host)&&
      !host.endsWith('.')&&!/\.(local|localhost|internal)$/.test(host)&&(!hosts||hosts.includes(host));
  } catch{return false;}
}

class OnlineWindow {
  constructor({request,write,appearance,icon,incoming,diagnostics=false}) {
    Object.assign(this,{request,write,appearance,icon,incoming,diagnostics});
    this.window=null;this.view=null;this.ticket=null;this.timer=null;this.epoch=0;
    this.grant=null;this.offers=new Map();this.received=0;this.downloadCount=0;
    ipcMain.handle('yingxu:online:request',(event,action,params={})=>{
      if(!this.window||event.sender!==this.window.webContents||event.senderFrame!==this.window.webContents.mainFrame||
         event.senderFrame.origin!=='yingxu://app'||!ACTIONS.has(action))throw Error('UNTRUSTED_ONLINE_FRAME');
      if(Buffer.byteLength(JSON.stringify(params),'utf8')>4096)throw Error('INVALID_ONLINE_REQUEST');
      return this.request(action,params);
    });
    ipcMain.handle('yingxu:online:appearance',event=>{
      if(!this.window||event.sender!==this.window.webContents||event.senderFrame!==this.window.webContents.mainFrame)throw Error('UNTRUSTED_ONLINE_FRAME');
      return this.appearance();
    });
  }
  async show() {
    if(this.window&&!this.window.isDestroyed()){this.window.show();this.window.focus();this.changed();return;}
    this.window=new BrowserWindow({title:'映序 · 查找字幕',width:1240,height:840,minWidth:1060,minHeight:700,
      icon:this.icon,backgroundColor:'#101927',show:false,webPreferences:{preload:path.join(__dirname,'online-preload.cjs'),
      contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true}});
    this.window.removeMenu();
    this.window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    this.window.webContents.on('will-navigate',(event,url)=>{if(url!=='yingxu://app/online.html')event.preventDefault();});
    this.view=new WebContentsView({webPreferences:{partition:'yingxu-site-'+randomUUID(),
      contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true,webviewTag:false}});
    const contents=this.view.webContents,session=contents.session;
    session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
    session.setPermissionCheckHandler(()=>false);
    session.webRequest.onBeforeRequest((details,callback)=>{
      const upload=details.uploadData?.some(item=>item.file||item.blobUUID);
      callback({cancel:Boolean(upload)||(!safeHttps(details.url)&&!details.url.startsWith('data:'))});
    });
    session.on('will-download',(event,item,source)=>this.download(event,item,source));
    const navigation=(event,url)=>{if(!safeHttps(url,this.ticket?.plan.hosts||this.hosts))event.preventDefault();};
    contents.on('will-navigate',navigation);contents.on('will-redirect',navigation);
    contents.setWindowOpenHandler(({url})=>{if(safeHttps(url,this.ticket?.plan.hosts||this.hosts))contents.loadURL(url).catch(()=>{});return {action:'deny'};});
    contents.on('did-finish-load',()=>this.documentReady().then(()=>this.downloadReady()).catch(()=>this.fail('网站页面未能解析，请切换来源或手动浏览。')));
    contents.on('did-fail-load',(_event,code,_text,_url,isMainFrame)=>{if(isMainFrame&&code!==-3)this.fail('网站加载失败，请重试或切换备用来源。');});
    contents.on('render-process-gone',()=>this.fail('网站页面已退出，请重新查找。'));
    this.window.contentView.addChildView(this.view);
    this.view.setVisible(false);
    // Initialize an isolated blank document without contacting a website.
    await contents.loadURL('about:blank');
    const layout=()=>{if(this.window&&!this.window.isDestroyed()){const [width,height]=this.window.getContentSize();this.view.setBounds({x:352,y:184,width:Math.max(1,width-364),height:Math.max(1,height-198)});}};
    this.window.on('resize',layout);layout();
    this.window.once('ready-to-show',()=>{this.window.show();this.window.focus();});
    this.window.on('closed',()=>{if(this.ticket)this.finish(this.ticket,{status:'manual',message:'网站窗口已关闭；可重新打开后继续搜索。'});this.stop();this.disarm();try{this.write({type:'browser.closed'});}catch{}if(!contents.isDestroyed())contents.close();this.window=null;this.view=null;});
    await this.window.loadURL('yingxu://app/online.html');
    if(this.diagnostics)process.stdout.write(JSON.stringify({type:'online.window',pid:process.pid})+'\n');
  }
  changed(){if(this.window&&!this.window.isDestroyed())this.window.webContents.send('yingxu:online:changed');}
  appearanceChanged(){if(this.window&&!this.window.isDestroyed())this.window.webContents.send('yingxu:online:appearance',this.appearance());}
  notice(message){if(this.window&&!this.window.isDestroyed())this.window.webContents.send('yingxu:online:notice',message);}
  stop(){this.epoch++;clearTimeout(this.timer);this.ticket=null;if(this.view&&!this.view.webContents.isDestroyed())this.view.webContents.stop();}
  async search(frame) {
    const epoch=this.epoch;await this.show();if(epoch!==this.epoch)return;this.stop();
    if(!frame.plan||!Array.isArray(frame.plan.hosts)||!safeHttps(frame.plan.home,frame.plan.hosts))throw Error('INVALID_PROVIDER_PLAN');
    const ticket=this.ticket={...frame,submitted:false};this.hosts=frame.plan.hosts;
    this.view.setVisible(true);
    this.timer=setTimeout(()=>{if(this.ticket===ticket)this.finish(ticket,{status:'manual',message:'请在右侧完成网站验证或核对页面，再点击继续查找。'});},20000);
    if(frame.resume&&safeHttps(this.view.webContents.getURL(),frame.plan.hosts))await this.documentReady();
    else await this.view.webContents.loadURL(frame.plan.home);
  }
  finish(ticket,value) {
    if(this.ticket!==ticket)return;
    this.write({type:'browser.result',taskId:ticket.taskId,effectId:ticket.effectId,generation:ticket.generation,...value});
    if(value.final||['manual','failed'].includes(value.status)){clearTimeout(this.timer);this.ticket=null;this.changed();}
  }
  fail(message){if(this.ticket)this.finish(this.ticket,{status:'failed',message});else this.notice(message);}
  async documentReady() {
    const ticket=this.ticket,contents=this.view?.webContents;
    if(!ticket||!contents||!safeHttps(contents.getURL(),ticket.plan.hosts))return;
    if(await contents.executeJavaScript(ticket.plan.challengeScript)){
      this.finish(ticket,{status:'manual',message:'网站需要验证，请在右侧完成后点击继续查找。'});return;
    }
    if(this.ticket!==ticket)return;
    const raw=await contents.executeJavaScript(ticket.plan.candidateScript);
    if(this.ticket!==ticket)return;
    let result;try{result=typeof raw==='string'?JSON.parse(raw):raw;}catch{result={status:'unrecognized',rows:[]};}
    if(result?.status==='ready'||result?.status==='empty') {
      const rows=Array.isArray(result.rows)?result.rows.slice(0,20):[];
      for(let index=0;index<Math.max(1,rows.length);index++){
        const row=rows[index],trimmed=row?{url:String(row.url||'').slice(0,2048),title:String(row.title||'').slice(0,200),
          release:String(row.release||'').slice(0,500),metadata:String(row.metadata||'').slice(0,200)}:null;
        this.finish(ticket,{status:'results',raw:JSON.stringify({status:result.status,rows:trimmed?[trimmed]:[]}),final:index===rows.length-1||!rows.length});
      }
      return;
    }
    if(!ticket.submitted) {
      ticket.submitted=true;
      const response=await contents.executeJavaScript(ticket.plan.submitScript);
      if(this.ticket===ticket&&response?.status!=='submitted')this.finish(ticket,{status:'manual',message:'未找到可自动填写的搜索框，请在网站输入片名。'});
    } else this.finish(ticket,{status:'manual',message:'当前页面暂不支持候选解析，可切换备用来源；网站验证须由你完成。'});
  }
  async open(frame) {
    const epoch=this.epoch;await this.show();if(epoch!==this.epoch)return;this.stop();
    // This URL is resolved in Python from the task's validated candidate vault.
    if(!safeHttps(frame.url,frame.hosts))throw Error('UNTRUSTED_PROVIDER_URL');
    this.hosts=frame.hosts;
    this.view.setVisible(true);
    await this.view.webContents.loadURL(frame.url);
  }
  close(){this.stop();if(this.window&&!this.window.isDestroyed())this.window.close();}

  async arm(frame) {
    const epoch=this.epoch;await this.show();if(epoch!==this.epoch)return;this.stop();
    if(!safeHttps(frame.url,frame.hosts))throw Error('UNTRUSTED_PROVIDER_URL');
    this.hosts=frame.hosts;
    this.grant={taskId:frame.taskId,effectId:frame.effectId,generation:frame.generation};
    this.downloadPlan={script:frame.downloadScript,clicked:new Set()};
    this.view.setVisible(true);
    this.notice('已确认这份候选，正在尝试网站下载；必要验证或未识别的步骤请在右侧完成。下载后自动验证和解压。');
    try{await this.view.webContents.loadURL(frame.url);}catch{this.downloadFailed(frame,'候选下载页面未能打开；请重新查找或切换来源。');}
  }
  disarm() {
    this.epoch++;
    this.grant=null;
    this.downloadPlan=null;
    for(const value of this.offers.values()){clearTimeout(value.timer);value.item.cancel();}
    this.offers.clear();
  }
  download(event,item,source) {
    const grant=this.grant,page=this.view?.webContents.getURL(),url=item.getURL();
    const blob=url.startsWith('blob:');
    let sameBlob=false;
    try{sameBlob=blob&&new URL(url.slice(5)).origin===new URL(page).origin;}catch{}
    if(!grant||source!==this.view?.webContents||!safeHttps(page,this.hosts)||
       (!safeHttps(url)&&!sameBlob)||item.getTotalBytes()>64*1024*1024||
       this.downloadCount>=20||this.received>=256*1024*1024){
      event.preventDefault();this.notice('请先选择候选并确认下载；仅接收当前网站的有界字幕文件。');return;
    }
    this.grant=null;this.downloadCount++;
    const offerId=randomUUID().replaceAll('-','');
    const frame={type:'download.offer',...grant,offerId,url,page,name:item.getFilename(),mime:item.getMimeType(),total:Math.max(0,item.getTotalBytes())};
    if([url,page,frame.name,frame.mime].some(value=>value.length>2048)){
      event.preventDefault();this.downloadFailed(grant,'下载链接或文件名过长，已拒绝。');return;
    }
    if(!blob) {
      event.preventDefault();
      // Cookies stay in memory and only accompany this HTTPS origin request.
      this.view.webContents.session.cookies.get({url}).then(cookies=>{
        const cookie=cookies.map(value=>`${value.name}=${value.value}`).join('; ');
        if(cookie.length>2048)throw Error('网站凭据过长，请重新获取下载链接。');
        this.write({...frame,headers:{Cookie:cookie,Referer:page,'User-Agent':this.view.webContents.getUserAgent()}});
      }).catch(()=>this.downloadFailed(grant,'无法获取网站下载凭据，请回网站重新获取链接。'));
      return;
    }
    fs.mkdirSync(this.incoming,{recursive:true});
    const destination=path.join(this.incoming,offerId+'.part');
    const handle=fs.openSync(destination,'wx');fs.closeSync(handle);
    item.setSavePath(destination);item.pause();
    const value={item,artifactId:null,received:0,timer:setTimeout(()=>{item.cancel();this.offers.delete(offerId);this.downloadFailed(grant,'接收下载超时；未导入，请重新获取。');},15000)};
    this.offers.set(offerId,value);
    item.on('updated',()=>{
      const bytes=item.getReceivedBytes();this.received+=Math.max(0,bytes-value.received);value.received=bytes;
      if(bytes>64*1024*1024||this.received>256*1024*1024)item.cancel();
    });
    item.once('done',(_event,status)=>{
      clearTimeout(value.timer);this.offers.delete(offerId);
      if(value.artifactId)this.write({type:'download.result',artifactId:value.artifactId,status:status==='completed'?'completed':'interrupted'});
      this.changed();
    });
    this.write(frame);
  }
  capture(frame) {
    const contents=this.view?.webContents;if(!contents||contents.isDestroyed())return;
    this.write({type:'browser.page',taskId:frame.taskId,effectId:frame.effectId,generation:frame.generation,url:contents.getURL().slice(0,2048),title:contents.getTitle().slice(0,200)});
  }
  async downloadReady(){
    const plan=this.downloadPlan,contents=this.view?.webContents,url=contents?.getURL();
    if(!this.grant||!plan?.script||!safeHttps(url,this.hosts)||plan.clicked.has(url)||plan.clicked.size>=2)return;
    plan.clicked.add(url);
    const result=await contents.executeJavaScript(plan.script);
    if(plan!==this.downloadPlan)return;
    if(result?.status==='manual')this.notice(result.message||'请在网站完成必要验证或下载选择；程序不会代替验证。');
  }
  accept(frame) {
    const value=this.offers.get(frame.offerId);
    if(!value)return;
    clearTimeout(value.timer);value.artifactId=frame.artifactId;value.item.resume();
  }
  reject(frame) {
    const value=this.offers.get(frame.offerId);
    if(value){clearTimeout(value.timer);value.item.cancel();this.offers.delete(frame.offerId);}
    this.notice(frame.message);
  }
  downloadFailed(grant,message){
    if(this.grant?.effectId===grant.effectId&&this.grant?.generation===grant.generation)this.grant=null;
    this.notice(message);
    try{this.write({type:'download.failed',taskId:grant.taskId,effectId:grant.effectId,generation:grant.generation,message});}catch{}
  }
}
module.exports={OnlineWindow,safeHttps,ACTIONS};
