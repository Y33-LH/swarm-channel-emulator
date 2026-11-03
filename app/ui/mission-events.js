/* The journal belongs to the run, not to whichever node is currently selected. */
(()=>{
 const box=document.getElementById('events');let identity='',page=0,last='',heard=null,heardRun='';
 const fmt=row=>row.wall?row.wall.slice(11,19):'—';
 const names={start:'开始',end:'结束',fault:'异常',recover:'恢复',receipt:'回执'};
 const short=s=>s.replace('最近','近');
 function draw(){
  const rid=history?.id||S.network_record_id||'',ms=(V.snapshot?.round||0)*100;
  const events=history?(history.mission_timeline||[]).filter(r=>r.model_ms<=ms&&(r.kind!=='end'||historyIndex===history.snapshots.length-1)):(S.mission_timeline||[]);
  const display=events.length?events:history&&history.meta?.created?[{kind:'start',wall:history.meta.created,model_ms:0,label:'历史记录开始'}]:[];
  if(identity!==rid){identity=rid;page=0;last='';}
  const count=display.length,per=4,pages=Math.max(1,Math.ceil(count/per));
  page=Math.min(page,pages-1);
  const key=rid+'|'+count+'|'+page+'|'+(!!history);
  if(key!==last){
   last=key;
   const start=display.find(r=>r.kind==='start'),end=display.find(r=>r.kind==='end');
   box.innerHTML='<div class="journal-times"><span>开始 <b>'+(start?fmt(start):'—')+'</b></span><span>结束 <b>'+(end?fmt(end):'—')+'</b></span></div>'+
    display.slice().reverse().slice(page*per,(page+1)*per).map(r=>`<div class="journal-row j-${r.kind}"><time title="${esc(r.wall)}">${fmt(r)}</time><strong>${names[r.kind]}</strong><span>${esc(short(r.label))}</span></div>`).join('')+
    (pages>1?`<div class="journal-pages"><button data-prev ${page===0?'disabled':''}>较新</button><small>${page+1} / ${pages}</small><button data-next ${page+1===pages?'disabled':''}>较早</button></div>`:'');
   box.querySelector('[data-prev]')?.addEventListener('click',()=>{page--;draw();});
   box.querySelector('[data-next]')?.addEventListener('click',()=>{page++;draw();});
  }
  if(history)return;
  if(heardRun!==rid){heardRun=rid;heard=null;}
  if(heard===null){heard=S.busy&&events.length<=2?0:events.length;}
  const fresh=events.slice(heard);heard=events.length;
  if(fresh.length){window.returnSound?.announce(fresh);}
 }
 window.renderEvents=draw;
})();
