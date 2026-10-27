// Variable-size detail pages and isolated selection failures; no desktop/network.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
const Custom=globalThis.CustomEvent||class extends Event{constructor(type,{detail}={}){super(type);this.detail=detail;}};
function load(file,name,extra={}){
  const source=fs.readFileSync(path.join(root,file),'utf8').replace(/^import[^\n]*\n/gm,'').replace('export class','class');
  return vm.runInNewContext(source+`\n${name}`,{EventTarget,Event,CustomEvent:Custom,setTimeout,clearTimeout,window:new EventTarget(),...extra});
}
const tracks=Array.from({length:64},(_,i)=>({trackId:`track-${i+1}`,title:`完整标题 ${i+1} `+'中🙂'.repeat(80)}));
const sections={tracks,subtitles:[{name:'完整字幕名.srt',targetPath:'example/完整目标名.srt'}],warnings:[],basis:['语言符合','不导出']};
let broken=false,calls=0;
class Bridge extends EventTarget{
  constructor(){super();this.version=2;}
  async connect(){return {summary:{},busy:false};}
  async call(action,params){
    if(action==='review.details')return {rowId:params.rowId,embedded:{tracks:[]},detailCounts:Object.fromEntries(Object.entries(sections).map(([key,values])=>[key,values.length]))};
    assert.equal(action,'review.detailPage');calls++;
    const source=sections[params.section],entries=source.slice(params.offset,params.offset+3),next=params.offset+entries.length;
    return {rowId:params.rowId,section:params.section,offset:params.offset,total:source.length,entries,
      nextOffset:broken?0:next<source.length?next:null};
  }
}
const LocalAdapter=load('frontend/js/local-adapter.js','LocalAdapter',{BridgeClient:Bridge});
const WorkspaceStore=load('frontend/js/store.js','WorkspaceStore');
(async()=>{
  const adapter=new LocalAdapter(),params={scanId:'scan',revision:1,rowId:'video-1'};
  const details=await adapter.request('review.details',params);
  assert.deepEqual([...details.embedded.tracks],tracks);
  assert.equal(details.subtitles[0].targetPath,sections.subtitles[0].targetPath);
  assert.equal(calls,24,'Three-item replies must assemble all 64 tracks and both other collections');
  broken=true;await assert.rejects(adapter.request('review.details',params),/分页/);broken=false;

  const mock=new EventTarget(),summary={scanId:'scan',revision:1,counts:{all:2}},view={total:2,ids:['video-1','video-2']};
  let fail=true,rejectOld;
  Object.assign(mock,{state:{summary,busy:false},load:async()=>summary,request:async(action,p)=>{
    if(action==='app.state')return summary;if(action==='review.query')return view;
    if(p.rowId==='video-1'&&fail)throw Error('injected detail failure');
    return {rowId:p.rowId};
  }});
  const store=new WorkspaceStore(mock);await store.load('scan');
  assert.equal(store.error,'');assert.equal(store.view.total,2);assert.equal(store.selectedId,'video-1');
  assert.match(store.detailsError,/injected/);assert.equal(store.details,null);
  await store.select('video-2');assert.equal(store.details.rowId,'video-2');assert.equal(store.detailsError,'');
  await store.select('video-1');assert.equal(store.view.total,2);assert.equal(store.selectedId,'video-1');assert.equal(store.details,null);
  fail=false;await store.select('video-1');assert.equal(store.details.rowId,'video-1');assert.equal(store.detailsError,'');
  mock.request=async(_action,p)=>p.rowId==='video-1'?new Promise((_resolve,reject)=>{rejectOld=reject;}):{rowId:p.rowId};
  const old=store.select('video-1');await store.select('video-2');rejectOld(Error('late failure'));await old;
  assert.equal(store.selectedId,'video-2');assert.equal(store.details.rowId,'video-2');assert.equal(store.detailsError,'');
  console.log(JSON.stringify({passed:true,tracksPreserved:64,variablePageSizes:true,invalidPageRejected:true,
    detailFailureKeepsList:true,selectOtherVideo:true,retry:true,lateFailureIgnored:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
