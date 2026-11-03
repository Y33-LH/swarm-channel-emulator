const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','product_ui_hardware_'+Date.now());fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8878';let browser,page,errors=[];
(async()=>{browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
page=await browser.newPage({viewport:{width:1920,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
const state=async()=>(await page.request.get(base+'/api/state')).json();
async function wait(pred,ms=180000){const end=Date.now()+ms;while(Date.now()<end){const s=await state();if(s.status==='error')throw Error(s.error);if(pred(s))return s;await page.waitForTimeout(300);}throw Error('UI hardware wait timeout');}
async function post(p,d={}){const r=await page.request.post(base+p,{data:d});return {status:r.status(),data:await r.json()};}
await page.goto(base);await page.waitForFunction(()=>document.getElementById('configHash').textContent.includes('校验通过'));
await page.locator('#program').click();await wait(s=>s.task==='firmware'&&s.status==='complete'&&s.connected&&!s.busy);
console.log('UI_PROGRAM_PASS');
// Malformed input must be rejected before touching FPGA registers.
let r=await post('/api/start',{config:{formation:7,center_x_m:500,spacing_m:1100}});assert(r.status>=400);
r=await post('/api/command',{confirm:false,action:{target:2,opcode:5,value:2000,ttl_ms:10000}});assert(r.status>=400);
await page.locator('[data-tab="evidence"]').click();await page.locator('#openLab').click();const lab=[];
for(const preset of ['ideal','echo','noise']){const previous=(await state()).lab?.id;await page.locator('#labPreset').selectOption(preset);await page.locator('#labRun').click();let s=await wait(s=>s.task==='lab'&&s.lab?.id!==previous&&!s.busy&&s.status==='complete');
 if(preset!=='noise')assert(s.lab.match);else assert(s.lab.match||(!s.lab.received_ok&&!s.lab.rx_hex));
 lab.push({preset,id:s.lab.id,match:s.lab.match,evm:s.lab.payload_evm_percent});}
await page.locator('#labBatch').click();const batch=await wait(s=>s.task==='labnoise'&&!s.busy&&s.lab_batch?.finished);assert(batch.lab_batch.target_met&&batch.lab_batch.delivered>=9);
await page.screenshot({path:path.join(out,'phy.png'),fullPage:true});await page.locator('#closeLab').click();
assert((await page.locator('#sourceLabel').innerText()).includes('单帧实测'));
assert((await page.locator('#channelDetails').innerText()).includes('单链路文字收发'));
await page.locator('[data-tab="mission"]').click();await page.locator('#resetConfig').click();await page.waitForTimeout(500);await page.locator('#start').click();
await wait(s=>s.task==='network'&&s.status==='running'&&s.snapshot?.round>=3400);
const owningRun=(await state()).network_record_id;
const conflict=await post('/api/program',{port:'COM4'});assert.equal(conflict.status,409);assert.equal((await state()).network_record_id,owningRun);
await page.locator('#pause').click();let paused=await wait(s=>s.status==='paused');const round=paused.snapshot.round;
await page.waitForTimeout(1200);assert.equal((await state()).snapshot.round,round);
await page.locator('#nodeSelect').selectOption('2');await page.locator('#controlDetails summary').click();await page.locator('#commandOp').selectOption('1');await page.locator('#sendCommand').click();assert(await page.locator('#confirmDialog').isVisible());assert.equal((await state()).commands.length,0);
await page.locator('#confirmCommand').click();await page.waitForTimeout(300);assert.equal((await state()).commands.length,0,'A host-queued paused command must not be shown as executed');
await page.screenshot({path:path.join(out,'paused_command.png'),fullPage:true});
await page.locator('#resume').click();const expired=await wait(s=>s.commands?.some(c=>c[1]===2&&c[4]===4));
assert(expired.snapshot.round>=3700,'An outage-time query must expire, not invent success');
await page.locator('#sendCommand').click();await page.locator('#confirmCommand').click();
const controlled=await wait(s=>s.commands?.some(c=>c[0]===2&&c[1]===2&&c[4]===2));
await page.locator('#stop').click();await wait(s=>s.status==='stopped'&&!s.busy);await page.locator('#connect').click();await wait(s=>s.task==='connect'&&!s.busy&&s.connected);
console.log('UI_PAUSE_COMMAND_STOP_RECONNECT_PASS');
// Three fresh runs through the visible UI, with no replay and no pause excluded.
const runs=[];
for(let i=0;i<3;i++){const previous=(await state()).network_record_id;await page.locator('#resetConfig').click();await page.waitForTimeout(500);await page.locator('#start').click();let s=await wait(s=>s.task==='network'&&s.network_record_id!==previous&&s.status==='complete'&&!s.busy);
 assert(s.report.pass&&s.report.all_media_complete);assert(s.report.performance_gates.complete_within_120s);assert(s.report.performance_gates.delivery_above_99pct);
 runs.push({id:s.network_record_id,report:s.report});console.log('UI_FULL_RUN_PASS',i+1,s.report.wall_total_seconds,s.report.final.delivered+'/'+s.report.final.generated);
 await page.waitForTimeout(1100);assert.equal(await page.locator('#start').isDisabled(),false);await page.screenshot({path:path.join(out,`run${i+1}.png`),fullPage:true});}
assert.equal(new Set(runs.map(x=>x.id)).size,3,'Three distinct board experiments required');
const id=runs[2].id;await page.waitForTimeout(500);
for(const media of ['audio','video']){const src=await page.locator('#'+media).getAttribute('src');assert(src.includes(id));const response=await page.request.get(base+src);assert(response.ok());}
// Independent capacity task must not relabel the last received media.
await page.locator('[data-tab="evidence"]').click();await page.locator('.secondary-details').evaluate(e=>e.open=true);await page.locator('#capacityRun').click();await wait(s=>s.task==='capacity'&&s.status==='running');await page.locator('#capacityStop').click();await wait(s=>s.status==='stopped'&&!s.busy);
await page.locator('[data-tab="mission"]').click();assert((await page.locator('#audio').getAttribute('src')).includes(id));
await page.locator('[data-tab="history"]').click();await page.locator('#refreshRecords').click();await page.waitForTimeout(700);await page.locator(`[data-record="${id}"]`).click();await page.waitForFunction(()=>document.getElementById('sourceLabel').textContent.includes('历史'));
assert(await page.locator('#start').isDisabled());assert(await page.locator('#sendCommand').isDisabled());await page.locator('#replayRange').fill('17');await page.locator('#replayRange').dispatchEvent('input');await page.waitForTimeout(500);
await page.screenshot({path:path.join(out,'fault_replay.png'),fullPage:true});await page.locator('#returnLive').click();
await page.locator('[data-tab="history"]').click();for(const type of ['report','csv','export']){r=await (await page.request.get(`${base}/api/${type}?id=${id}&save=1`)).json();assert(r.ok&&r.path.startsWith(root));}
const compare=await (await page.request.get(`${base}/api/compare?left=${runs[0].id}&right=${runs[1].id}`)).json();assert(compare.controlled_single_setting_comparison);
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,source:'rendered_browser_actions_and_physical_board',ui_runs:runs.map(x=>({id:x.id,wall_s:x.report.wall_total_seconds,delivery:x.report.final.delivered/x.report.final.generated})),image_hashes:runs[0].report.image_hashes,lab,paused_round:round,expired_then_successful:controlled.commands,concurrent_program_rejected:true,stop_reconnect:true,exports:true,history_read_only:true,errors},null,2));
console.log('PRODUCT_UI_HARDWARE_PASS',out);await browser.close();
})().catch(async e=>{console.error(e);if(page){try{await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors},null,2));}catch{}}if(browser)await browser.close();process.exit(1)});
