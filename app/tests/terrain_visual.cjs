/* Presentation tests use labelled preview coordinates, never hardware evidence. */
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{const b=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true}),p=await b.newPage({viewport:{width:1600,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(String(e)));const out=path.resolve(__dirname,'../results/terrain_visual');fs.mkdirSync(out,{recursive:true});try{
 await p.goto('http://127.0.0.1:8887/');await p.waitForFunction(()=>typeof catalog!=='undefined'&&catalog);await p.waitForTimeout(1500);
 // Freeze the browser clock/polls. Test only rendering with explicit preview data.
 await p.clock.install();const captures=[];
 for(const [env,weather] of [[1,0],[4,4],[5,7]]){await p.evaluate(([environment,weather])=>{history=null;V={};preview={config:{...catalog.defaults,environment,weather},nodes:Array.from({length:16},(_,i)=>({id:i+1,xyz_m:[4000+(i%4)*650,4000+Math.floor(i/4)*650,400]}))};showTab('mission');document.getElementById('terrainReset').click();drawMap();},[env,weather]);await p.locator('#map').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(out,`preview_${env}_${weather}.png`)});const data=await p.locator('#map').evaluate(c=>c.toDataURL());captures.push(data);}
 assert.equal(new Set(captures).size,3);assert.deepEqual(errors,[]);
 for(const size of [{width:1366,height:768},{width:1920,height:1080}]){await p.setViewportSize(size);await p.evaluate(()=>drawMap());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.screenshot({path:path.join(out,`layout_${size.width}.png`)});}
 fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,scope:'labelled preview rendering only',distinct_scenes:3,errors},null,2));console.log('TERRAIN_VISUAL_PASS');
 }finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
