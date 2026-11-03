/* End-to-end acceptance for startup sampling on an idle, connected physical board.
 * Usage: node validation/chart_startup.cjs path/to/a/record/config.json
 * Starts one 60-model-second network run via the actual dashboard button. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const settings = JSON.parse(fs.readFileSync(path.join(root, 'config.json')));
const url = 'http://127.0.0.1:' + settings.http_port;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2])).config;
  const state = await (await fetch(url + '/api/state')).json();
  assert(!state.busy && state.connected && state.ping?.arm_build === '20261102-liveiq1', 'Load firmware and finish any existing run first');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'swarm-chart-'));
  const chrome = spawn(process.env.CHROME_EXE || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    ['--headless=new', '--disable-gpu', '--no-first-run', '--disable-extensions', '--remote-debugging-port=0',
     '--user-data-dir='+profile, '--window-size=1920,1080', url], {windowsHide:true, stdio:'ignore'});
  let ws, session,rows=[];
  try {
    const portFile=path.join(profile,'DevToolsActivePort');
    for(let n=0;!fs.existsSync(portFile)&&n<80;n++)await sleep(150);
    const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0];
    const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
    ws=new WebSocket(tabs.find(t=>t.type==='page'&&t.url.startsWith(url)).webSocketDebuggerUrl);
    await once(ws,'open');
    let id=0;const pending=new Map();
    ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}};
    async function evaluate(expression) {
      const k=++id;const response=new Promise(ok=>pending.set(k,ok));
      ws.send(JSON.stringify({id:k,method:'Runtime.evaluate',params:{expression,awaitPromise:true,returnByValue:true}}));
      const msg=await response;if(msg.error||msg.result.exceptionDetails)throw Error(JSON.stringify(msg));return msg.result.result.value;
    }
    for(let n=0;n<100;n++){if(await evaluate("typeof catalog!=='undefined' && !!catalog && !!document.querySelector('#start') && !!S.connected"))break; await sleep(200);}
    await evaluate(`(async()=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());showTab('evidence');setConfig(${JSON.stringify(config)});$('seconds').value=60;$('telemetry').value='10';await previewConfig();updateButtons();if($('start').disabled)throw Error('Start disabled: '+$('configError').textContent);$('start').click()})()`);
    const start=performance.now();
    const expression=`(()=>{const s=V?.snapshot;if(!s||!s.wall_iq)return null;
      const ids=['cir','cfr','envelope','linkQuality','iqBefore','iqAfter','eye','iqWall'];
      const hashes=ids.map(id=>{const c=$(id);const bytes=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let h=2166136261;for(let j=0;j<bytes.length;j+=4)h=Math.imul((h^bytes[j]^bytes[j+1]<<8^bytes[j+2]<<16),16777619);return h>>>0});
      return {id:S.network_record_id,round:s.round,watch:s.watch_link,focus:Number($('linkSelect').value),gen:window.frameObservation?.()?.generation,counts:s.wall_iq.filter(r=>r[3]).length,taps:$('envelopeValue').textContent,quality:$('linkQualityValue').textContent,eye:$('eyeValue').textContent,wall:$('iqWallValue').textContent,hashes,busy:S.busy}})()`;
    let switched=false;
    for(let n=0;n<550;n++){
      const elapsed=(performance.now()-start)/1000;
      const row=await evaluate(expression);
      if(row && row.id!==state.network_record_id && (!session||row.id===session) && (!rows.length||row.round!==rows.at(-1).round||row.focus!==rows.at(-1).focus)){
        session=row.id;rows.push({...row,wall_s:elapsed});
        if(rows.length<=5||rows.length%10===0)console.log(elapsed.toFixed(2),row.round,row.gen,row.wall,row.taps);
      }
      if(!switched&&elapsed>=32&&rows.length&&row?.busy){await evaluate("(()=>{$('linkSelect').value='14';$('linkSelect').dispatchEvent(new Event('change',{bubbles:true}))})()");switched=true}
      if(session && row?.id===session && !row.busy)break;
      if(!row&&elapsed>25)throw Error('No board plot snapshot: '+await evaluate("JSON.stringify([S.status,S.error,S.events?.slice(-2),S.task,document.querySelector('#configError').textContent])"));
      await sleep(300);
    }
    const early=rows.filter(r=>r.wall_s<30),populated=rows.find(r=>r.counts===16);
    const changes=Array.from({length:8},(_,i)=>new Set(early.map(r=>r.hashes[i])).size);
    const out={record:session,first_s:rows[0]?.wall_s,first_full_wall_s:populated?.wall_s,
      distinct_focus_frames_first30:new Set(early.map(r=>r.gen).filter(Boolean)).size,
      distinct_pixels_first30:changes,rows};
    if(!session)throw Error('No archive');const dest=path.join(root,'app/results',session,'chart_startup.json');
    fs.writeFileSync(dest,JSON.stringify(out,null,2));console.log(dest,JSON.stringify({...out,rows:undefined}));
    assert(rows[0].wall_s<15 && populated?.wall_s<15 && out.distinct_focus_frames_first30>=5);
    assert(changes.every(n=>n>=2));assert(rows.some(r=>r.focus===14&&r.watch===14&&r.gen));
    const final=await(await fetch(url+'/api/state')).json();assert(!final.busy&&!final.error&&final.report?.pass,'Run did not pass');
  } finally {
    ws?.close();const exited=chrome.exitCode!==null?Promise.resolve():once(chrome,'exit');chrome.kill();
    await exited;
    if(path.dirname(path.resolve(profile))===path.resolve(os.tmpdir()) && /^swarm-chart-[a-zA-Z0-9]+$/.test(path.basename(profile))){
      try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:4,retryDelay:200});}catch(e){console.warn('Profile cleanup:',e.message);}
    }
  }
}
main().catch(e=>{console.error(e);process.exitCode=1});
