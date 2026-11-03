/* Node markers are driven by DENSE MODEL-TRUTH track (1 model-second samples, linear
 * interpolation) so motion is continuous; RECEIVED heartbeats remain visible as
 * evidence dots. Contract: truth between received samples must be labeled. */
(()=>{
 const E=id=>document.getElementById(id),tracks=new Map(),shownPositions=new Map();let identity='',lastRound=-1,cam=null,angle=-.32,zoom=1,drag=null,terrainCache=null,cacheKey='';
 // ── 模型时钟与真值轨迹窗口 ──
 const truth={samples:null,times:null,t0:0,end:0,clockT:0,clockAt:0,rate:0,fetching:false,runtimeKey:'',lastFetch:0};
 const visualClock=new MotionClock();
 function anchor(s){const t=s.round/10,now=performance.now();visualClock.observe(t,now);truth.rate=visualClock.rate;truth.clockT=t;truth.clockAt=now;}
 function modelNow(){const running=history?!!replayTimer:!!(S.busy&&S.status==='running'&&!pollFailed);return visualClock.read(performance.now(),running);}
 async function ensureTruth(){const mt=modelNow();
  if(truth.fetching||(!S.snapshot&&!history))return;
  if(truth.samples&&mt>=truth.t0-.5&&mt<truth.end-1.5)return;
  if(performance.now()-truth.lastFetch<300)return;truth.lastFetch=performance.now();
  truth.fetching=true;const requestedIdentity=identity,requestedRuntime=truth.runtimeKey;
  try{const r=await(await fetch(`/api/truth?t=${mt.toFixed(2)}&span=10${history?'&record='+encodeURIComponent(history.id):''}`)).json();
   if(r&&r.samples&&r.samples.length>1&&identity===requestedIdentity&&truth.runtimeKey===requestedRuntime){truth.samples=r.samples;truth.t0=r.t0;truth.times=r.times||r.samples.map((_,i)=>Math.min(r.t0+i,r.duration_s>0?r.duration_s:r.confirmed_model_s+3));truth.end=r.end_s??truth.times[truth.times.length-1];}}catch(e){}
  truth.fetching=false;}
 function truthPos(id){const a=truth.samples;if(!a||a.length<2)return null;
  const mt=modelNow(),ts=truth.times;if(mt<truth.t0||mt>truth.end)return null;let k=0;while(k<a.length-2&&ts[k+1]<mt)k++;
  const f=Math.min(1,Math.max(0,(mt-ts[k])/Math.max(.000001,ts[k+1]-ts[k]))),p=a[k][id-1],q=a[k+1][id-1];
  return p.map((v,i)=>v+(q[i]-v)*f);}
 const reduced=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)').matches:false;
 const colors={good:'#359eff',degraded:'#ff465e',broken:'#ff4d6a',unknown:'#8fa5b8'};
 // 天气粒子覆盖层（雨/雪/雾的视觉提示；不参与传播计算，传播参数由场景预设决定）
 window.drawWorkflowWeather=(g,w,h,weather,t)=>{
  if(!weather)return;g.save();g.fillStyle=weather===1?'#bfd1d71a':'#99bad808';g.fillRect(0,0,w,h);
  if(weather>=2){g.strokeStyle=weather>=5?'#dfedff44':'#9ec7e840';g.lineWidth=1;const count=[0,0,24,38,60,24,38,60][weather];for(let i=0;i<count;i++){const x=(i*137+23)%w,y=(i*79+47+t*5)%h;g.beginPath();if(weather>=5)g.arc(x,y,1.2,0,Math.PI*2);else{g.moveTo(x,y);g.lineTo(x-3,y+8);}g.stroke();}}g.restore();
 };
 function sceneNow(){return V.snapshot?.scene_ms!=null?V.snapshot.scene_ms/1000:(V.snapshot?.round||0)/10;}
 function env(){const cfg=V.snapshot?.config||preview?.config||catalog?.defaults||{};return cfg.environment||[1,3,4][Math.min(2,Math.floor(sceneNow()/300))];}
 const height=(x,y,e)=>window.terrainModel.elevation(x,y,(V.snapshot?.config||preview?.config||{}).environment??e,sceneNow());
 const live=()=>window.causalPresentation?.active?['running','queued'].includes(window.causalPresentation.view?.phase):['running','paused'].includes(S.status);
 const active=()=>!pollFailed&&((!history&&S.busy&&live())||(!!history&&!!replayTimer));
 function sample(){const s=V.snapshot,key=window.actionContext?.record_id||history?.id||S.network_record_id||'preview';if(key!==identity){identity=key;lastRound=-1;tracks.clear();shownPositions.clear();cam=null;truth.samples=null;truth.clockAt=0;truth.rate=0;visualClock.reset();}
  if(!s||s.round===lastRound)return;if(s.round<lastRound){tracks.clear();shownPositions.clear();truth.samples=null;visualClock.reset();lastRound=-1;}
  const runtimeKey=JSON.stringify(s.scene_runtime||null);if(runtimeKey!==truth.runtimeKey){truth.runtimeKey=runtimeKey;truth.samples=null;}
  anchor(s);
  ReceivedTracks.append(tracks,history?.snapshots||S.snapshots||[s],lastRound,s.round,performance.now());
  lastRound=s.round;
 }
 function display(n){const t=tracks.get(n.id);if(!t||!active()||reduced)return n.xyz;let f=Math.max(0,Math.min(1,(performance.now()-t.at)/t.duration));return t.from.map((v,i)=>v+(t.to[i]-v)*f);}// 实收位置回退仅线性插值；不逐帧减速到零。
 const label=document.createElement('p');label.className='terrain-note';label.textContent='原创程序地形 · 拖动旋转 / 滚轮缩放 · 航标连续位置 = 模型真值轨迹（1 通信秒采样插值，已按契约标注）· 实心圆点 = 地面实收心跳（验收依据）';E('map').parentElement.after(label);
 const reset=document.createElement('button');reset.id='terrainReset';reset.textContent='重置视角';document.querySelector('.mapoptions').append(reset);reset.onclick=()=>{cam=null;zoom=1;angle=-.32;drawMap();};
 E('map').closest('.mapwrap').querySelector('.mapstamp small').textContent='程序场景示意 · 高度投影2.6倍 · 不用于真实避障';
 const canvas=E('map');canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,angle};});canvas.addEventListener('pointermove',e=>{if(!drag)return;angle=drag.angle+(e.clientX-drag.x)/250;drawMap();});window.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.65,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));drawMap();},{passive:false});
 window.drawInstrumentMap=()=>{
  if(tab!=='mission')return;sample();ensureTruth();const c=canvasSize(canvas);if(!c)return;const {g,w,h}=c,e=env(),cfg=V.snapshot?.config||preview?.config||{},tiltEl=E('mapPerspective'),tilt=tiltEl?tiltEl.value==='3d':true;
  const nodes=Array.from({length:16},(_,i)=>nodeData(i+1)).filter(n=>n&&(n.preview||n.known));
  const posOf=n=>{const p=truthPos(n.id);if(p){shownPositions.set(n.id,p);return p;}return n.preview?n.xyz:(shownPositions.get(n.id)||display(n));};
  // 相机：跟随系数必须小，否则编队永远居中、节点在屏幕上纹丝不动，看着像摆拍。
  // 收紧到编队尺寸 +600 m（原 +1800 让每米只占很少像素），并留出缓慢回中，
  // 这样节点相对画面真实穿行，长时间运行也不会飞出视野。
  const full=E('mapView').value==='full',orbitView=E('mapView').value==='orbit';
  const points=nodes.map(posOf);points.push(window.terrainModel.ground(cfg,e,sceneNow()));
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const targetX=(full||orbitView)?5000:(Math.min(...xs)+Math.max(...xs))/2,targetY=(full||orbitView)?5000:(Math.min(...ys)+Math.max(...ys))/2;
  if(!cam||cam.full!==full||cam.orbitView!==orbitView)cam={full,orbitView,cx:targetX,cy:targetY};
  else {cam.cx+=(targetX-cam.cx)*.06;cam.cy+=(targetY-cam.cy)*.06;}
  cam.px=Math.round(cam.cx/5)*5;cam.py=Math.round(cam.cy/5)*5;
  const a=tilt?angle:0,project=p=>{const x=p[0]-cam.px,y=p[1]-cam.py;return [x*Math.cos(a)-y*Math.sin(a),-(x*Math.sin(a)+y*Math.cos(a))*(tilt?.53:1)-(tilt?(p[2]||0)*3.8:0)];};
  const fittingPoints=points.concat(nodes.map(n=>{const p=posOf(n);return [p[0],p[1],height(p[0],p[1],e)];}));
  const fit=(orbitView?[[0,0,cfg.altitude_m||400],[10000,0,cfg.altitude_m||400],[0,10000,cfg.altitude_m||400],[10000,10000,cfg.altitude_m||400],points[points.length-1]]:full?[[0,0,0],[10000,0,0],[0,10000,0],[10000,10000,0]]:fittingPoints).map(project);
  const ux=fit.map(p=>p[0]),uy=fit.map(p=>p[1]),loX=Math.min(...ux),hiX=Math.max(...ux),loY=Math.min(...uy),hiY=Math.max(...uy);
  const scale=Math.min((w-(orbitView?40:110))/Math.max(300,hiX-loX),(h-(orbitView?70:150))/Math.max(300,hiY-loY))*zoom;
  const offsetX=(loX+hiX)/2,offsetY=(loY+hiY)/2;
  cam.span=Math.max(300,hiX-loX,hiY-loY);cam.scale=scale;
  const xy=p=>{const q=project(p);return [w/2+(q[0]-offsetX)*scale,h*.49+(q[1]-offsetY)*scale];};
  const key=[w,h,devicePixelRatio,e,cfg.environment===0?Math.min(320,Math.max(300,sceneNow()))+Math.min(620,Math.max(600,sceneNow())):0,tilt,angle,zoom,cam.px,cam.py,cam.span,scale,offsetY,E('basemapMode').value].join(':');
  if(key!==cacheKey){cacheKey=key;terrainCache=document.createElement('canvas');terrainCache.width=canvas.width;terrainCache.height=canvas.height;const q=terrainCache.getContext('2d');q.scale(devicePixelRatio,devicePixelRatio);
   const bg=q.createLinearGradient(0,0,0,h);bg.addColorStop(0,'#0a2432');bg.addColorStop(1,'#040f19');q.fillStyle=bg;q.fillRect(0,0,w,h);
   const grid=E('basemapMode').value==='grid',faces=[];
   // 高程分带色带（仅按程序地形高度着色，不代表真实地物）：低地青蓝 → 草甸绿 → 黄绿 → 黄褐 → 岩灰 → 积雪白
   const ramp=[[0,12,64,84],[.2,15,114,102],[.38,48,158,92],[.52,128,186,76],[.66,200,166,90],[.79,156,126,104],[.9,214,228,232],[1,246,251,253]];
   const rampColor=t=>{t=Math.max(0,Math.min(1,t));for(let i=1;i<ramp.length;i++){if(t<=ramp[i][0]){const a=ramp[i-1],b=ramp[i],f=(t-a[0])/((b[0]-a[0])||1);return [a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f,a[3]+(b[3]-a[3])*f];}}return ramp[ramp.length-1].slice(1);};
   // 地形必须铺满整个画布：可见世界宽度 = w/scale、可见世界高度（立体压缩后）= h/(scale*(tilt?.53:1))。
   // 原先固定取 cam.span*1.65 的方形区域，宽屏下竖向适配决定 scale，地形只剩中间一个方块、两侧大片留白。
   // 现在取编队视野与画布可见范围的最大值，横向多出的空间显示更多地貌；网格数随边长自适应，块感不增。
   const coverX=(w+90)/scale,coverY=(h*1.3)/(scale*(tilt?.53:1))+Math.abs(offsetY)*3;
   const span=Math.max(cam.span*1.65,coverX,coverY),n=Math.max(34,Math.min(80,Math.round(34*span/(cam.span*1.65)))),step=span/n;let zmin=1e9,zmax=-1e9;
   for(let i=0;i<n;i++)for(let j=0;j<n;j++){const x=cam.px-span/2+i*step,y=cam.py-span/2+j*step;const a=[x,y,height(x,y,e)],b=[x+step,y,height(x+step,y,e)],c=[x+step,y+step,height(x+step,y+step,e)],d=[x,y+step,height(x,y+step,e)];for(const f of [[a,b,c],[a,c,d]]){faces.push(f);for(const p of f){zmin=Math.min(zmin,p[2]);zmax=Math.max(zmax,p[2]);}}}
   faces.sort((a,b)=>xy(a[0])[1]-xy(b[0])[1]);
   // 定向光照：光源在西北上方，按面法线明暗，坡度越陡对比越强，立体感来自明暗而非单色平涂
   const zspan=Math.max(1,zmax-zmin),L=[-.5,-.72,.62];
   for(const f of faces){const z=f.reduce((s,p)=>s+p[2],0)/3,t=(z-zmin)/zspan;
    const e1=[f[1][0]-f[0][0],f[1][1]-f[0][1],(f[1][2]-f[0][2])*6],e2=[f[2][0]-f[0][0],f[2][1]-f[0][1],(f[2][2]-f[0][2])*6];
    let nx=e1[1]*e2[2]-e1[2]*e2[1],ny=e1[2]*e2[0]-e1[0]*e2[2],nz=e1[0]*e2[1]-e1[1]*e2[0];const nl=Math.hypot(nx,ny,nz)||1;nx/=nl;ny/=nl;nz=Math.abs(nz/nl);
    const lit=Math.max(0,nx*L[0]+ny*L[1]+nz*L[2]),bright=grid?1:.42+.62*lit+.14*t;
    const c0=grid?[18,38,50]:rampColor(t),r=Math.min(255,c0[0]*bright),gg=Math.min(255,c0[1]*bright),bb=Math.min(255,c0[2]*bright);
    q.beginPath();f.forEach((p,i)=>i?q.lineTo(...xy(grid?[p[0],p[1],0]:p)):q.moveTo(...xy(grid?[p[0],p[1],0]:p)));q.closePath();q.fillStyle=`rgb(${r|0} ${gg|0} ${bb|0})`;q.fill();q.strokeStyle=grid?'#284855':'rgba(5,16,22,.30)';q.lineWidth=.4;q.stroke();}
   if(!grid&&[2,3,4].includes(e)){for(let i=0;i<(e===4?120:40);i++){const x=5000+Math.sin(i*17.3)*4800,y=5000+Math.cos(i*9.1)*4800,z=height(x,y,e),s=45,H=e===4?35+(i%7)*12:16;const base=[[x,y,z],[x+s,y,z],[x+s,y+s,z],[x,y+s,z]];for(const [ix,jx] of [[0,1],[1,2]]){q.beginPath();[base[ix],base[jx],[...base[jx].slice(0,2),z+H],[...base[ix].slice(0,2),z+H]].forEach((p,k)=>k?q.lineTo(...xy(p)):q.moveTo(...xy(p)));q.closePath();q.fillStyle=ix?'#2a4f63':'#1b3a4c';q.fill();}q.beginPath();base.forEach((p,k)=>k?q.lineTo(...xy([p[0],p[1],z+H])):q.moveTo(...xy([p[0],p[1],z+H])));q.closePath();q.fillStyle='#5d8296';q.fill();}}
  }
  g.drawImage(terrainCache,0,0,w,h);const motion=active()&&!reduced,t=motion?performance.now()/1000:sceneNow();
  window.drawWorkflowWeather?.(g,w,h,cfg.weather||0,t);mapTargets=[];const ground=window.terrainModel.ground(cfg,e,sceneNow());
  // Display projection only: reserve a clear band above the station for the airborne layer.
  const pixels=points.slice(0,-1).map(xy), station=xy(ground);
  const axis=i=>pixels.length?pixels.map(v=>v[i]):[0];
  const xx=axis(0),yy=axis(1),xmin=Math.min(...xx),ymin=Math.min(...yy);
  const dx=Math.max(...xx)-xmin,dy=Math.max(...yy)-ymin;
  const ceiling=24,bottom=Math.max(ceiling+1,Math.min(h-65,Math.max(25,station[1]))-62);
  const spread=tilt?Math.max(.01,Math.min(1.65,(w-60)/Math.max(1,dx),(bottom-ceiling)/Math.max(1,dy))):1;
  const left=Math.max(25,Math.min(w-30-spread*dx,xmin+(1-spread)*dx/2));
  const top=Math.max(ceiling,Math.min(bottom-spread*dy,ymin-h*.13+(1-spread)*dy/2));
  const airborne=p=>{const [x,y]=xy(p);return tilt?[left+(x-xmin)*spread,top+(y-ymin)*spread]:[x,y];};
  const issues=V.snapshot?.recovery?.issues||[],brokenSet=new Set(issues.filter(x=>x.node).map(x=>x.node));
  for(const n of nodes){const dst=n.id%4?n.id+1:0,to=dst?nodes.find(x=>x.id===dst):null;if(dst&&!to)continue;const a=airborne(posOf(n)),b=dst?airborne(posOf(to)):station;const row=(V.link_windows||[]).find(x=>x.link_id===n.id-1);const state=issues.some(x=>x.link===n.id-1)?'broken':n.preview?'unknown':window.ChannelMath?.linkState?.(row)||(!row?'unknown':row.hop_success===0?'broken':row.hop_success<.95?'degraded':'good');const color=state==='good'?'#2df5c6':colors[state]||colors.unknown;g.strokeStyle=color;g.globalAlpha=state==='broken'&&motion?.55+.45*Math.sin(t*5)**2:.75;g.lineWidth=2.3;g.setLineDash([7,5]);g.lineDashOffset=motion?-t*16:0;g.beginPath();g.moveTo(...a);if(state==='broken'){g.lineTo(a[0]+(b[0]-a[0])*.43,a[1]+(b[1]-a[1])*.43);g.moveTo(a[0]+(b[0]-a[0])*.57,a[1]+(b[1]-a[1])*.57);}g.lineTo(...b);g.stroke();g.setLineDash([]);g.globalAlpha=1;g.fillStyle=color;if(state==='broken'){g.font='16px sans-serif';g.fillText('⚠',(a[0]+b[0])/2-7,(a[1]+b[1])/2);}else if(state!=='unknown'){const f=motion?(t*.5+n.id*.13)%1:.5;g.beginPath();g.arc(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,3,0,7);g.fill();}}
  for(const n of nodes){const p=posOf(n),[x,y]=airborne(p),base=xy([p[0],p[1],height(p[0],p[1],e)]),col=n.preview||!n.known?colors.unknown:n.fresh&&!brokenSet.has(n.id)?colors.good:colors.degraded;
   if(brokenSet.has(n.id)){const pulse=motion?.5+.5*Math.sin(t*6):.8;g.save();g.strokeStyle='#ff4d6a';g.globalAlpha=.3+.5*pulse;g.lineWidth=2.2;g.beginPath();g.arc(x,y,13+5*pulse,0,7);g.stroke();g.globalAlpha=.12+.1*pulse;g.fillStyle='#ff4d6a';g.beginPath();g.arc(x,y,13+5*pulse,0,7);g.fill();g.restore();}
   g.strokeStyle=col+'bc';g.setLineDash([3,3]);g.beginPath();g.moveTo(x,y);g.lineTo(...base);g.stroke();g.setLineDash([]);g.fillStyle='#02101699';g.beginPath();g.ellipse(...base,7,3,0,0,7);g.fill();g.strokeStyle=col;g.lineWidth=1.6;g.fillStyle=col;g.beginPath();g.moveTo(x,y-8);g.lineTo(x+6,y+6);g.lineTo(x,y+3);g.lineTo(x-6,y+6);g.closePath();g.fill();if(n.id===selected){g.beginPath();g.arc(x,y,17,0,7);g.stroke();}mapTargets.push({x,y,id:n.id});}
  g.save();g.font='bold 12px Consolas, monospace';g.lineJoin='round';g.lineWidth=3;g.strokeStyle='#071525';g.fillStyle='#f0f7ff';g.textAlign='center';
  for(const point of mapTargets){const id=String(point.id).padStart(2,'0');g.strokeText(id,point.x,point.y+21);g.fillText(id,point.x,point.y+21);}
  const picked=nodes.find(n=>n.id===selected);
  if(picked){const info=`节点 ${String(selected).padStart(2,'0')} · 高度 ${picked.xyz[2].toFixed(1)} m`;g.textAlign='right';g.strokeText(info,w-12,17);g.fillText(info,w-12,17);}
  g.restore();
  if(E('showTruth').checked&&V.snapshot){for(const n of nodes){if(!n.truth)continue;const [tx,ty]=airborne(n.truth);g.strokeStyle='#c4d1df';g.setLineDash([3,3]);g.strokeRect(tx-8,ty-8,16,16);g.setLineDash([]);}g.fillStyle='#c4d1df';g.fillText('虚线方框：模型真值（不是接收位置）',18,45);}
  const groundScreen=xy(ground),gx=Math.max(22,Math.min(w-80,groundScreen[0])),gy=Math.max(25,Math.min(h-65,groundScreen[1]));const groundOutside=gx!==groundScreen[0]||gy!==groundScreen[1];g.fillStyle='#e7f4ff';g.font='22px sans-serif';g.fillText('★',gx-10,gy);g.font='11px sans-serif';g.fillText(groundOutside?'地面站（画外）':'地面站',gx+12,gy);
  E('mapExtent').textContent=`${catalog?.environment.find(x=>x.id===e)?.name||'场景'} · ${tilt?'立体地形 · 高度与编队间距视觉放大':'俯视'} · ${full?'全域固定相机':'绕站视域 · 编队与地面站同屏'}`;
  // Net displacement between received heartbeats is not accumulated flight distance.
  const moves=ReceivedTracks.displacement(tracks);
  if(moves.length){const avg=moves.reduce((a,b)=>a+b,0)/moves.length,mx=Math.max(...moves);
   g.fillStyle='#7fe9dd';g.font='11px sans-serif';
   g.fillText(`实收位置净位移：平均 ${avg.toFixed(0)} m / 最大 ${mx.toFixed(0)} m（距本记录首个心跳，三维）`,18,h-38);}
  g.fillStyle='#bed5db';g.font='11px sans-serif';g.fillText(window.mapObservationLabel?.()||'',18,h-22);
  canvas.dataset.motionState=(!active()?'暂停 / 非运行':performance.now()-truth.clockAt>3000?'位置更新延迟 · 已停止预测':'连续模型轨迹');
  canvas.setAttribute('aria-label',canvas.dataset.motionState+'；航标为模型轨迹，圆点为实收位置');
  label.textContent='原创程序地形 · 拖动旋转 / 滚轮缩放 · 航标 = 连续模型轨迹；圆点 = 地面实收心跳（验收依据）'+(performance.now()-truth.clockAt>3000&&active()?' · 位置更新延迟，已停止预测':'');
  window.terrainDiagnostics={record:identity,round:lastRound,environment:e,tracks:[...tracks].map(([id,v])=>({id,points:v.trail.length,first:v.trail[0],last:v.to})),camera:{...cam},projection:mapTargets.map(p=>({...p})),active:active(),truth_track:!!truth.samples,truth_t0:truth.t0,clock_rate:truth.rate,display:'continuous model-truth track (labeled); received heartbeats shown as dots'};
 };
 let last=0;function tick(t){if(t-last>40&&tab==='mission'&&!document.hidden){window.drawInstrumentMap();last=t;}requestAnimationFrame(tick);}requestAnimationFrame(tick);
})();
