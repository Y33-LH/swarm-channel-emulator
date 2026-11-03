const assert=require('assert'),Clock=require('../ui/motion-clock.js');
const c=new Clock();c.observe(0,0);let prev=0,min=Infinity,max=0;
for(let ms=20;ms<=15000;ms+=20){if(ms%1000===0)c.observe(ms/1000,ms);const t=c.read(ms,true),d=t-prev;assert(d>0,'unexpected pause at '+ms);min=Math.min(min,d);max=Math.max(max,d);prev=t;}
const paused=c.read(15020,false);assert.equal(c.read(16020,false),paused);
c.read(18020,true);const stale=c.read(18100,true);assert.equal(c.read(19000,true),stale);
c.observe(19,19000);assert(c.read(19020,true)>stale);
console.log('PASS continuous 15s, pause, stale telemetry freeze, resume; per-frame dt range',min,max);
