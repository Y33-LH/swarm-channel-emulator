const {chromium}=require('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','ui_check');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launchPersistentContext(path.join(out,'browser_profile'),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,viewport:{width:1920,height:1080}});
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:8873/',{waitUntil:'networkidle'});
 await page.screenshot({path:path.join(out,'dashboard.png'),fullPage:true});
 const state=await page.evaluate(()=>({status:document.getElementById('badge').textContent,width:document.documentElement.scrollWidth,viewport:window.innerWidth,buttons:[...document.querySelectorAll('button')].map(b=>b.textContent),data:typeof current!=='undefined'?current:null}));
 if(errors.length)throw Error(errors.join('\n'));if(state.width>state.viewport)throw Error('Horizontal page overflow');
 if(state.data?.status==='complete'){
  await page.locator('[data-n="12"]').click();
  if(await page.locator('#selected').innerText()!=='12')throw Error('Node selection failed');
  for(const id of ['audio','video']){
   await page.locator('#'+id).evaluate(async e=>{e.load();await new Promise((resolve,reject)=>{e.onloadedmetadata=resolve;e.onerror=()=>reject(Error('Media decoding failed'));setTimeout(()=>reject(Error('Media metadata timeout')),10000)});});
  }
  state.media=await page.evaluate(()=>({audio:document.getElementById('audio').duration,video:document.getElementById('video').duration}));
 }
 fs.writeFileSync(path.join(out,'browser_check.json'),JSON.stringify({pass:true,errors,state},null,2));await browser.close();console.log('UI_BROWSER_PASS '+out);
})().catch(e=>{console.error(e);process.exit(1)});
