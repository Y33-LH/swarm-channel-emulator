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

  const state = await (await fetch(url + '/api/state')).json();
  assert(!state.busy && state.connected && state.ping?.arm_build === '20261102-returnpcm1', 'Load firmware and finish any existing run first');
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
      ws.send(JSON.stringify({id:k,method:'Runtime.evaluate',params:{expression,userGesture:true,awaitPromise:true,returnByValue:true}}));
      const msg=await response;if(msg.error||msg.result.exceptionDetails)throw Error(JSON.stringify(msg));return msg.result.result.value;
    }
    for(let n=0;n<100;n++){if(await evaluate("typeof catalog!=='undefined' && !!catalog && !!document.querySelector('#start') && !!S.connected"))break; await sleep(200);}
    const js=async expr=>evaluate(expr);
    const ready=async expr=>{for(let i=0;i<200;i++){if(await js(expr))return;await sleep(200);}throw Error('Timeout: '+expr+' '+await js("document.getElementById('replayNarration').textContent"));};

    const pane=async (name)=>js("Array.from(document.querySelectorAll('.p2-right [role=tab]')).find(b=>b.textContent==="+JSON.stringify(name)+").click()");
    const qa={};const save=()=>fs.writeFileSync(path.join(root,'logs','mission_live_check.json'),JSON.stringify(qa,null,2));
    await js("document.querySelectorAll('dialog[open]').forEach(d=>d.close());showTab('mission')");
    qa.nav=[];for(const id of ['evidence','mission','history']){await js("showTab('"+id+"')");await sleep(400);qa.nav.push(await js("(()=>{const b=document.querySelector('header nav .active');return [b.textContent,tab,getComputedStyle(b).fontSize,getComputedStyle(b).backgroundColor]})()"));};
    console.log('actual nav',qa.nav);assert.equal(new Set(qa.nav.map(v=>v[3])).size,3);assert(qa.nav.every(v=>parseFloat(v[2])>=14));await js("showTab('mission')");
    await pane('AI问答');qa.aiControls=await js("Array.from(document.querySelector('.assistantPanel').querySelectorAll('input,textarea,button,details')).filter(e=>e.getClientRects().length).map(e=>e.id)");assert.deepEqual(qa.aiControls,['question','ask']);
    await pane('建议');qa.idleAdvice=await js("$('advice').innerText.trim()");assert.equal(qa.idleAdvice,'');save();console.log('NAV, AI CONTROLS, CLEAN IDLE ADVICE',qa);
    await js("window.audioTest={prompts:[],pcm:0,overlaps:0,active:0};const origPlay=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.includes('/cues/')){this.addEventListener('playing',()=>{audioTest.prompts.push(this.src.split('/').pop());if(++audioTest.active>1)audioTest.overlaps++},{once:true});this.addEventListener('ended',()=>audioTest.active--,{once:true})}return origPlay.apply(this,arguments)};const origStart=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(){if(this.buffer?.length===1920)audioTest.pcm++;return origStart.apply(this,arguments)};if(!$('soundToggle').textContent.endsWith('开'))$('soundToggle').click()");
    await ready("$('soundToggle').textContent.endsWith('开')");
    await js("[...document.querySelectorAll('button')].find(b=>b.textContent==='稳定绕站演示').click();");
    await js("(async()=>{await previewConfig();updateButtons();if($('start').disabled)throw Error('Start disabled');$('start').click()})()");
    const deadline=Date.now()+230000;let chosen=false,slow=false,fast=false,asked=false,receipt1='',receipt2='',positions=new Set(),healthy=0,advice='',lastRound=-1,final=null;
    const issue=async value=>{await pane('文字指令');await js("$('recoveryText').value='节点 1 心跳间隔 "+value+" 毫秒';$('recoveryParse').click()");await ready("!$('recoveryExecute').disabled");await js("$('recoveryExecute').click()");};
    while(Date.now()<deadline){
      const r=await js("({run:S.network_record_id,busy:S.busy,round:V.snapshot?.round||0,pass:S.report?.pass,error:S.error||'',out:$('recoveryReceipt').textContent,issues:V.snapshot?.recovery?.issues||[],advice:$('advice').textContent,pos:document.querySelector('.node-motion')?.dataset.position,clock:$('sceneClockStatus').textContent,audio:audioTest,events:(S.mission_timeline||[]).map(e=>e.kind),received:V.snapshot?.heartbeat_audio?.length||0,ai:$('answer').textContent,plan:$('recoveryPlan').textContent})");final=r;
      if(r.run && r.run!==state.network_record_id){session=r.run;if(!r.busy){if(r.pass||r.error||r.round>=600)break;}}
      if(session && r.round>0){
        if(!chosen){await js("const t=document.querySelector('.return-topology select');t.value=9;t.dispatchEvent(new Event('change'))");chosen=true;}
        if(r.pos)positions.add(r.pos);
        if(!r.issues.length&&!r.advice&&r.round>=30)healthy++;
        if(r.round>=35&&!slow){await issue(10000);slow=true;}
        if(r.out.includes('10000'))receipt1=r.out;
        if(r.issues.some(i=>i.kind==='heartbeat'&&i.node===1)&&r.advice.includes('节点 1')&&!fast){advice=r.advice;await pane('AI问答');await js("$('question').value='节点1为什么心跳过期？';$('ask').click()");asked=true;await issue(1000);fast=true;}
        if(fast && /1000 毫秒/.test(r.out))receipt2=r.out;
        if(r.round>=lastRound+80){lastRound=r.round;console.log('BOARD',r.round,r.clock,r.audio,r.received,r.plan,r.out);}
      }
      await sleep(220);
    }
    qa.record=session;qa.measured={healthy,advice,receipt1,receipt2,uniquePositions:positions.size,asked,final};save();
    assert(final?.pass,'experiment did not pass: '+JSON.stringify(final));assert(positions.size>=5&&final.received===16);assert(healthy&&advice&&receipt1&&receipt2);
    assert(Number(final.clock.match(/绕站 ([\d.]+)/)?.[1])>=1);
    await pane('事件');await sleep(1700);
    qa.journal=await js("({box:$('events').innerText,rows:[...$('events').querySelectorAll('.journal-row')].map(r=>({h:r.clientHeight,s:r.scrollHeight})),audio:audioTest,full:S.mission_timeline})");save();
    assert(qa.journal.rows.length>0&&qa.journal.rows.every(r=>r.s<=r.h+1));assert(['start','fault','recover','end'].every(k=>qa.journal.full.some(row=>row.kind===k)));
    assert(qa.journal.audio.pcm>0 && qa.journal.audio.overlaps===0);assert(['start','fault','recover','end'].every(k=>qa.journal.audio.prompts.includes(k+'.wav')));
    await pane('AI问答');qa.answer=await js("$('answer').innerText");assert(qa.answer.includes('1000') && !qa.answer.includes('位置新鲜'));save();
    const archived=await (await fetch(url+'/api/record?id='+session)).json();assert.deepEqual(archived.mission_timeline,qa.journal.full);
    await js("Array.from(document.querySelectorAll('.p2-left [role=tab]')).find(b=>b.textContent==='回放记录').click();$('replayNode').value='9';$('replayNode').dispatchEvent(new Event('change'));$('replayLoad').click()");
    await ready("!$('replayPlayPause').disabled");await js("$('replayPlayPause').click()");await ready("!$('nodeAudio').paused && $('nodeAudio').currentTime>.2");
    const story=await (await fetch(url+'/api/node_story?record='+session+'&node=9&audio=1')).json();assert(story.narration.length>0 && story.narration.every((r,i)=>r.end>r.t&&(!i||r.t-story.narration[i-1].end>=.24)));
    await js("Array.from(document.querySelectorAll('.p2-left [role=tab]')).find(b=>b.textContent==='真实回传').click()");assert(await js("$('nodeAudio').paused"));
    assert(await js("!!document.querySelector('.return-topology .node-motion') && !document.querySelector('.returned-files, #receivedAudio, #receivedVideo')"));
    qa.replay={phrases:story.narration.length,sequential:true};qa.passed=true;save();console.log('MISSION_UI_BOARD_PASS',session);
  } finally {
    ws?.close();const exited=chrome.exitCode!==null?Promise.resolve():once(chrome,'exit');chrome.kill();
    await exited;
    if(path.dirname(path.resolve(profile))===path.resolve(os.tmpdir()) && /^swarm-chart-[a-zA-Z0-9]+$/.test(path.basename(profile))){
      try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:4,retryDelay:200});}catch(e){console.warn('Profile cleanup:',e.message);}
    }
  }
}
main().catch(e=>{console.error(e);process.exitCode=1});

