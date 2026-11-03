/* One frame identity for channel readback, receiver samples and frame counters.
 * Missing/other-link records stay missing. Window counters are a separate view. */
(function(root){
 'use strict';
 function identity(o){return o?[o.record_id,o.run_id,o.config_id,o.channel_id,o.link_id,o.model_ms,o.generation].join(':'):null;}
 function select(o,s,id){
  return o&&s&&o.run_id===s.run_id&&o.config_id===s.config_id&&o.link_id===Number(id)&&
   (s.protocol<21||o.channel_id===s.channel_id)&&o.model_ms<=s.round*100&&o.waveform==='DATA'?o:null;
 }
 function interval(errors,bits){
  if(!Number.isInteger(errors)||!Number.isInteger(bits)||bits<=0||errors<0||errors>bits)return null;
  // Wilson 95% binomial interval. Not a guarantee for correlated bit errors.
  const z=1.959963984540054,p=errors/bits,d=1+z*z/bits;
  const c=(p+z*z/(2*bits))/d,r=z*Math.sqrt(p*(1-p)/bits+z*z/(4*bits*bits))/d;
  return [Math.max(0,c-r),Math.min(1,c+r)];
 }
 const api={identity,select,interval};
 if(typeof module!=='undefined')module.exports=api;
 if(root)root.Observation=api;
})(typeof window==='undefined'?null:window);
