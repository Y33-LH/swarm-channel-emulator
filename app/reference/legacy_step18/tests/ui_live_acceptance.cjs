const {chromium}=require('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');const root=path.resolve(__dirname,'..'),out=path.join(root,'results','ui_live_'+Date.now());fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,viewport:{width:1920,height:1080}});
 const page=await browser.newPage(),errors=[],shots=new Set();page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:8873/',{waitUntil:'networkidle'});await page.locator('#connect').click();
 await page.waitForFunction(()=>document.getElementById('message').textContent.includes('已确认真实板卡'),null,{timeout:10000});
 await page.locator('#duration').selectOption('900');await page.locator('#ideal').selectOption('0');await page.locator('#start').click();
 const start=Date.now();let final;
 while(Date.now()-start<480000){
  const response=await page.request.get('http://127.0.0.1:8873/api/state'),s=await response.json();
  if(s.status==='error')throw Error(s.error);if(s.status==='stopped')throw Error('Unexpected stop');
  const t=s.snapshot?.round/10||0;
  for(const at of [60,350,400,680,720,900])if(t>=at&&!shots.has(at)){await page.screenshot({path:path.join(out,'at_'+at+'s.png'),fullPage:true});shots.add(at);console.log('UI_LIVE_PROGRESS sim_s='+t+' elapsed_s='+((Date.now()-start)/1000).toFixed(1));}
  if(s.status==='complete'){final=s;break}await page.waitForTimeout(400);
 }
 if(!final)throw Error('Live run timeout');if(errors.length)throw Error(errors.join('\n'));
 await page.waitForFunction(()=>document.getElementById('audio').getAttribute('src')!==null);
 for(const id of ['audio','video'])await page.locator('#'+id).evaluate(async e=>{e.load();await new Promise((ok,bad)=>{e.onloadedmetadata=ok;e.onerror=()=>bad(Error('Decode failed'));setTimeout(()=>bad(Error('Metadata timeout')),10000)})});
 await page.locator('[data-n="12"]').click();if(await page.locator('#selected').innerText()!=='12')throw Error('Node selection failed');
 await page.locator('#details details').click();
 const media=await page.evaluate(()=>({audio:document.getElementById('audio').duration,video:document.getElementById('video').duration,parameter:document.getElementById('parameter-detail').innerText}));
 if(!media.parameter.includes('链路距离')||media.video<=0||media.audio<=0)throw Error('Missing live details/media');
 await page.screenshot({path:path.join(out,'complete.png'),fullPage:true});
 fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,scope:'live board via UI buttons, three environments, actual received media decoding',errors,media,result_path:final.result_path,report:final.report},null,2));
 await browser.close();console.log('UI_LIVE_HARDWARE_PASS evidence='+out);
})().catch(e=>{console.error(e);process.exit(1)});
