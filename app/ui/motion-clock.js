/* Continuous display clock; never changes the ARM clock or received evidence.
   Slews toward telemetry instead of resetting at each packet; stops after 3 s of silence. */
(function(root){
 class MotionClock {
  constructor(){this.reset();}
  reset(){this.started=false;this.rate=1;this.current=0;this.observed=0;this.at=0;this.last=0;}
  observe(t,now){
   if(!this.started||t<this.observed){this.started=true;this.current=t;this.observed=t;this.at=now;this.last=now;this.rate=1;return;}
   const dt=(now-this.at)/1000,delta=t-this.observed;
   if(dt>=.25&&delta>0){const measured=delta/dt;if(measured>.05&&measured<200)this.rate=.8*this.rate+.2*measured;}
   this.observed=t;this.at=now;
  }
  read(now,running){
   if(!this.started)return 0;
   const dt=Math.max(0,Math.min(.25,(now-this.last)/1000));this.last=now;
   if(!running||now-this.at>3000)return this.current;
   const target=this.observed+Math.max(0,now-this.at)/1000*this.rate;
   const correction=Math.max(-this.rate*.5,Math.min(this.rate*.5,(target-this.current)*.4));
   this.current=Math.min(this.observed+3,this.current+dt*(this.rate+correction));return this.current;
  }
 }
 root.MotionClock=MotionClock;
 if(typeof module==='object'&&module.exports)module.exports=MotionClock;
})(typeof window==='object'?window:globalThis);
