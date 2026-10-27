// A minimized native window must stop effects even when DevTools keeps the page visible.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const document=new EventTarget();document.hidden=false;document.documentElement={dataset:{}};
const window=new EventTarget();let native,removed=false;
const source=fs.readFileSync(path.resolve(__dirname,'../../frontend/js/visibility.js'),'utf8').replaceAll('export ','');
const context={document,window,Event,yingxuHost:{lifecycle:{onVisibility:callback=>{native=callback;return()=>{removed=true;};}}}};
vm.createContext(context);vm.runInContext(source+'\nglobalThis.check=windowInactive;globalThis.listen=onWindowVisibility;',context);
let notifications=0;context.listen(()=>notifications++);
assert.equal(context.check(),false);native(true);assert.equal(document.hidden,false);assert.equal(context.check(),true);
native(false);assert.equal(context.check(),false);assert.equal(notifications,2);
document.hidden=true;assert.equal(context.check(),true);window.dispatchEvent(new Event('pagehide'));assert.equal(removed,true);
console.log(JSON.stringify({passed:true,nativeMinimizeOverridesDebugVisibility:true,listenerReleased:true}));
