// Minimal CDP client: Qt doesn't implement Playwright's browser-context APIs.
import {EventEmitter} from 'node:events';
export class CdpClient extends EventEmitter {
  constructor(socket){super();this.socket=socket;this.serial=0;this.pending=new Map();
    socket.addEventListener('message',event=>{
      const value=JSON.parse(event.data);
      if(value.id){const waiter=this.pending.get(value.id);if(!waiter)return;this.pending.delete(value.id);clearTimeout(waiter.timer);value.error?waiter.reject(Error(value.error.message)):waiter.resolve(value.result);}
      else if(value.method)this.emit(value.method,value.params);
    });
    socket.addEventListener('close',()=>{for(const waiter of this.pending.values()){clearTimeout(waiter.timer);waiter.reject(Error('CDP connection closed'));}this.pending.clear();});
  }
  static async open(url){const socket=new WebSocket(url);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});return new CdpClient(socket);}
  send(method,params={}){const id=++this.serial;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error(`CDP timeout: ${method}`));},30000);this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method,params}));});}
  close(){this.socket.close();}
}
