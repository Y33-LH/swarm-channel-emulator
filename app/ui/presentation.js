/* Lightweight presentation only. No graphics/audio changes experiment data. */
(() => {
 const reduced=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)').matches:false;
 if(!sessionStorage.getItem('workbench-intro')){
  const intro=document.createElement('div');intro.className='startup';intro.setAttribute('role','status');
  intro.innerHTML='<div class="startup-orbit">◈</div><small>CHANNEL • MODEM • NETWORK</small><h2>蜂群信道实验平台</h2><p>让通信条件可控制，让业务影响可观察。</p><button>跳过启动画面 →</button>';
  const close=()=>{intro.remove();sessionStorage.setItem('workbench-intro','1');};
  intro.querySelector('button').onclick=close;document.body.append(intro);setTimeout(close,reduced?200:1400);
 }
 // A single cue channel shares the speakers with received media and recorded narration.
 const toggle=document.createElement('button');toggle.id='soundToggle';
 document.querySelector('.topactions').prepend(toggle);
 let enabled=true,ctx=null,voices=[];
 try{enabled=localStorage.getItem('swarm-cues')!=='off';}catch{}
 function label(){
  toggle.textContent=!enabled?'声效：关':ctx?.state==='running'?'声效：开':'声效：待启用';
  toggle.title='实时回传的心跳、故障和恢复提示音';toggle.setAttribute('aria-pressed',String(enabled));
 }
 async function unlock(){
  if(!enabled)return;
  try{ctx=ctx||new AudioContext();if(ctx.state!=='running')await ctx.resume();}catch{}label();
 }
 function stop(){for(const o of voices)try{o.stop();}catch{}voices=[];}
 let speaking=false,queue=[],activePrompt=null,interrupted=null;
 function quiet(){if(activePrompt){activePrompt.pause();activePrompt=null;}speaking=false;queue=[];interrupted=null;stop();}
 function announce(rows){
  if(!enabled||ctx?.state!=='running'||document.hidden)return;
  for(const kind of new Set(rows.map(r=>r.kind))){
   if(!['start','fault','recover','end'].includes(kind))continue;
   if(!queue.includes(kind))queue.push(kind);
  }
  if(speaking)return;
  function next(){
   if(!enabled||document.hidden){quiet();return;}
   if(!queue.length){
    activePrompt=null;speaking=false;
    if(interrupted?.isConnected&&interrupted.getClientRects().length)interrupted.play().catch(()=>{});
    interrupted=null;return;
   }
   speaking=true;stop();
   for(const el of document.querySelectorAll('audio,video'))if(!el.paused){interrupted=el;el.pause();}
   const player=new Audio('cues/'+queue.shift()+'.wav');activePrompt=player;
   let done=false;const finish=()=>{if(done||activePrompt!==player)return;done=true;next();};
   player.onended=finish;player.onerror=finish;player.play().catch(finish);
  }
  next();
 }
 function packet(hex){
  if(!enabled||ctx?.state!=='running'||speaking||document.hidden||!/^([0-9a-f]{2}){48}$/i.test(hex)||[...document.querySelectorAll('audio,video')].some(m=>!m.paused&&!m.ended))return;
  const bytes=hex.match(/../g).map(h=>parseInt(h,16)),samples=[];
  for(const b of bytes)samples.push(((b&15)-8)/12,((b>>4)-8)/12);
  // Browsers accept 48 kHz. Linear interpolation preserves the packet's original 2400 Hz time base.
  const ratio=20,buf=ctx.createBuffer(1,samples.length*ratio,48000),out=buf.getChannelData(0);
  for(let i=0;i<out.length;i++){const j=Math.floor(i/ratio),f=i%ratio/ratio;out[i]=(samples[j]*(1-f)+(samples[j+1]??samples[j])*f)*.44;}
  stop();const source=ctx.createBufferSource();source.buffer=buf;voices.push(source);source.connect(ctx.destination);
  source.onended=()=>{voices=voices.filter(v=>v!==source);source.disconnect();};source.start();
 }
 function pauseHidden(){stop();if(document.hidden)quiet();document.querySelectorAll('audio,video').forEach(m=>{if(!m.paused&&(document.hidden||!m.getClientRects().length))m.pause();});}
 document.addEventListener('play',e=>{
  if(!(e.target instanceof HTMLMediaElement))return;
  if(speaking)quiet();stop();document.querySelectorAll('audio,video').forEach(m=>{if(m!==e.target&&!m.paused)m.pause();});
 },true);
 document.addEventListener('visibilitychange',pauseHidden);
 for(const event of ['click','keydown'])document.addEventListener(event,e=>{if(e.isTrusted&&e.target!==toggle&&enabled&&ctx?.state!=='running')unlock();},true);
 toggle.onclick=()=>{enabled=!(enabled&&ctx?.state==='running');if(enabled)unlock();else quiet();
  try{localStorage.setItem('swarm-cues',enabled?'on':'off');}catch{}label();};
 window.returnSound={announce,packet,stop,pauseHidden};label();
})();
