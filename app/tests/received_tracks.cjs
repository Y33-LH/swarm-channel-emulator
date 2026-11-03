const assert=require('assert/strict'),r=require('../ui/received-tracks.js');
const row=(x,z,updates)=>[1,999999,999999,999999,x,0,z,0,0,updates];
const s=[{round:0,nodes:[row(0,0,0)]},{round:10,nodes:[row(1000,0,1)]},{round:20,nodes:[row(4000,4000,2)]},{round:30,nodes:[row(4000,4000,2)]},{round:40,nodes:[row(9000,0,3)]}];
const t=new Map();r.append(t,s,-1,30,100);
assert.equal(t.get(1).trail.length,2);assert.equal(r.displacement(t)[0],5);
assert.deepEqual(t.get(1).first,[1,0,0]);assert.deepEqual(t.get(1).to,[4,0,4]);
// A backwards seek rebuilds from the prefix and cannot borrow future positions.
t.clear();r.append(t,s,-1,10,200);assert.equal(r.displacement(t)[0],0);
r.append(t,s,10,30,300);assert.equal(r.displacement(t)[0],5);
r.append(t,s,30,40,400);assert.equal(r.displacement(t)[0],8);
console.log('RECEIVED_TRACKS_PASS: record origin, 3D displacement, duplicate heartbeats, rewind, no future/truth leak');
