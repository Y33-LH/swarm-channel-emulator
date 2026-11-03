// A rendered UI action -> asynchronous local inference -> confirmed network
// command -> PL endpoint execution -> received heartbeat. No fabricated states.
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','assistant_ui_'+Date.now());fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8878';
(async()=>{const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const state=async()=>(await page.request.get(base+'/api/state')).json();
 async function wait(pred,ms=90000){const until=Date.now()+ms;while(Date.now()<until){const s=await state();if(s.error&&s.status==='error')throw Error(s.error);if(pred(s))return s;await page.waitForTimeout(250);}throw Error('Live assistant deadline');}
 try{
  await page.goto(base);await page.waitForFunction(()=>document.getElementById('configHash').textContent.includes('校验通过'));
  await page.locator('#connect').click();await wait(s=>s.connected&&!s.busy);
  await page.locator('[data-tab="mission"]').click();await page.locator('#resetConfig').click();await page.waitForTimeout(700);
  await page.locator('#start').click();let initial=await wait(s=>s.task==='network'&&s.busy&&s.snapshot?.round>=200);
  await page.locator('.assistantPanel details').evaluate(e=>e.open=true);
  await page.locator('#question').fill('让9号高度设为450米');const askedAt=Date.now();await page.locator('#ask').click();
  await page.waitForFunction(()=>document.querySelector('#answer button'));
  const answered=await state(),answerSeconds=(Date.now()-askedAt)/1000;assert(answered.busy&&answered.task==='network','Answer must arrive during the active experiment');
  assert(answerSeconds<30,'A useful live answer must arrive within 30 wall seconds');
  // A fast answer may precede the next 20-model-second UART snapshot. Requiring
  // answer_round > before_round would incorrectly reject that faster response.
  // A slow-inference unit test separately proves the worker does not own UART.
  const progressed=await wait(s=>s.busy&&s.task==='network'&&s.snapshot?.round>initial.snapshot.round,15000);
  assert((await page.locator('#assistantStatus').innerText()).includes('本地模型参与'));
  assert.equal(answered.commands.length,0,'Inference must not execute a command');
  const answerBefore=await page.locator('#answer').innerText();
  await page.locator('#answer button').filter({hasText:'节点 9'}).click();assert(await page.locator('#confirmDialog').isVisible());
  assert.equal((await state()).commands.length,0);await page.locator('#confirmCommand').click();
  const executed=await wait(s=>s.commands?.some(c=>c[1]===9&&c[2]===5&&c[3]===450&&c[4]===2)&&s.snapshot?.nodes[8][6]===450000);
  await page.locator('#nodeSelect').selectOption('9');assert((await page.locator('#nodeDetails').innerText()).includes('FPGA 硬件端点'));
  await page.locator('#question').fill('小九现在在哪里？');await page.locator('#ask').click();
  await page.waitForFunction(()=>document.getElementById('answer').textContent.includes('节点 09')&&!document.getElementById('answer').textContent.includes('正在分析'));
  const answerAfter=await page.locator('#answer').innerText();assert.notEqual(answerAfter,answerBefore);assert(answerAfter.includes('450'));
  await page.screenshot({path:path.join(out,'actual_pl_height.png'),fullPage:true});
  const imageHashes=JSON.parse(fs.readFileSync(path.join(root,'release.json')));const crypto=require('crypto');
  const hashes=Object.fromEntries(['bit','elf','init'].map(k=>[k,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,imageHashes[k]))).digest('hex')]));
  assert.deepEqual(errors,[]);await page.locator('#stop').click();await wait(s=>!s.busy);
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,source:'browser_local_model_and_physical_PL_node9',record:executed.network_record_id,image_hashes:hashes,release_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex'),before_round:initial.snapshot.round,answer_round:answered.snapshot.round,progress_round:progressed.snapshot.round,answer_seconds:answerSeconds,executed_round:executed.snapshot.round,commands:executed.commands,received_node9:executed.snapshot.nodes[8],answerBefore,answerAfter,errors},null,2));
  console.log('ASSISTANT_UI_HARDWARE_PASS',out);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors},null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
