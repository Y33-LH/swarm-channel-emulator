const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','intervention_abort');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1366,height:768}}),errors=[],url='http://127.0.0.1:8881';
 page.on('pageerror',e=>errors.push(String(e)));
 const state=async()=>await(await page.request.get(url+'/api/causal/state')).json();
 const wait=async p=>{const until=Date.now()+60000;while(Date.now()<until){const d=await state();if(p(d))return d;await page.waitForTimeout(200);}throw Error('state timeout')};
 try{
  await page.goto(url+'/#causal');await page.waitForTimeout(1500);
  if(!(await state()).connected){await page.locator('#connect').click();await wait(d=>d.connected&&!d.busy);}
  await page.waitForFunction(()=>!document.getElementById('cxStart').disabled);
  await page.locator('#cxStart').click();
  let d=await wait(d=>d.experiment?.phase==='waiting');
  const first=d.experiment.id;
  // Invalid parameter must not mutate ARM or release the model-time pause.
  const rejected=await page.request.post(url+'/api/causal/action',{data:{id:first,kind:'change',gain_permille:1001,sigma:0,window_s:10}});
  assert(!rejected.ok());assert.equal((await state()).experiment.phase,'waiting');
  await page.locator('#cxStop').click();await wait(d=>!d.busy&&d.experiment?.phase==='stopped');
  const records=await(await page.request.get(url+'/api/causal/records')).json();
  assert.equal(records.find(r=>r.id===first).complete,false);
  const badReplay=await page.request.post(url+'/api/causal/reproduce',{data:{id:first}});assert(!badReplay.ok());
  await page.waitForFunction(()=>!document.getElementById('cxStart').disabled);
  await page.locator('#cxStart').click();
  d=await wait(d=>d.experiment?.id!==first&&d.experiment?.phase==='waiting');
  assert(d.experiment.view.nodes.every(n=>n.fresh));
  const second=d.experiment.id;
  assert.equal(d.experiment.events.length,0);
  await page.locator('button[data-tab="mission"]').click();
  assert(!await page.locator('#networkIntervention').isVisible());
  await page.locator('button[data-tab="evidence"]').click();
  assert(await page.locator('#networkIntervention').isVisible());
  assert(!await page.locator('#runDock .run-tools').isVisible());
  await page.screenshot({path:path.join(out,'laptop-waiting.png'),fullPage:true});
  await page.locator('#cxStop').click();await wait(d=>!d.busy&&d.experiment?.phase==='stopped');
  assert.deepEqual(errors,[]);
  const raw=fs.readFileSync(path.join(root,'results',second,'uart.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(raw.at(-1).command,'NETSTOP');
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,first,second,errors,stopped_firmware:true,partial_not_accepted:true,invalid_input_no_mutation:true,restart_clean_baseline:true},null,2));
  console.log('INTERVENTION_ABORT_RESTART_PASS',first,second);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
