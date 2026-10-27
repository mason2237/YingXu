// Loaded by check_noqt_desktop.cjs into the actual Electron page; never shipped.
globalThis.__renderTests = null;
(async () => {
  const {VirtualFileList, ROW_HEIGHT} = await import(new URL('/js/components/file-list.js',location.href).href);
  const checks = [], assert = (ok, message) => {if (!ok) throw new Error(message);};
  const viewport = document.createElement('div'), spacer = document.createElement('div'), items = document.createElement('div');
  Object.assign(viewport.style,{position:'fixed',left:'-10000px',width:'600px',height:'252px',overflow:'auto'});
  items.style.position = 'absolute';items.style.top = '0';
  viewport.append(spacer,items);document.body.append(viewport);
  const store = new EventTarget();let calls = 0;
  const rows = Array.from({length:5000},(_,i)=>({rowId:`test-${i}`,video:{name:`影片 ${i}.mkv`},subtitles:[],warnings:[],state:'未匹配'}));
  Object.assign(store,{busy:false,error:'',summary:{scanId:'test-scan',revision:1},filters:{search:''},view:{total:rows.length},selectedId:rows[0].rowId,
    rows:async(offset,limit)=>{calls++;return rows.slice(offset,offset+limit);},select() {}});
  const list = new VirtualFileList(store,viewport,spacer,items);list.resize.disconnect();
  try {
    await list.update();
    const first = items.firstElementChild, second = first.nextElementSibling, before = calls;
    store.selectedId = rows[1].rowId;await list.draw(true);
    assert(items.firstElementChild === first && first.nextElementSibling === second,'Selection replaced visible row nodes');
    assert(calls === before && second.getAttribute('aria-selected') === 'true','Selection fetched rows again or lost highlight');
    checks.push('selection_reuses_nodes_and_cached_data');
    viewport.scrollTop = ROW_HEIGHT * 8;await list.draw();
    assert(calls === before && items.children.length <= 60,'Buffered scroll refetched rows or rendered all files');
    for (let i=50;i<5000;i+=123) {viewport.scrollTop=ROW_HEIGHT*i;await list.draw();assert(items.children.length<=60,'Virtual row bound exceeded');}
    assert(viewport.getAttribute('aria-rowcount') === '5000','Large collection count changed');
    checks.push('five_thousand_rows_bounded_buffered_scroll');
    viewport.scrollTop = 0;await list.draw();
    const previousCalls = calls;store.filters.search = 'different-filter';await list.draw(true);
    assert(calls > previousCalls,'Filter reused stale cache');
    const filterCalls = calls;store.summary.scanId = 'new-scan';await list.draw(true);
    assert(calls > filterCalls,'New scan reused old rows');
    checks.push('filter_and_scan_identity_invalidate_cache');
    // A slow reply from the old revision must not repaint a newer result.
    let finishOld;
    store.summary.revision++;store.rows=()=>new Promise(resolve=>{finishOld=resolve;});
    const stale = list.draw(true);
    store.summary.revision++;store.rows=async()=>[{...rows[0],video:{name:'最新结果.mkv'}}];store.view.total=1;
    await list.draw(true);finishOld(rows.slice(0,60));await stale;
    assert(items.children.length===1 && items.textContent.includes('最新结果'),'Stale reply replaced new rows');
    checks.push('out_of_order_replies_do_not_repaint_new_results');
    // Simultaneous selection refreshes share one request.
    let finishShared;let sharedCalls=0;
    store.summary.revision++;store.rows=()=>{sharedCalls++;return new Promise(resolve=>{finishShared=resolve;});};
    const one=list.draw(true),two=list.draw(true);finishShared([rows[0]]);await Promise.all([one,two]);
    assert(sharedCalls===1,'Repeated refresh duplicated pending query');
    checks.push('concurrent_same_page_queries_coalesced');
    store.view.total=0;await list.update();assert(items.childElementCount===0 && !viewport.hasAttribute('aria-activedescendant'),'Empty list kept stale selection');
    store.view.total=1;store.summary.revision++;store.rows=async()=>[{...rows[0],video:{name:'<img src=x>.mkv'}}];
    await list.update();assert(!items.querySelector('img') && items.textContent.includes('<img src=x>'),'Filename escaped plain text');
    checks.push('empty_restore_and_untrusted_filename_plain_text');
    globalThis.__renderTests = {passed:true,checks,queries:calls};
  } finally {list.resize.disconnect();cancelAnimationFrame(list.raf);viewport.remove();}
})().catch(error=>{globalThis.__renderTests={passed:false,error:String(error.stack||error)};});
