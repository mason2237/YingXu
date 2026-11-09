// Isolated report rendering/paging contracts; desktop evidence is separate.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
class Node{
  constructor(tag,text=''){this.tag=tag;this.text=String(text);this.children=[];this.isConnected=true;this.attributes={};this.classList={add(){}};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;this.text='';}
  setAttribute(key,value){this.attributes[key]=value;}
  get textContent(){return this.text+this.children.map(c=>typeof c==='string'?c:c.textContent).join('');}
  set innerHTML(_value){throw Error('Untrusted subtitle text must not use innerHTML');}
}
const el=(tag,_className='',text='')=>new Node(tag,text),button=(text,_className,click)=>Object.assign(new Node('button',text),{click});
const code=fs.readFileSync(path.join(root,'frontend/js/components/subtitle-quality.js'),'utf8').replace(/^import[^\n]*\n/gm,'').replace(/export (class|function)/g,'$1');
const {SubtitleQuality,validateQualityPage,validateQualityReport}=vm.runInNewContext(code+'\n({SubtitleQuality,validateQualityPage,validateQualityReport})',{el,button});
const report={reportId:'report-one',format:'srt',status:'issues',encoding:'utf-8',cueCount:1,issueCount:1,errors:1,warnings:0,encodingCandidates:[]};
const makePage=(id='report-one',offset=0)=>({reportId:id,qualitySection:'issues',offset,total:1,nextOffset:null,entries:[{line:2,cue:'1',start:2000,end:1000,message:'结束早于开始',excerpt:'<img src=x onerror=alert(1)>'}]});
(async()=>{
  const host=new Node('div'),source={scope:'review',scanId:'scan',revision:1,rowId:'video-1',subtitleId:'sub-1'};
  let fail=false;
  const controller=new SubtitleQuality(async(action)=>{if(fail)throw Error('injected check failure');return action==='review.quality'?report:makePage();});
  controller.mount(host,source);await controller.run(JSON.stringify(source));
  assert.ok(host.textContent.includes('<img src=x onerror=alert(1)>'));
  assert.ok(host.textContent.includes('第 2 行'));
  assert.throws(()=>validateQualityPage({...makePage(),nextOffset:0},report.reportId,'issues',0),/分页/);
  assert.throws(()=>validateQualityPage({...makePage(),entries:[],total:1},report.reportId,'issues',0),/分页/);
  assert.throws(()=>validateQualityReport({...report,cueCount:NaN}),/格式/);
  fail=true;await controller.run(JSON.stringify(source));assert.ok(host.textContent.includes('injected check failure'));
  let complete;
  const late=new SubtitleQuality(async(action)=>action==='review.quality'?new Promise(resolve=>complete=resolve):makePage());
  const first=new Node('div'),second=new Node('div');
  late.mount(first,source);const pending=late.run(JSON.stringify(source));first.isConnected=false;
  const other={...source,subtitleId:'sub-2'};late.mount(second,other);complete(report);await pending;
  assert.equal(second.textContent,'检查字幕质量');
  console.log(JSON.stringify({passed:true,pureTextPreview:true,sourceLocations:true,invalidReportAndPageRejected:true,localErrorRetained:true,lateResultIsolated:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
