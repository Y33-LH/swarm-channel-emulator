/* Pure display calculations. No random points and no receiver-estimate claims. */
(function(root){
 const fs=8e6;
 function taps(c){
  if(!c)return [];
  if(Array.isArray(c.taps)&&c.taps.length)return c.taps;
  return [{gain:c.gain0,delay_samples:c.delay_samples,phase_radians:c.phase_radians||0,cfo_hz:c.cfo_hz},
          {gain:c.gain1,delay_samples:c.delay_samples+c.echo_delay_samples,phase_radians:c.echo_phase_radians||0,cfo_hz:c.echo_cfo_hz}];
 }
 function statistics(c){
  const list=taps(c);if(!list.length||list.some(t=>![t.gain,t.delay_samples,t.phase_radians].every(Number.isFinite)))return null;
  // Combine coincident delays coherently at this exact frame start.
  const groups=new Map(),rate=c.sample_rate_hz||fs;
  for(const t of list){const v=groups.get(t.delay_samples)||[0,0];v[0]+=t.gain*Math.cos(t.phase_radians);v[1]+=t.gain*Math.sin(t.phase_radians);groups.set(t.delay_samples,v);}
  const first=Math.min(...groups.keys()),bins=[...groups].sort((a,b)=>a[0]-b[0]).map(([d,z])=>({delay:(d-first)/rate,power:Math.hypot(...z)**2}));
  const powers=bins.map(b=>b.power<1e-24?0:b.power),total=powers.reduce((a,b)=>a+b,0),delays=bins.map(b=>b.delay);
  if(!total)return {powers,delays,total,rms:null,mean:null,attenuation:null,bandwidth:null};
  const mean=powers.reduce((s,p,i)=>s+p*delays[i],0)/total,rms=Math.sqrt(powers.reduce((s,p,i)=>s+p*(delays[i]-mean)**2,0)/total);
  return {powers,delays,total,mean,rms,attenuation:-10*Math.log10(total),bandwidth:rms>0?1/(5*rms):null};
 }
 function response(c,f){const rate=c.sample_rate_hz||fs;let re=0,im=0;for(const t of taps(c)){const p=t.phase_radians-2*Math.PI*f*t.delay_samples/rate;re+=t.gain*Math.cos(p);im+=t.gain*Math.sin(p);}return Math.hypot(re,im);}
 function windowQuality(s,previous,id){
  const v=s?.links?.[id];if(!v)return null;
  const p=previous?.run_id===s.run_id&&previous.round<s.round?previous.links?.[id]:null,d=v.map((n,i)=>n-(p?.[i]||0));
  return {time:s.round/10,capture:d[0]>0?d[1]/d[0]:null,hop:d[19]>0?d[3]/d[19]:null};
 }
 function linkState(row){if(!row||!row.active||!row.data_attempts)return 'unknown';if(row.acked===0)return 'broken';if(row.hop_success<.95)return 'degraded';return 'good';}
 const api={fs,taps,statistics,response,windowQuality,linkState};root.ChannelMath=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
