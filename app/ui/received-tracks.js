/* Positions originate only in ground-received heartbeat fields, never truth. */
(function(root){
 'use strict';
 function append(tracks,snapshots,afterRound,toRound,now){
  for(const s of snapshots||[]){
   if(s.round<=afterRound||s.round>toRound)continue;
   for(const v of s.nodes||[]){
    if(!v[9])continue;
    const old=tracks.get(v[0]);if(old?.updates===v[9])continue;
    const xyz=v.slice(4,7).map(x=>x/1000),trail=old?.trail||[];
    trail.push(xyz);if(trail.length>180)trail.shift();
    tracks.set(v[0],{first:old?.first||xyz,from:old?.to||xyz,to:xyz,trail,
     updates:v[9],duration:Math.max(200,Math.min(9000,old?now-old.at:600)),at:now});
   }
  }
 }
 function displacement(tracks){return [...tracks.values()].map(v=>Math.hypot(...v.to.map((x,i)=>x-v.first[i])));}
 const api={append,displacement};root.ReceivedTracks=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
