/* Recorded motion only: never synthesize extra turns or reuse unrelated metrics. */
(()=>{
 const E=id=>document.getElementById(id),bar=document.createElement('div');bar.className='orbit-movie-controls';document.querySelector('.mapheading').after(bar);
 const preset=document.createElement('button');preset.textContent='稳定绕站演示';preset.onclick=()=>{const c={"schema":1,"environment":1,"weather":0,"formation":7,"spacing_m":1050,"altitude_m":400,"center_x_m":5000,"center_y_m":5000,"speed_mmps":20000,"heading_deg":0,"reference_snr_cdb":3400,"faults":0,"jitter_percent":100,"carrier_mhz":2400,"external_node":0,"reserved":16,"channel":{"schema":1,"mode":1,"fading":2,"sample_rate_khz":8000,"tap_count":8,"rician_k_cdb":1500,"scatter_millihz":2000,"loss_cdb":1200,"cfo_hz":0,"phase_cdeg":0,"delay_ns":0,"delay_scale_percent":100,"echo_decay_cdb":300,"reserved0":0,"reserved1":0,"reserved2":0,"tap0_power_cdb":0,"tap0_delay_ns":0,"tap0_phase_cdeg":0,"tap0_cfo_hz":0,"tap1_power_cdb":-300,"tap1_delay_ns":125,"tap1_phase_cdeg":0,"tap1_cfo_hz":0,"tap2_power_cdb":-600,"tap2_delay_ns":250,"tap2_phase_cdeg":0,"tap2_cfo_hz":0,"tap3_power_cdb":-900,"tap3_delay_ns":375,"tap3_phase_cdeg":0,"tap3_cfo_hz":0,"tap4_power_cdb":-1200,"tap4_delay_ns":500,"tap4_phase_cdeg":0,"tap4_cfo_hz":0,"tap5_power_cdb":-1500,"tap5_delay_ns":625,"tap5_phase_cdeg":0,"tap5_cfo_hz":0,"tap6_power_cdb":-1800,"tap6_delay_ns":750,"tap6_phase_cdeg":0,"tap6_cfo_hz":0,"tap7_power_cdb":-2100,"tap7_delay_ns":875,"tap7_phase_cdeg":0,"tap7_cfo_hz":0}};c.speed_mmps=20000;c.formation=7;c.spacing_m=1050;c.reserved=48;c.center_x_m=c.center_y_m=5000;setConfig(c);E('speed').dataset.manual='1';E('spacing_m').dataset.manual='1';E('seconds').value='75';E('telemetry').value='10';previewConfig();toast('已选旷野晴天、34 dB 稳定基线；20 m/s、1050 m间距、约3.23 km轨道、48倍飞行场景快进，75 通信秒约 3.5 圈。通信仍逐帧经过FPGA。');};bar.append(preset);
 const compatible=c=>c.environment===5&&c.weather===0&&c.formation===0&&!c.faults&&!c.external_node;
 window.mountainDrillRequested=req=>compatible(req.config)&&!Number(req.ideal);
 function mountainDemo(){
  const c=readConfig();Object.assign(c,{environment:5,weather:0,formation:0,spacing_m:MOUNTAIN_X_SPACING_M,altitude_m:800,center_x_m:5000,center_y_m:5000,speed_mmps:20000,heading_deg:0,reference_snr_cdb:4500,faults:0,jitter_percent:100,carrier_mhz:2400,external_node:0,reserved:48});
  c.channel={"schema":1,"mode":1,"fading":2,"sample_rate_khz":8000,"tap_count":8,"rician_k_cdb":1500,"scatter_millihz":2000,"loss_cdb":1200,"cfo_hz":0,"phase_cdeg":0,"delay_ns":0,"delay_scale_percent":100,"echo_decay_cdb":300,"reserved0":1,"reserved1":0,"reserved2":0,"tap0_power_cdb":0,"tap0_delay_ns":0,"tap0_phase_cdeg":0,"tap0_cfo_hz":0,"tap1_power_cdb":-300,"tap1_delay_ns":125,"tap1_phase_cdeg":0,"tap1_cfo_hz":0,"tap2_power_cdb":-600,"tap2_delay_ns":250,"tap2_phase_cdeg":0,"tap2_cfo_hz":0,"tap3_power_cdb":-900,"tap3_delay_ns":375,"tap3_phase_cdeg":0,"tap3_cfo_hz":0,"tap4_power_cdb":-1200,"tap4_delay_ns":500,"tap4_phase_cdeg":0,"tap4_cfo_hz":0,"tap5_power_cdb":-1500,"tap5_delay_ns":625,"tap5_phase_cdeg":0,"tap5_cfo_hz":0,"tap6_power_cdb":-1800,"tap6_delay_ns":750,"tap6_phase_cdeg":0,"tap6_cfo_hz":0,"tap7_power_cdb":-2100,"tap7_delay_ns":875,"tap7_phase_cdeg":0,"tap7_cfo_hz":0};setConfig(c);E('seconds').value='60';E('telemetry').value='10';E('seed').value='20261009';E('ideal').value='0';previewConfig();
 }
 const mountain=document.createElement('button');mountain.textContent='最终演示 · 山地晴天 X 形';mountain.onclick=()=>{mountainDemo();syncRailFromConfig();toast('已选最终演示。运行满 60 秒后，观测节点 9 心跳，按建议发送文字指令恢复。');};bar.prepend(mountain);
 E('start').addEventListener('click',()=>{const c=readConfig();if(c.environment===5&&c.channel?.reserved0&&c.altitude_m<=400&&c.reference_snr_cdb<=3400&&confirm(`当前低空山地配置可能同时遮挡四条回地链路。切换到山地晴天 X 形演示（间距 ${MOUNTAIN_X_SPACING_M} 米、高度 800 米、45 dB）再开始？取消则按当前参数运行。`))mountainDemo();},true);
 const clocks=document.createElement('strong');clocks.id='sceneClockStatus';bar.append(clocks);
 E('sceneScale').addEventListener('change',()=>previewConfig());
 let turnRun='',turnRound=-1,angle=null,rotation=0;
 function turns(s){
  const run=(history?.id||S.network_record_id||'')+(history?':history':':live');
  if(run!==turnRun||s.round<turnRound){turnRun=run;turnRound=-1;angle=null;rotation=0;}
  if(s.round>turnRound)for(const sample of history?.snapshots||S.snapshots||[s]){
   if(sample.round<=turnRound||sample.round>s.round||sample.nodes?.length!==16)continue;
   const x=sample.nodes.reduce((a,n)=>a+n[1]/16000,0)-5000,y=sample.nodes.reduce((a,n)=>a+n[2]/16000,0)-5000;
   const next=Math.atan2(y,x);
   if(Math.hypot(x,y)>20&&angle!==null)rotation+=Math.atan2(Math.sin(next-angle),Math.cos(next-angle));angle=next;turnRound=sample.round;
  }
  return (Math.abs(rotation)/(2*Math.PI)).toFixed(2);
 }
 setInterval(()=>{const s=V.snapshot;if(!s){clocks.textContent='飞行场景时间 — · 网络仿真用时 —';return;}const scale=s.scene_time_scale||1,ct=s.round/10,st=s.scene_ms!=null?s.scene_ms/1000:ct;clocks.textContent=`飞行场景时间 ${st.toFixed(1)} s · 网络仿真用时 ${ct.toFixed(1)} s · ${scale}×场景扫描 · 编队绕站 ${turns(s)} 圈`;clocks.title='运动、距离、信道使用场景时间；TDMA、心跳周期、重传、业务时延使用通信时间。不是整网同倍率加速。';},100);
})();
