// Diagnostic DOM driver without browser-context or focus/visibility emulation.
import fs from 'node:fs';
export function domDriver(client) {
  const evaluate=async(fn,arg)=>{
    const reply=await client.send('Runtime.evaluate',{expression:`(${fn.toString()})(${arg===undefined?'':JSON.stringify(arg)})`,returnByValue:true,awaitPromise:true});
    if(reply.exceptionDetails)throw Error(reply.exceptionDetails.exception?.description||reply.exceptionDetails.text);
    return reply.result?.value;
  };
  const driver={evaluate,waitForFunction:async(fn,_arg,{timeout=30000}={})=>{
    const deadline=performance.now()+timeout;
    while(performance.now()<deadline){try{if(await evaluate(fn))return;}catch(error){if(!/context|Cannot read properties/i.test(error.message))throw error;}await new Promise(resolve=>setTimeout(resolve,60));}
    throw Error('Application state timed out');
  },reload:async()=>{
    await client.send('Page.enable');
    let timeout;
    const loaded=new Promise((resolve,reject)=>{timeout=setTimeout(()=>reject(Error('Reload timed out')),30000);client.once('Page.loadEventFired',()=>{clearTimeout(timeout);resolve();});});
    await client.send('Page.reload');await loaded;
  },close:()=>client.send('Page.close'),
  screenshot:async({path})=>{const image=await client.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path,Buffer.from(image.data,'base64'));},
  mouse:{move:(x,y)=>client.send('Input.dispatchMouseEvent',{type:'mouseMoved',x,y})}};
  driver.locator=selector=>{
    // Keep the evaluator CSP-compatible: no Function/eval in the page.
    const read=async(key,arg)=>evaluate(({selector,key,arg})=>{const e=document.querySelector(selector);if(!e)throw Error(`Missing control: ${selector}`);
      if(key==='box'){const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,disabled:e.disabled};}
      if(key==='disabled')return e.disabled;
      if(key==='attribute')return e.getAttribute(arg);
      if(key==='fill'){e.focus();e.value=arg;e.dispatchEvent(new Event('input',{bubbles:true}));}
      if(key==='select'){e.value=arg;e.dispatchEvent(new Event('change',{bubbles:true}));}
    },{selector,key,arg});
    const locator={first:()=>locator,isDisabled:()=>read('disabled'),getAttribute:attribute=>read('attribute',attribute),
      fill:text=>read('fill',text),selectOption:value=>read('select',value),boundingBox:()=>read('box'),
      count:()=>evaluate(selector=>document.querySelectorAll(selector).length,selector),
      click:async()=>{await evaluate(selector=>document.querySelector(selector)?.scrollIntoView({block:'nearest',inline:'nearest'}),selector);
        const r=await read('box');if(r.disabled)throw Error(`Disabled control: ${selector}`);const point={x:r.x+r.width/2,y:r.y+r.height/2};
        await client.send('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
        await client.send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',buttons:1,clickCount:1,...point});
        await client.send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',buttons:0,clickCount:1,...point});
      }};
    return locator;
  };
  return driver;
}
