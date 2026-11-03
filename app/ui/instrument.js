/* Visual instruments are driven by saved/current board data, never synthetic measurements. */
(() => {
 const M=ChannelMath, C={good:'#63e1c4',degraded:'#ffc879',broken:'#ff6f84',unknown:'#718a9b'},ns='http://www.w3.org/2000/svg';
 const fmt=(v,n=2)=>Number.isFinite(v)?num(v,n):'—';
 const envText=['按旷野 → 郊区 → 城市切换，复现三环境基准。','较低多径和较小参数起伏，作为稳定对照。','比旷野增加回波与位置扰动；噪声由用户独立设定。','中等回波与参数起伏，用于过渡场景。','较强回波和更大扰动，观察重传与送达时延。','较长回波及山地DEM；启用地形传播后按路径剖面计算单主障碍绕射。','丘陵DEM及中等多径；可启用单主障碍绕射，不执行射线追踪。','高原DEM与较低附加衰减预设；不是高海拔实测标定。'];
 const weatherText=['不增加天气损耗和位置扰动。','加入轻微天气损耗和位置扰动。','小幅增加等效损耗及编队扰动。','在小雨基础上增加损耗与扰动。','强降雨参数预设；注意链路余量下降。','轻度雪天参数预设；观察回传质量。','较强雪天参数预设；注意重传增加。','恶劣雪天参数预设；注意通信与位置时效。'];
 const formationText=['16 节点四臂 X 形；速度、间距、高度与朝向均可调整。','16 节点横向排列，间距为最近节点标称距离。','16 节点纵向排列，间距为最近节点标称距离。','16 节点双臂 V 形，共用固定四组路由。','16 节点三角布局，固定多跳路由保持不变。','16 节点梯形布局；可调整标称间距与朝向。','16 节点菱形布局；可调整标称高度与间距。','4 × 4 方阵，便于比较相邻与空地链路。','16 节点环形；可调整间距、朝向和中心位置。'];
 let shapePoints=null,cardReady=false;
 fetch('formation-icons.json').then(r=>r.json()).then(x=>{shapePoints=x;if(catalog)buildChoices();}).catch(()=>{});
 function svgIcon(kind,id){
  const s=document.createElementNS(ns,'svg');s.setAttribute('viewBox','0 0 64 44');s.setAttribute('aria-hidden','true');
  if(kind==='formation'){
   let p=shapePoints?.[id]||[];if(!p.length)p=Array.from({length:16},(_,i)=>[(i%4-1.5)*(i<8?1:-1),Math.floor(i/4)-1.5]);
   const mx=Math.max(1,...p.map(x=>Math.abs(x[0]))),my=Math.max(1,...p.map(x=>Math.abs(x[1]))),sc=Math.min(24/mx,16/my);
   s.innerHTML=p.map(([x,y])=>`<circle cx="${32+x*sc}" cy="${22-y*sc}" r="1.9" fill="currentColor"/>`).join('');
  }else if(kind==='weather'){
   const sun='<circle cx="32" cy="20" r="8"/><path d="M32 5v4m0 22v4M17 20h4m22 0h4M21 9l3 3m16 16 3 3M21 31l3-3m16-16 3-3"/>';
   const cloud='<path d="M17 25h30c10 0 9-13 1-13-2-11-20-11-23-2-10-2-16 13-8 15Z"/>';
   s.innerHTML=`<g fill="none" stroke="currentColor" stroke-width="1.5">${id===0?sun:cloud}${id===1?'<path d="M14 30h36M20 35h28"/>':id>=2&&id<=4?Array.from({length:id===2?2:id===3?3:5},(_,i)=>`<path d="M${19+i*6} 29l-3 8"/>`).join(''):id>=5?Array.from({length:id-3},(_,i)=>`<path d="M${18+i*7} 30v8m-3-4h6"/>`).join(''):''}</g>`;
  }else{
   const paths=['M10 29 23 13 37 26 53 9M10 35h44','M4 32q12-14 27-3t29-4M10 38h45','M8 31V20l9-8 9 8v11m-13 0v-8h8v8m13 0V13h16v18','M9 33V17h12v16m6 0V9h14v24m6 0V21h10v12','M6 35V16h12v19m7 0V6h14v29m6 0V13h13v22M28 12h8m-8 6h8m-8 6h8','M4 35 24 7 40 35M27 35 44 15 60 35M18 16l6 5 5-6','M3 35q10-29 24-5 13-24 34 5','M5 35 18 14h27l15 21'];
   s.innerHTML=`<path d="${paths[id]}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>`;
  }return s;
 }
 function buildChoices(){if(!catalog)return;for(const kind of ['environment','weather','formation']){const grid=$(kind+'Cards');if(!grid)continue;grid.replaceChildren();for(const item of catalog[kind]){const b=document.createElement('button');b.type='button';b.className='option-card';b.dataset.value=item.id;b.setAttribute('aria-label',item.name);b.setAttribute('aria-pressed','false');b.append(svgIcon(kind,item.id),document.createTextNode(item.name));b.onclick=()=>{if(window.causalPresentation?.active||$('configFields').disabled){window.requestSceneChoice?.(kind,item.id,item.name);return;}$(kind).value=item.id;$(kind).dispatchEvent(new Event('change',{bubbles:true}));$(kind).dispatchEvent(new Event('input',{bubbles:true}));syncChoices();};grid.append(b);}}cardReady=true;syncChoices();}
 function syncChoices(){if(!catalog)return;if(!cardReady){buildChoices();return;}for(const kind of ['environment','weather','formation']){const grid=$(kind+'Cards');if(!grid)continue;const id=Number($(kind).value);grid.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-pressed',String(Number(b.dataset.value)===id));b.disabled=!!history;});const desc=$(kind+'Description');if(desc)desc.innerHTML=`<b>${esc(catalog[kind][id]?.name)}</b>${esc(({environment:envText,weather:weatherText,formation:formationText})[kind][id])}<br><small>${kind==='formation'?'16 节点 · 编队仅改变几何关系，非自动选路':kind==='weather'?'受控扰动预设，非真实气象安全预测':'空空 / 空地分别施加参数，空地起伏更大'}</small>`;}}
 window.syncChoices=syncChoices;
 function axes(id,xlabel,ylabel,xmin,xmax,ymin,ymax,xf=x=>fmt(x,1),yf=x=>fmt(x,2),equal=false){
  const c=canvasSize($(id));if(!c||c.w<50||c.h<40)return null;const {g,w,h}=c;
  const pw=equal?Math.min(w-59,h-45):w-59,ph=equal?pw:h-45,x=equal?(w-pw)/2:44,y=15;g.font='9px Consolas';g.lineWidth=1;
  for(let i=0;i<=4;i++){const py=y+ph-i/4*ph;g.strokeStyle='#24404b77';g.beginPath();g.moveTo(x,py);g.lineTo(x+pw,py);g.stroke();g.fillStyle='#8aa8b4';g.textAlign='right';g.fillText(yf(ymin+i/4*(ymax-ymin)),x-6,py+3);}
  g.textAlign='center';for(let i=0;i<=4;i++)g.fillText(xf(xmin+i/4*(xmax-xmin)),x+i/4*pw,y+ph+14);
  g.textAlign='left';g.fillStyle='#a5c2cb';g.fillText(ylabel,5,10);g.textAlign='right';g.fillText(xlabel,w-6,h-2);g.textAlign='left';
  return {...c,x,y,pw,ph,xy:(a,b)=>[x+(a-xmin)/(xmax-xmin)*pw,y+ph-(b-ymin)/(ymax-ymin)*ph]};
 }
 function empty(c,label='等待本链路实测数据',hint=''){if(!c)return;const g=c.g;g.textAlign='center';g.fillStyle='#5a8a9c';g.font='12px Microsoft YaHei';g.fillText(label,c.w/2,c.h/2-10,Math.max(20,c.w-10));if(hint){g.fillStyle='#3d6a7a';g.font='11px Microsoft YaHei';g.fillText(hint,c.w/2,c.h/2+12,Math.max(20,c.w-10));}g.textAlign='left';}
 function line(c,points,color,connect=true){if(!c)return;const g=c.g;g.save();g.beginPath();g.rect(c.x,c.y,c.pw,c.ph);g.clip();g.strokeStyle=color;g.fillStyle=color;g.lineWidth=1.6;let started=false;g.beginPath();for(const p of points){if(p[1]==null){started=false;continue;}const [x,y]=c.xy(...p);if(connect&&started)g.lineTo(x,y);else g.moveTo(x,y);started=true;}g.stroke();for(const p of points){if(p[1]==null)continue;const [x,y]=c.xy(...p);g.beginPath();g.arc(x,y,connect?2:2.6,0,Math.PI*2);g.fill();}g.restore();}
 function series(){return (window.causalPresentation?.active?window.causalPresentation.trace||[]:history?history.snapshots:S.snapshots||[]).filter(s=>s.round<=(V.snapshot?.round||0)).slice(-120);}
 const PDP={update(v){
  if(!v){empty(axes('cir','额外时延 / μs','功率 / dB',0,1,-60,0),'等待同帧抽头读回');return;}
  const ds=v.delays.map(x=>x*1e6),max=Math.max(.25,...ds),db=v.powers.map(p=>10*Math.log10(Math.max(1e-9,p)));
  const a=axes('cir','额外时延 / μs','功率 / dB',-.05*max,max*1.12,Math.min(-45,...db)-3,Math.max(0,...db)+2,x=>fmt(x,2),x=>fmt(x,0));if(!a)return;
  const g=a.g,colors=['#52dcd5','#b2a2ff','#ffc879','#82b9ff'];
  ds.forEach((d,i)=>{if(v.powers[i]<=0)return;const [x,y]=a.xy(d,db[i]);g.strokeStyle=colors[i%4];g.lineWidth=Math.max(3,Math.min(15,a.pw/(ds.length*5)));g.beginPath();g.moveTo(x,a.y+a.ph);g.lineTo(x,y);g.stroke();g.fillStyle=colors[i%4];g.font='9px Consolas';g.fillText(String(i),x+3,y-3);});
 }};
 /* ── 实收 I/Q 三级来源：单帧实测 → 最近一帧实况（PHYSTATS/IQ 轮询）→ 快照中的观测链路采样 ──
    数据格式注意：lab 与 phy_live 的 iq 已是 [I,Q] 数值对（服务端 IQ 命令已解包）；
    只有快照里的 watch_iq 是打包 32 位字，需要 unpack。混用 unpack 会把数值对全毁成 [0,0]。 */
 const i16=x=>{x&=0xffff;return x>=0x8000?x-0x10000:x;};
 const unpack=w=>[i16(w),i16(w>>>16)];
 function liveIQ(){
  const lab=window.currentLab?window.currentLab():null;
  if(lab?.iq?.received?.length)return{received:lab.iq.received,equalized:lab.iq.equalized,tag:'单帧实测',gen:null};
  const pl=window.frameObservation?.();
  if(pl?.received?.length)return{received:pl.received,equalized:pl.equalized,tag:`链路 ${pl.link_id} · ${fmt(pl.model_ms/1000,3)}s`,gen:pl.generation};
  return null;
 }
 /* Continuous ADC-equivalent baseband samples, never interpolated symbols. */
 function drawEye(){
  const pl=window.frameObservation?.(),wave=pl?.waveform_samples,pts=wave?.received||[];
  const peak=Math.max(1200,...pts.flat().map(Math.abs))*1.1,sps=wave?.samples_per_symbol||4;
  const ax=axes('eye','符号周期','I / 定点码值',0,2,-peak,peak,x=>fmt(x,1),x=>fmt(x/1000,1)+'k');
  if(!pts.length){empty(ax,'等待连续接收样本','符号抽样不能替代真实眼图');$('eyeValue').textContent='本帧暂无波形';return;}
  for(let i=0;i+2*sps<pts.length;i+=sps){line(ax,pts.slice(i,i+2*sps+1).map((p,k)=>[k/sps,p[0]]),'#60e8db55',true);}
  $('eyeValue').textContent=`${pts.length} 连续样本 · ${sps} 点/符号 · 同帧#${pl.generation}`;
 }
 // Each bank belongs to one board snapshot, so seeking cannot retain future samples.
 function wallFeed(){
  const snap=V.snapshot,cells={};
  if(Array.isArray(snap?.wall_iq)){
   for(const [id,ms,generation,encoded] of snap.wall_iq){
    const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
    const view=new DataView(bytes.buffer),raw=[],pts=[];
    for(let i=0;i<bytes.length;i+=8){
     raw.push(unpack(view.getUint32(i,true)));pts.push(unpack(view.getUint32(i+4,true)));
    }
    cells[id]={raw,pts,at:ms,generation};
   }
  }else{
   for(const o of [...Object.values(V.phy_links||{}),V.phy_live]){
    if(Observation.select(o,snap,o?.link_id))cells[o.link_id]={raw:o.received||[],pts:o.equalized||[],at:o.model_ms,evm:o.evm_percent};
   }
  }
  return cells;
 }
 function drawWall(){
  const iqCells=wallFeed();
  const c=canvasSize($('iqWall'));if(!c)return;const {g,w,h}=c;
  const rows=4,cols=4,cw=w/cols,ch=h/rows,s=V.snapshot,watch=Number($('linkSelect').value);
  let fresh=0;
  for(let i=0;i<16;i++){
   const x=i%cols*cw,y=Math.floor(i/cols)*ch;
   const a=i+1,b=a%4?a+1:0;
   const cell=iqCells[i],row=(V.link_windows||[]).find(r=>r.link_id===i);
   const isWatch=i===watch;
   g.strokeStyle=isWatch?'#2df5c6':'#1b3a5e';g.lineWidth=isWatch?1.6:1;g.strokeRect(x+1,y+1,cw-2,ch-2);
   g.fillStyle=isWatch?'#7ef2f5':'#6d8aa3';g.font='9px Consolas';g.textAlign='left';
   g.fillText(`${String(i).padStart(2,'0')} ${a}→${b||'地'}`,x+5,y+11);
   if(cell?.evm!=null&&row&&cw>=110){g.textAlign='right';g.fillStyle=M.linkState(row)==='good'?'#63e1c4':M.linkState(row)==='broken'?'#ff6f84':'#ffc879';
    g.fillText(`EVM ${cell.evm!=null?fmt(cell.evm,1)+'%':'—'}`,x+cw-5,y+11);g.textAlign='left';}
   if(cell?.raw.length){
    g.fillText(fmt((s.round*100-cell.at)/1000,1)+'s前',x+4,y+ch-4,Math.max(12,cw-8));
    fresh++;
    const bound=Math.max(1500,...cell.raw.flat().map(Math.abs),...cell.pts.flat().map(Math.abs))*1.15;
    const px=v=>x+cw/2+v/bound*(cw/2-8),py=v=>y+ch/2-v/bound*(ch/2-10);
    g.fillStyle='rgba(140,160,180,.25)';
    for(const p of cell.raw)g.fillRect(px(p[0])-1,py(p[1])-1,2,2);
    g.fillStyle='#5ff0ea';
    for(const p of cell.pts){g.beginPath();g.arc(px(p[0]),py(p[1]),1.6,0,Math.PI*2);g.fill();}
    // 判决参考十字
    g.strokeStyle='#2a4f5a55';g.beginPath();g.moveTo(x+cw/2,y+14);g.lineTo(x+cw/2,y+ch-4);g.moveTo(x+4,y+ch/2);g.lineTo(x+cw-4,y+ch/2);g.stroke();
   }else{g.fillStyle='#3d6a7a';g.font='9px Microsoft YaHei';g.fillText(cell?'本帧无符号':'等待 DATA',x+5,y+ch/2+3,Math.max(12,cw-8));}
  }
  $('iqWallValue').textContent=fresh?`${fresh}/16 路实收 · 灰=均衡前 青=均衡后`:'等待实验运行';
 }
 function channelRow(s,id){return s.observation?.link===id?s.observation.applied:s.protocol>=20?null:s.applied_links?.[id];}
 function drawInstruments(){
  const id=Number($('linkSelect').value),c=window.observedChannel?window.observedChannel(id):V.scene?.find(x=>x.link_id===id),valid=c&&c.applied!==false,stat=valid?M.statistics(c):null,s=V.snapshot,rows=V.link_windows||[],row=rows.find(x=>x.link_id===id),data=series(),lab=window.currentLab?window.currentLab():null;
  const frame=window.frameObservation?.();const stamp=frame?' · 帧#'+frame.generation:'';
  PDP.update(stat);
  $('cirValue').textContent=stat?.rms!=null?`${stat.powers.length} 有效时延位置 · RMS ${fmt(stat.rms*1e9,1)} ns${stamp}`:'待读回 / 无有效功率';
  const halfRate=(c?.sample_rate_hz||8e6)/2e6;
  // CFR 量程自适应：固定 -50~6 太大，实际响应集中在窄带内
  const b=valid?(()=>{const pts=Array.from({length:181},(_,i)=>{const f=-halfRate+i/180*2*halfRate;return [f,20*Math.log10(Math.max(1e-9,M.response(c,f*1e6)))];});const vs=pts.map(p=>p[1]);const lo=Math.min(...vs),hi=Math.max(...vs),pad=Math.max(3,(hi-lo)*.25);return {ax:axes('cfr','频率 / MHz','幅度 / dB',-halfRate,halfRate,lo-pad,hi+pad),pts};})():null;
  if(b&&b.ax){const {g}=b.ax,base=b.ax.y+b.ax.ph;g.save();g.beginPath();g.rect(b.ax.x,b.ax.y,b.ax.pw,b.ax.ph);g.clip();g.beginPath();b.pts.forEach((p,i)=>{const [x,y]=b.ax.xy(...p);i?g.lineTo(x,y):g.moveTo(x,y);});const grd=g.createLinearGradient(0,b.ax.y,0,base);grd.addColorStop(0,'rgba(85,220,213,.30)');grd.addColorStop(1,'rgba(85,220,213,.02)');g.lineTo(b.ax.x+b.ax.pw,base);g.lineTo(b.ax.x,base);g.closePath();g.fillStyle=grd;g.fill();g.restore();line(b.ax,b.pts,'#55dcd5',true);}else empty(axes('cfr','频率 / MHz','幅度 / dB',-4,4,-50,6),'暂无频率响应','运行一次实验后自动读回');
  $('cfrValue').textContent=valid?`${M.taps(c).length} 抽头 · 同帧系数计算${stamp}`:'待读回';
  const trend=[];let previousStamp=null;let count=0;
  function addTaps(ms,gains){
   if((previousStamp!=null&&ms<=previousStamp)||!gains.length)return;
   count=Math.max(count,gains.length);trend.push([ms/1000,...gains]);previousStamp=ms;
  }
  for(const snap of data){
   if(snap.watch_link===id)for(const [ms,...gains] of snap.tap_history||[])addTaps(ms,gains.map(g=>g/32768));
   const aa=channelRow(snap,id);
   if(aa?.[0]&&(previousStamp==null||aa[1]>previousStamp)){
    const bank=snap.observation?.link===id?snap.observation.taps:null;
    addTaps(aa[1],bank?.length?bank.map(t=>t[0]/32768):[aa[3]/32768,aa[4]/32768]);
   }
  }
  if(lab){trend.splice(0,trend.length,[0,...M.taps(c).map(t=>t.gain)]);count=M.taps(c).length;}
  const xmax=Math.max(1,...trend.map(x=>x[0])),xmin=trend.length?Math.max(0,trend[0][0]-1):0;
  const en=axes('envelope',lab?'单帧':'模型时间 / s','抽头幅度',xmin,xmax,0,Math.max(.01,...trend.flatMap(x=>x.slice(1)))*1.15,x=>fmt(x,0));
  const colors=['#55dcd5','#b2a2ff','#ffc879','#82b9ff','#e287d6','#9fce6e','#fb9879','#80bad7'];
  for(let k=0;k<count;k++)line(en,trend.map(x=>[x[0],x[k+1]??null]),colors[k],true);
  if(!trend.length)empty(en,'等待所选链路 DATA 帧','实际抽头读回，无自动生成曲线');
  $('envelopeValue').textContent=trend.length?`${trend.length} 帧 · ${count} 抽头 · 线段仅连接采样点`:'尚无时序样本';
  const q=data.map((x,i)=>M.windowQuality(x,data[i-1],id)).filter(Boolean);
  // 量程自适应：好链路时数据都挤在 95-100%，固定 0-100% 轴会把变化压成一条直线。
  const allQ=q.flatMap(x=>[x.capture,x.hop].filter(v=>v!=null));
  const qLo=allQ.length?Math.max(0,Math.min(...allQ)*100-8):0;
  const qc=axes('linkQuality','模型时间 / s','%',q.length?Math.max(0,q[0].time-1):0,Math.max(1,...q.map(x=>x.time)),qLo,100,x=>fmt(x,0),x=>fmt(x,0));
  if(!lab&&q.length){line(qc,q.map(x=>[x.time,x.capture===null?null:x.capture*100]),'#55dcd5');line(qc,q.map(x=>[x.time,x.hop===null?null:x.hop*100]),'#ffc879');}else empty(qc,lab?'单帧测试：请查看捕获与 CRC 状态':'等待网络统计窗口',lab?'':'选择一条链路后自动显示该链路质量趋势');
  $('linkQualityValue').textContent=q.length?`青 PN / 金 ACK · 最近 ${fmt(q.at(-1).time,1)} s`:'等待窗口计数';
  const pairs=(id,values)=>$(id).innerHTML=values.map(([k,v])=>`<div><span>${k}</span><b>${esc(v)}</b></div>`).join('');
  // 几何多普勒：实收 CFO 减去固件振荡器偏移表（与 sw/scene_product.c osc[] 同源）
  const OSC=[0,-113,24,161,-203,-66,71,208,-156,-19,118,-246,-109,28,165,-199,-62];
  let doppler=null,tx0=id%16+1,rx0=tx0%4?tx0+1:0;if(id>=16)[tx0,rx0]=[rx0,tx0];
  if(!lab&&valid){if(c.model_metadata&&c.model_metadata[4]!==2)doppler=c.model_metadata[2];else if(!s?.config?.channel||s.config.channel.mode===0)doppler=c.cfo_hz-(OSC[tx0]-OSC[rx0]);}
  const snrLin=stat?.total&&c.sigma>0?stat.total*8192*8192/(2*c.sigma*c.sigma):null;
  const capHz=snrLin?Math.log2(1+snrLin):null;
  pairs('channelStatistics',[
   ['有效抽头 / 支持',stat?`${stat.powers.filter(x=>x>0).length} / 8`:'— / 8'],
   ['RMS 时延扩展',stat&&stat.rms!==null?fmt(stat.rms*1e9,1)+' ns':'—'],
   ['相干带宽粗估¹',stat?.bandwidth?fmt(stat.bandwidth/1e6,3)+' MHz':stat?.total?'平坦单径 / 不定义':'—'],
   ['几何多普勒频移²',doppler!=null?fmt(doppler,1)+' Hz':'—'],
   ['相干时间', '待实测自相关；不由单径 CFO 推算'],
   ['抽头功率 / 噪声功率',snrLin?fmt(10*Math.log10(snrLin),2)+' dB（非网络容量）':'—'],
   ['抽头功率等效衰减',stat?.attenuation!=null?fmt(stat.attenuation,2)+' dB':'—'],
   ['主径时延',valid?fmt(c.delay_samples/(c.sample_rate_hz||8e6)*1e6,3)+' μs':'—'],
   ['主径 / 回波频偏',valid?fmt(c.cfo_hz,1)+' / '+fmt(c.echo_cfo_hz,1)+' Hz':'—']]);
  $('channelStatistics').title='1/(5×RMS时延扩展)仅为经验读图近似。新模型的几何多普勒来自同帧 ARM 位置导数，排除散射频移与本振差；自主信道不推算几何多普勒。抽头功率不等于相关多径波形的实际接收功率；网络容量由有期限的负载实验测量。';
  pairs('linkStatistics',[
   ['窗口 DATA / ACK',!lab&&row?`${row.data_attempts} / ${row.ack_attempts}`:'—'],
   ['帧头捕获率',!lab?pct(row?.capture_rate):lab.registers?.['100']?'1 / 1':'0 / 1'],
   ['逐跳成功率',!lab?pct(row?.hop_success):'单帧不含逐跳 ACK'],
   ['纠错前 BER',lab?(lab.phy.pre_bits?(lab.phy.pre_errors/lab.phy.pre_bits).toExponential(2):'—'):row?.pre_ber==null?'—':row.pre_ber.toExponential(2)],
   ['纠错后 BER',lab?(lab.phy.post_bits?(lab.phy.post_errors/lab.phy.post_bits).toExponential(2):'—'):row?.post_ber==null?'—':row.post_ber.toExponential(2)],
   ['均衡后 EVM',fmt(lab?.payload_evm_percent??row?.evm_percent,2)+(Number.isFinite(lab?.payload_evm_percent??row?.evm_percent)?' %':'')],
   ['唯一有效载荷速率',!lab&&row?fmt(row.unique_hop_payload_bps,1)+' bit/s':'—']]);
  const points=liveIQ();const peak=Math.max(800,...(points?.received||[]).flat().map(Math.abs),...(points?.equalized||[]).flat().map(Math.abs));const bound=peak*1.18;
  for(const [key,name] of [['iqBefore','received'],['iqAfter','equalized']]){const iq=axes(key,'I / 定点码值','Q / 定点码值',-bound,bound,-bound,bound,x=>fmt(x/1000,0)+'k',x=>fmt(x/1000,0)+'k',true);if(points?.[name]?.length)line(iq,points[name],'#60e8db',false);else empty(iq,'暂无 I/Q 样本','实验运行后每批自动读回最近一帧真实符号');$(key+'Value').textContent=points?.[name]?.length?points[name].length+' 点 · '+points.tag+(points.gen!=null?' · 帧#'+points.gen:''):'暂无样本';}
  drawEye();drawWall();
  const values=[['主径幅度',valid?fmt(c.gain0,4):'—'],['回波幅度',valid?fmt(c.gain1,4):'—'],['I/Q 噪声 σ',valid?fmt(c.sigma,0):'—'],['主径初相位',valid?fmt((c.phase_radians||0)*180/Math.PI,1)+'°':'—'],['额外回波时延',valid?fmt((M.taps(c).at(-1).delay_samples-M.taps(c)[0].delay_samples)/(c.sample_rate_hz||8e6)*1e6,3)+' μs':'—']];
  $('appliedTicker').innerHTML=values.map(([k,v])=>`<span>${k}<b>${esc(v)}</b></span>`).join('');
  const td=s?.tdma;
  $('tdmaReadback').textContent=s?`100 ms / 20×5 ms · 模型超限 ${s.slot_misses} · ARM超时 ${td?.arm_service_overruns??'—'}`:'100 ms / 20×5 ms；等待实际预算读回';
  $('tdmaReadback').title=td?`模型波形最大 ${td.max_model_samples} 样本；PL 最大 ${(td.max_pl_cycles/62500).toFixed(3)} ms / 超限 ${td.pl_service_overruns}；ARM 单次服务最大 ${(td.max_arm_transaction_us/1000).toFixed(3)} ms / 超限 ${td.arm_service_overruns}。模型时隙与实际计算耗时分开；ARM 超时不等于模型丢包，也不能宣称严格实时。`:'模型 TDMA 调度，不将模型时间冒充墙钟。';
 }
 function nodeColor(n){if(n.preview||!n.known)return C.unknown;const r=(V.link_windows||[]).find(x=>x.link_id===n.id-1);const state=M.linkState(r);return state==='broken'?C.broken:!n.fresh||state==='degraded'?C.degraded:C.good;}
 function drawRisk(){const rm=$('riskMap');if(!rm)return;const c=canvasSize(rm);if(!c)return;const {g,w,h}=c,nodes=Array.from({length:16},(_,i)=>nodeData(i+1)).filter(Boolean);const rs=$('riskSource');if(rs)rs.textContent=V.snapshot?(history?'历史实收':'地面实收'):'配置预览';
  const visible=nodes.filter(n=>n.preview||n.known),xs=visible.map(n=>n.xyz[0]),ys=visible.map(n=>n.xyz[1]);const cx=xs.length?(Math.max(...xs)+Math.min(...xs))/2:5000,cy=ys.length?(Math.max(...ys)+Math.min(...ys))/2:5000,range=Math.max(500,...xs.map(x=>Math.abs(x-cx)),...ys.map(y=>Math.abs(y-cy)))*2.5;
  g.strokeStyle='#1d3942';for(let i=1;i<5;i++){g.beginPath();g.moveTo(i*w/5,0);g.lineTo(i*w/5,h);g.stroke();}for(let i=1;i<4;i++){g.beginPath();g.moveTo(0,i*h/4);g.lineTo(w,i*h/4);g.stroke();}
  g.font='9px Consolas';for(const n of visible){const x=w/2+(n.xyz[0]-cx)/range*(w-20),y=h/2-(n.xyz[1]-cy)/range*(h-20);g.fillStyle=nodeColor(n);g.beginPath();g.arc(x,y,4,0,Math.PI*2);g.fill();g.fillText(String(n.id),x+6,y+3);}
  if(!visible.length){g.fillStyle=C.unknown;g.fillText('等待实收位置',w/2-30,h/2);}}
 window.renderInstruments=()=>{document.body.classList.toggle('has-history',!!history);syncChoices();drawRisk();if(tab==='evidence')drawInstruments();};
 let lastFrame=0;
 window.drawInstrumentMap=()=>{
  if(tab!=='mission')return;
  const c=canvasSize($('map'));if(!c)return;const {g,w,h}=c,tiltEl=$('mapPerspective'),tilt=tiltEl?tiltEl.value==='3d':true,nodes=Array.from({length:16},(_,i)=>nodeData(i+1)).filter(Boolean),visible=nodes.filter(n=>n.preview||n.known),cfg=V.snapshot?.config||preview?.config||catalog?.defaults;
  if(!cfg)return;
  const coords=visible.map(n=>n.xyz).concat([[5000,5000,0]]),xs=coords.map(p=>p[0]),ys=coords.map(p=>p[1]);
  const full=$('mapView').value==='full',cx=full?5000:(Math.min(...xs)+Math.max(...xs))/2,cy=full?5000:(Math.min(...ys)+Math.max(...ys))/2;
  const range=full?11000:Math.max(1800,Math.max(...xs)-Math.min(...xs)+650,Math.max(...ys)-Math.min(...ys)+650);
  const maxZ=Math.max(300,...visible.map(n=>n.xyz[2]));
  // Fit actual projected positions (including height), not a square XY extent.
  const project=p=>[p[0]+(tilt?.22*p[1]:0),-(tilt?.65:1)*p[1]-(tilt?(p[2]||0)*3:0)];
  const bounds=(full?[[0,0,0],[10000,0,0],[0,10000,0],[10000,10000,0],...coords]:coords).map(project);
  let loX=Math.min(...bounds.map(p=>p[0])),hiX=Math.max(...bounds.map(p=>p[0])),loY=Math.min(...bounds.map(p=>p[1])),hiY=Math.max(...bounds.map(p=>p[1]));
  const midX=(loX+hiX)/2,midY=(loY+hiY)/2,spanX=Math.max(1000,hiX-loX),spanY=Math.max(750,hiY-loY);
  const scale=Math.min(Math.max(100,w-115)/spanX,Math.max(100,h-155)/spanY);
  const xy=p=>{const q=project(p);return [w/2+(q[0]-midX)*scale,(h-15)/2+(q[1]-midY)*scale];};
  const env=cfg.environment||([1,3,4][Math.min(2,Math.floor((V.snapshot?.scene_ms??(V.snapshot?.round||0)*100)/300000))]);
  g.fillStyle='#06131e';g.fillRect(0,0,w,h);
  const im=window.offlineMapImage?.(env),sat=$('basemapMode').value==='satellite';
  g.save();const origin=xy([0,0,0]),dx=xy([1,0,0]),dy=xy([0,1,0]);g.setTransform(devicePixelRatio*(dx[0]-origin[0]),devicePixelRatio*(dx[1]-origin[1]),devicePixelRatio*(dy[0]-origin[0]),devicePixelRatio*(dy[1]-origin[1]),devicePixelRatio*origin[0],devicePixelRatio*origin[1]);
  g.beginPath();g.rect(0,0,10000,10000);g.clip();
  if(sat&&im){g.save();g.translate(-3000,10000);g.scale(1,-1);g.globalAlpha=.76;g.drawImage(im,0,0,16000,10000);g.restore();}else{g.fillStyle='#0d2835';g.fillRect(0,0,10000,10000);}
  g.fillStyle='#03172526';g.fillRect(0,0,10000,10000);g.restore();
  window.drawWorkflowWeather?.(g,w,h,cfg.weather,(V.snapshot?.round||0)/10);
  g.strokeStyle='#57a6b84d';g.lineWidth=.7;for(let m=0;m<=10000;m+=1000){for(const endpoints of [[[m,0,0],[m,10000,0]],[[0,m,0],[10000,m,0]]]){g.beginPath();g.moveTo(...xy(endpoints[0]));g.lineTo(...xy(endpoints[1]));g.stroke();}}
  const frame=[[0,0,0],[10000,0,0],[10000,10000,0],[0,10000,0]];g.strokeStyle='#448a9a';g.lineWidth=1.2;g.beginPath();frame.forEach((p,i)=>i?g.lineTo(...xy(p)):g.moveTo(...xy(p)));g.closePath();g.stroke();
  if(tilt){g.fillStyle='#0a263477';g.beginPath();[[0,0,0],[10000,0,0],[10000,0,-90],[0,0,-90]].forEach((p,i)=>i?g.lineTo(...xy(p)):g.moveTo(...xy(p)));g.closePath();g.fill();}
  $('mapExtent').textContent=tilt?'10 × 10 × 1 km · 高度投影':'10 × 10 km · 平面俯视';
  const animate=(!history&&S.busy&&S.status==='running'&&!pollFailed)||(history&&replayTimer),motion=animate&&!matchMedia('(prefers-reduced-motion: reduce)').matches,phase=motion?performance.now()/1200:0;
  mapTargets=[];const ground=[5000,5000,0];
  for(const n of visible){const dest=n.id%4?n.id+1:0,to=dest?visible.find(x=>x.id===dest):null;if(dest&&!to)continue;const start=xy(n.xyz),end=xy(dest?to.xyz:ground),row=(V.link_windows||[]).find(x=>x.link_id===n.id-1),state=n.preview?'unknown':M.linkState(row),color=C[state],a=start,b=end;
   g.save();g.strokeStyle=color;g.lineWidth=state==='broken'?2:1.6;g.globalAlpha=state==='unknown'?.45:(state==='broken'||state==='degraded')&&motion?.6+.4*Math.sin(phase*8)**2:.85;g.setLineDash([5,7]);g.lineDashOffset=motion&&state!=='broken'?-phase*18:0;
   g.beginPath();g.moveTo(...a);if(state==='broken'){g.lineTo(a[0]+(b[0]-a[0])*.40,a[1]+(b[1]-a[1])*.40);g.moveTo(a[0]+(b[0]-a[0])*.60,a[1]+(b[1]-a[1])*.60);}g.lineTo(...b);g.stroke();g.setLineDash([]);
   if(state==='broken'){g.fillStyle='#0d1820';g.beginPath();g.arc((a[0]+b[0])/2,(a[1]+b[1])/2,11,0,Math.PI*2);g.fill();g.fillStyle=color;g.font='bold 18px Segoe UI';g.textAlign='center';g.fillText('⚠',(a[0]+b[0])/2,(a[1]+b[1])/2+6);g.textAlign='left';}
   else if(state!=='unknown'){const t=motion?(phase*.5+n.id*.19)%1:.55,x=a[0]+(b[0]-a[0])*t,y=a[1]+(b[1]-a[1])*t;g.translate(x,y);g.rotate(Math.atan2(b[1]-a[1],b[0]-a[0]));g.strokeStyle=color;g.lineWidth=2;g.beginPath();g.moveTo(-5,-4);g.lineTo(0,0);g.lineTo(-5,4);g.stroke();}g.restore();
   // Reverse DATA indicates a ground command, not an ACK from normal uplink traffic.
   const reverse=(V.link_windows||[]).find(r=>r.link_id===n.id-1+16);
   if(reverse?.data_attempts>0){const rs=M.linkState(reverse),rc=rs==='good'?'#7dbbff':C[rs],len=Math.max(1,Math.hypot(b[0]-a[0],b[1]-a[1])),ox=-(b[1]-a[1])/len*6,oy=(b[0]-a[0])/len*6;
    g.save();g.strokeStyle=rc;g.lineWidth=2;g.setLineDash([3,7]);g.lineDashOffset=motion?phase*18:0;g.beginPath();g.moveTo(b[0]+ox,b[1]+oy);if(rs==='broken'){g.lineTo(b[0]+(a[0]-b[0])*.4+ox,b[1]+(a[1]-b[1])*.4+oy);g.moveTo(b[0]+(a[0]-b[0])*.6+ox,b[1]+(a[1]-b[1])*.6+oy);}g.lineTo(a[0]+ox,a[1]+oy);g.stroke();g.setLineDash([]);
    const t=motion?(phase*.5+n.id*.19)%1:.5;g.translate(b[0]+(a[0]-b[0])*t+ox,b[1]+(a[1]-b[1])*t+oy);g.rotate(Math.atan2(a[1]-b[1],a[0]-b[0]));g.beginPath();g.moveTo(-6,-4);g.lineTo(0,0);g.lineTo(-6,4);g.stroke();g.restore();}
  }
  for(const n of [...visible].sort((a,b)=>b.xyz[1]-a.xyz[1])){const [x,y]=xy(n.xyz),base=xy([n.xyz[0],n.xyz[1],0]),color=nodeColor(n);if(tilt){g.strokeStyle=color+'66';g.setLineDash([2,4]);g.beginPath();g.moveTo(x,y);g.lineTo(...base);g.stroke();g.setLineDash([]);g.fillStyle='#03121c88';g.beginPath();g.ellipse(base[0],base[1],9,4,0,0,Math.PI*2);g.fill();}
   if(n.id===selected){g.strokeStyle=color+'80';g.fillStyle=color+'18';g.beginPath();g.arc(x,y,23,0,Math.PI*2);g.fill();g.stroke();g.fillStyle='#06131be0';g.fillRect(x+17,y-26,94,20);g.fillStyle=color;g.font='11px Consolas';g.fillText('Z '+fmt(n.xyz[2],1)+' m',x+22,y-12);}
   g.strokeStyle=color;g.fillStyle='#091b28';g.lineWidth=1.6;g.beginPath();if(n.id%4===0){g.moveTo(x,y-9);g.lineTo(x+9,y);g.lineTo(x,y+9);g.lineTo(x-9,y);g.closePath();}else{g.arc(x,y,5,0,Math.PI*2);}g.fill();g.stroke();
   for(const [dx,dy] of [[-7,-5],[7,-5],[-7,5],[7,5]]){g.beginPath();g.moveTo(x,y);g.lineTo(x+dx,y+dy);g.stroke();g.beginPath();g.ellipse(x+dx,y+dy,4,2,0,0,Math.PI*2);g.stroke();}
   g.font='bold 11px Consolas';g.fillStyle='#041019dd';g.fillRect(x-13,y+11,26,16);g.fillStyle=color;g.textAlign='center';g.fillText(String(n.id).padStart(2,'0'),x,y+23);g.textAlign='left';mapTargets.push({x,y,id:n.id});
   if($('showTruth').checked&&n.known){const [tx,ty]=xy(n.truth);g.strokeStyle='#b6c9d37a';g.strokeRect(tx-3,ty-3,6,6);}
  }
  const [gx,gy]=xy(ground);g.fillStyle='#e4f4ff';g.font='23px Segoe UI';g.textAlign='center';g.fillText('★',gx,gy+7);g.font='11px Microsoft YaHei';g.fillText('地面控制站',gx,gy+24);g.textAlign='left';
  if(tilt){const xx=w-43,yy=h-92;g.strokeStyle='#6d99a9';g.beginPath();g.moveTo(xx,yy);g.lineTo(xx,yy-90);g.stroke();g.fillStyle='#adc9d3';g.font='9px Consolas';g.fillText('Z',xx-3,yy-102);for(const [v,dy] of [[0,0],[500,45],[1000,90]]){g.beginPath();g.moveTo(xx-3,yy-dy);g.lineTo(xx+3,yy-dy);g.stroke();g.textAlign='right';g.fillText(v+'m',xx-6,yy-dy+3);}g.textAlign='left';}
  const missing=nodes.filter(n=>!n.preview&&!n.known);if(missing.length){g.fillStyle=C.unknown;g.font='11px Microsoft YaHei';g.fillText('无实收位置：'+missing.map(x=>x.id).join('、'),15,75);}
  g.fillStyle='#9dbdca';g.font='10px Microsoft YaHei';g.fillText(window.mapObservationLabel?.()||'配置预览 · 尚无实板接收位置',15,h-53);
 };
 function frame(now){if(now-lastFrame>50&&tab==='mission'&&!document.hidden){const active=(!history&&S.busy&&S.status==='running')||(history&&replayTimer);if(active){window.drawInstrumentMap();lastFrame=now;}}requestAnimationFrame(frame);}requestAnimationFrame(frame);
 window.syncInstrumentChoices=syncChoices;
})();
