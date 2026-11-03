const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={window:{},document:{getElementById:()=>({value:'0'})},V:{},S:{},history:null};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('app/ui/observation.js','utf8'),ctx);ctx.Observation=ctx.window.Observation;
const source=fs.readFileSync('app/ui/params-rail.js','utf8').split('const CH_ENV')[0];
vm.runInContext(source+'})();',ctx);
const frames=JSON.parse(fs.readFileSync('app/results/iq_wall_before/frontend_frames.json','utf8'));
for(const frame of frames){ctx.V=frame;assert(ctx.window.frameObservation());assert.equal(ctx.window.frameObservation().received.length,frame.phy_live.received.length);assert(ctx.window.observedChannel(0));assert.equal(ctx.window.receiverPoints().equalized.length,frame.phy_live.equalized.length);}
ctx.V={snapshot:{...frames[89].snapshot,run_id:-1},phy_live:frames[89].phy_live,phy_links:frames[89].phy_links};assert.equal(ctx.window.frameObservation(),null);
console.log('FRONTEND_CONTINUITY_PASS 90 batches; context change clears stale frames');
