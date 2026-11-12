// Replaceable browser adapter. The remote view has no preload or local IPC API.
const {BrowserWindow,WebContentsView,ipcMain}=require('electron');
const {randomUUID}=require('node:crypto');
const path=require('node:path');
const fs=require('node:fs');
const MAX_DOWNLOAD_BYTES=64*1024*1024;
const MAX_SESSION_BYTES=256*1024*1024;
const WAIT_FOR_DOWNLOAD_MS=90000;
const DOWNLOAD_IDLE_MS=30000;

const ACTIONS=new Set(['online.query','online.configure','online.start','online.cancel','online.candidates','online.select','online.openCandidate',
  'online.resumeQueue','online.usePage','online.download','online.downloads','online.retryDownload','online.discardDownload','online.compactDownload','online.import','online.cache',
  'online.qualityFiles','online.quality','online.qualityResult','online.qualityPage','online.provider']);
function safeHttps(value,hosts=null) {
  try {
    const url=new URL(value),host=url.hostname.toLowerCase();
    return url.protocol==='https:'&&!url.username&&!url.password&&(!url.port||url.port==='443')&&
      !/[\\\r\n\t]/.test(value)&&host.includes('.')&&!/^[0-9.]+$/.test(host)&&
      !host.endsWith('.')&&!/\.(local|localhost|internal)$/.test(host)&&(!hosts||hosts.includes(host));
  } catch{return false;}
}
function zimukuDownloadRedirect(url,page,hosts,grant) {
  if(!grant||!safeHttps(page,hosts)||!safeHttps(url,['s.zimuku.org']))return false;
  const origin=new URL(page);
  return ['zimuku.org','www.zimuku.org','srtku.com','www.srtku.com'].includes(origin.hostname)
    && /^\/(detail|dld)\/\d+\.html$/.test(origin.pathname)
    && new URL(url).pathname.startsWith('/download/');
}

