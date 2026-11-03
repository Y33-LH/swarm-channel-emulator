/* 固化实验记录（receiver_study.csv）canvas 重绘 + 本次实验实时工作点叠加。
   原则：固化基线数据一个字不改（三条曲线全部来自 CSV）；叠加层只有「本次实验」的
   实时投递率与等效样点 SNR 工作点，随遥测每批更新——基线静止、工作点会动。
   口径验证：固化 es 组 sigma 5793/4101/2903/2055/1455/729 ↔ 0/3/6/9/12/18 dB，
   恰为 20·log10(5793/σ)，故本次实验链路 σ 可同口径换算等效样点 SNR。 */
(function(){
 let DATA=null, LOADING=false;
 async function load(){
  if(DATA||LOADING)return; LOADING=true;
  try{
   const txt=await (await fetch('receiver_study.csv')).text();
   const lines=txt.replace(/^\uFEFF/,'').trim().split(/\r?\n/);
   const head=lines[0].split(',');
   const rows=lines.slice(1).map(l=>{const c=l.split(',');const o={};head.forEach((h,i)=>o[h]=c[i]);return o;});
   const series={es:{0:[],1:[]},eb:{0:[],1:[]},pe:{0:[],1:[]}};
   for(const r of rows){
    const m=(r.case||'').match(/^(es_comparison|eb_comparison|payload_energy)_(\d+(?:\.\d+)?)_(\d)$/);
    if(!m||!+r.attempts)continue;
    const k=m[1]==='es_comparison'?'es':m[1]==='eb_comparison'?'eb':'pe';
    series[k][m[3]].push({db:+m[2],rate:+r.delivered/+r.attempts*100});
   }
   for(const k in series)for(const f of [0,1])series[k][f].sort((a,b)=>a.db-b.db);
   DATA=series;
  }catch(e){DATA='err';}
 }
 /* 实时量：10 模型秒窗口整体投递率（DATA 加权）+ 选中链路等效样点 SNR */
 // Historical controlled sweeps and current network traffic have different
 // energy, packet mix and retry denominators. Do not overlay them.
 function live(){return {x:null,y:null};}
 function drawSub(g,x,y,w,h,p,lv,withPoint,labelLive){
  const ser=DATA[p.key];const all=[...ser[0],...ser[1]];
  if(!all.length)return;
  let xmin=Math.min(...all.map(q=>q.db)),xmax=Math.max(...all.map(q=>q.db));
  if(withPoint&&lv&&lv.x!=null){xmin=Math.min(xmin,lv.x-1);xmax=Math.max(xmax,lv.x+1);}
  const pad=(xmax-xmin)*.06||1;xmin-=pad;xmax+=pad;
  const X=v=>x+(v-xmin)/(xmax-xmin)*w, Y=v=>y+h-(v/100)*h;
  g.strokeStyle='#16324a';g.lineWidth=.6;g.fillStyle='#7c9db5';g.font='9px Consolas';
  for(const k of [0,20,40,60,80,100]){g.beginPath();g.moveTo(x,Y(k));g.lineTo(x+w,Y(k));g.stroke();g.textAlign='right';g.fillText(k,x-3,Y(k)+3);}
  g.textAlign='center';
  const step=Math.max(1,Math.round((xmax-xmin)/5));
  for(let v=Math.ceil(xmin);v<=xmax;v+=step){g.strokeStyle='#12293e';g.beginPath();g.moveTo(X(v),y);g.lineTo(X(v),y+h);g.stroke();g.fillStyle='#7c9db5';g.fillText(v,X(v),y+h+11);}
  g.fillText('dB',x+w,y+h+11);
  g.fillStyle='#9fc0d8';g.font='9px sans-serif';g.textAlign='center';
  g.fillText(p.title,x+w/2,y-13);
  g.fillStyle='#5f7f96';g.fillText(p.sub,x+w/2,y-2);
  for(const [fec,color] of [[0,'#f2a65a'],[1,'#3fd4d0']]){
   const pts=ser[fec];if(!pts.length)continue;
   g.strokeStyle=color;g.lineWidth=1.6;g.beginPath();
   pts.forEach((q,i)=>{const px=X(q.db),py=Y(q.rate);i?g.lineTo(px,py):g.moveTo(px,py);});
   g.stroke();
   for(const q of pts){g.fillStyle=color;g.beginPath();g.arc(X(q.db),Y(q.rate),2.4,0,Math.PI*2);g.fill();}
  }
  g.font='9px sans-serif';g.textAlign='left';
  g.fillStyle='#f2a65a';g.fillText('— 关闭纠错',x+6,y+h-20);
  g.fillStyle='#3fd4d0';g.fillText('— 完整纠错',x+6,y+h-9);
  if(lv&&lv.y!=null){
   g.strokeStyle='#7ff0d4';g.setLineDash([4,3]);g.lineWidth=1;
   g.beginPath();g.moveTo(x,Y(lv.y));g.lineTo(x+w,Y(lv.y));g.stroke();g.setLineDash([]);
   if(labelLive){g.fillStyle='#7ff0d4';g.font='9px sans-serif';g.textAlign='left';
    g.fillText('本次 '+lv.y.toFixed(1)+'%',x+3,Math.max(y+9,Y(lv.y)-3));}
   if(withPoint&&lv.x!=null){
    const px=X(lv.x),py=Y(lv.y);
    g.fillStyle='#7ff0d4';g.beginPath();
    g.moveTo(px,py-5);g.lineTo(px+5,py);g.lineTo(px,py+5);g.lineTo(px-5,py);g.closePath();g.fill();
    g.strokeStyle='#0a1926';g.stroke();
   }
  }
 }
 window.drawStudy=function(canvas){
  load();
  const cv=canvas||document.getElementById('rxStudyCanvas');if(!cv)return;
  const dpr=window.devicePixelRatio||1;
  const w=cv.clientWidth||cv.parentElement?.clientWidth||900;
  const h=cv.id==='rxStudyCanvas'?(cv.clientHeight||320):Math.round(w*0.36);
  const W=Math.round(w*dpr),H=Math.round(h*dpr);
  if(cv.width!==W||cv.height!==H){cv.width=W;cv.height=H;}
  const g=cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);
  g.fillStyle='#0a1926';g.fillRect(0,0,w,h);
  if(!DATA||DATA==='err'){
   g.fillStyle='#7391a5';g.font='12px sans-serif';
   g.fillText(DATA==='err'?'receiver_study.csv 读取失败':'固化数据加载中…',20,30);
   if(!DATA)setTimeout(()=>window.drawStudy(canvas),400);
   return;
  }
  const lv=live();
  const plots=[
   {key:'es',title:'样点 SNR · 编码能量',sub:'历史受控测量'},
   {key:'eb',title:'保护信息位 Eb/N0',sub:'历史受控测量'},
   {key:'pe',title:'总帧能量 / 载荷位',sub:'历史受控测量'},
  ];
  const pw=(w-36)/3;
  plots.forEach((p,i)=>drawSub(g,12+i*(pw+6),44,pw-46,h-102,p,lv,i===0,i===0));
  g.fillStyle='#7f9db8';g.font='10px sans-serif';g.textAlign='center';
  g.fillText('1020 次实板收发 · 噪声点各 30 帧 · 连线仅连接已测点'+(lv.y!=null?` · 本次实验投递率 ${lv.y.toFixed(1)}%（10 模型秒窗口）`:''),w/2,14);
  g.textAlign='left';
 };
 window.refreshStudy=function(){
  const cv=document.getElementById('rxStudyCanvas');
  if(cv&&cv.offsetParent)window.drawStudy(cv);
 };
})();