class OnlineWindow {
  constructor({request,write,appearance,icon,incoming,diagnostics=false}) {
    Object.assign(this,{request,write,appearance,icon,incoming,diagnostics});
    this.window=null;this.view=null;this.ticket=null;this.timer=null;this.epoch=0;
    this.grant=null;this.grantTimer=null;this.offers=new Map();this.received=0;this.downloadCount=0;
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
    session.webRequest.onHeadersReceived((details,callback)=>{
      if(details.resourceType==='mainFrame'&&safeHttps(details.url,['s.zimuku.org'])&&
         !Object.entries(details.responseHeaders||{}).some(([name,values])=>
           name.toLowerCase()==='content-disposition'&&values.some(value=>/^attachment\b/i.test(value)))){
        callback({cancel:true});return;
      }
      if(details.resourceType==='mainFrame'&&this.ticket){
        this.ticket.httpError=null;
        if(details.statusCode>=400){
          const retry=Object.entries(details.responseHeaders||{}).find(([name])=>name.toLowerCase()==='retry-after')?.[1]?.[0];
          this.ticket.httpError={status:'failed',statusCode:details.statusCode,
            ...(retry?{retryAfter:String(retry).slice(0,100)}:{}),
            message:`字幕来源返回 HTTP ${details.statusCode}，请重试或切换来源。`};
        }
      }
      callback({cancel:false});
    });
    const navigation=(event,url)=>{if(!safeHttps(event.url||url,this.ticket?.plan.hosts||this.hosts))event.preventDefault();};
    contents.on('will-navigate',navigation);
    contents.on('will-redirect',(event,url)=>{
      if(!zimukuDownloadRedirect(event.url||url,contents.getURL(),this.hosts,this.grant))navigation(event,url);
    });
    contents.setWindowOpenHandler(({url,referrer})=>{
      if(safeHttps(url,this.ticket?.plan.hosts||this.hosts))contents.loadURL(url,{httpReferrer:referrer}).catch(()=>{});
      return {action:'deny'};
    });
    contents.on('did-finish-load',()=>this.documentReady().then(()=>this.downloadReady()).catch(()=>this.fail('网站页面未能解析，请切换来源或手动浏览。')));
    contents.on('did-fail-load',(_event,code,_text,_url,isMainFrame)=>{if(isMainFrame&&code!==-3){if(this.ticket)this.finish(this.ticket,{status:'failed',errorClass:[-7,-21,-101,-102,-103,-105,-106,-118].includes(code)?'transient':'permanent',message:'网站连接未完成，临时故障会有限重试；必要验证需手动处理。'});else this.fail('网站加载失败，请重试或切换备用来源。');}});
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
  fail(message){
    if(this.ticket)this.finish(this.ticket,{status:'failed',message});
    else if(this.grant)this.downloadFailed(this.grant,message);
    else this.notice(message);
  }
  async documentReady() {
    const ticket=this.ticket,contents=this.view?.webContents;
    if(!ticket||!contents||!safeHttps(contents.getURL(),ticket.plan.hosts))return;
    const challenge=await contents.executeJavaScript(ticket.plan.challengeScript);
    if(this.ticket!==ticket)return;
    if(challenge){
      this.finish(ticket,{status:'manual',message:'网站需要验证，请在右侧完成后点击继续查找。'});return;
    }
    if(ticket.httpError){this.finish(ticket,ticket.httpError);return;}
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
    if(!safeHttps(frame.url,frame.hosts)){
      this.downloadFailed(frame,'下载页不属于当前字幕来源，请重新查找。');return;
    }
    this.hosts=frame.hosts;
    const grant=this.grant={taskId:frame.taskId,effectId:frame.effectId,generation:frame.generation};
    this.grantTimer=setTimeout(()=>{
      if(this.grant===grant)this.downloadFailed(grant,'网站没有开始下载。请重试、在右侧完成网站操作，或换个来源。');
    },WAIT_FOR_DOWNLOAD_MS);
    this.downloadPlan={script:frame.downloadScript,clicked:new Set()};
    this.view.setVisible(true);
    this.notice('正在打开下载页。如果网站要求验证或选择线路，请在右侧操作。');
    const contents=this.view.webContents;
    if(contents.getURL()===frame.url){
      await this.downloadReady();return;
    }
    try{await contents.loadURL(frame.url,{httpReferrer:contents.getURL()});}
    catch(error){
      if(this.grant===grant&&error.code!=='ERR_ABORTED')this.downloadFailed(grant,'下载页面未能打开，请重试或切换来源。');
    }
  }
  disarm() {
    this.epoch++;
    clearTimeout(this.grantTimer);
    this.grant=null;
    this.downloadPlan=null;
    for(const value of this.offers.values())value.cancel();
  }
  download(event,item,source) {
    const grant=this.grant,page=this.view?.webContents.getURL(),url=item.getURL();
    const blob=url.startsWith('blob:');
    let sameBlob=false;
    try{sameBlob=blob&&new URL(url.slice(5)).origin===new URL(page).origin;}catch{}
    if(!grant||source!==this.view?.webContents||!safeHttps(page,this.hosts)){
      event.preventDefault();this.notice('请先在映序选择要下载的字幕。');return;
    }
    if((!safeHttps(url)&&!sameBlob)||item.getTotalBytes()>MAX_DOWNLOAD_BYTES||
       this.downloadCount>=20||this.received>=MAX_SESSION_BYTES){
      event.preventDefault();this.downloadFailed(grant,'下载来源、文件大小或本次会话下载量超出限制。');return;
    }
    clearTimeout(this.grantTimer);
    this.grant=null;this.downloadCount++;
    const offerId=randomUUID().replaceAll('-','');
    const frame={type:'download.offer',...grant,offerId,url,page,name:item.getFilename(),mime:item.getMimeType(),
      total:Math.max(0,item.getTotalBytes()),browserTransfer:true};
    if([url,page,frame.name,frame.mime].some(value=>value.length>2048)){
      event.preventDefault();this.downloadFailed(grant,'下载链接或文件名过长，已拒绝。');return;
    }
    // Keep the response Chromium already opened, including single-use links.
    const destination=path.join(this.incoming,offerId+'.part');
    try{
      fs.mkdirSync(this.incoming,{recursive:true});
      fs.closeSync(fs.openSync(destination,'wx'));
      item.setSavePath(destination);
    }catch{
      event.preventDefault();this.downloadFailed(grant,'无法创建字幕暂存文件，请检查缓存目录。');return;
    }
    const value={artifactId:null,received:0,timer:null,finished:false};
    const cleanup=()=>fs.rm(destination,{force:true},()=>{});
    value.cancel=()=>{
      if(!this.offers.delete(offerId))return;
      clearTimeout(value.timer);
      if(value.finished)cleanup();else item.cancel();
    };
    const stop=message=>{
      if(!this.offers.has(offerId))return;
      value.cancel();this.downloadFailed(grant,message);
    };
    value.resetTimer=()=>{
      clearTimeout(value.timer);
      value.timer=setTimeout(()=>stop('接收字幕超时，请重新下载。'),DOWNLOAD_IDLE_MS);
    };
    this.offers.set(offerId,value);
    value.resetTimer();
    value.publish=()=>{
      if(!value.finished||!value.artifactId||!this.offers.has(offerId))return;
      try{
        this.write({type:'download.result',artifactId:value.artifactId,status:'completed'});
        this.offers.delete(offerId);clearTimeout(value.timer);
      }catch{stop('无法交接字幕文件，请重新下载。');}
    };
    item.on('updated',(_event,state)=>{
      if(!this.offers.has(offerId))return;
      const bytes=item.getReceivedBytes(),delta=Math.max(0,bytes-value.received);
      this.received+=delta;value.received=bytes;
      if(bytes>MAX_DOWNLOAD_BYTES||this.received>MAX_SESSION_BYTES)stop('字幕文件超过下载限制。');
      else if(state==='interrupted')stop('下载连接已中断，请重新下载。');
      else if(delta)value.resetTimer();
    });
    item.once('done',(_event,status)=>{
      value.finished=true;
      if(!this.offers.has(offerId)){cleanup();return;}
      const bytes=item.getReceivedBytes();
      this.received+=Math.max(0,bytes-value.received);
      if(status!=='completed')stop('字幕文件未能完整接收，请重新下载。');
      else if(bytes>MAX_DOWNLOAD_BYTES||this.received>MAX_SESSION_BYTES)stop('字幕文件超过下载限制。');
      else value.publish();
    });
    try{this.write(frame);}catch{stop('无法登记这次下载，请重试。');}
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
    value.artifactId=frame.artifactId;value.resetTimer();value.publish();
    this.notice('正在下载字幕，完成后会自动检查和解压。');
  }
  reject(frame) {
    const value=this.offers.get(frame.offerId);
    if(value)value.cancel();
    this.notice(frame.message);
  }
  downloadFailed(grant,message){
    if(this.grant?.effectId===grant.effectId&&this.grant?.generation===grant.generation){
      clearTimeout(this.grantTimer);this.grant=null;this.downloadPlan=null;
    }
    this.notice(message);
    try{this.write({type:'download.failed',taskId:grant.taskId,effectId:grant.effectId,generation:grant.generation,message});}catch{}
  }
}
module.exports={OnlineWindow,safeHttps,zimukuDownloadRedirect,ACTIONS};
