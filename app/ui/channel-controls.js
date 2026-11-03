/* Channel contract 1. No decorative sliders: every enabled field is serialized,
 * validated on both hosts, read back from ARM, and bound to the record hash. */
(() => {
 'use strict';
 const E=id=>document.getElementById(id),rail=document.querySelector('.channel-primary'),f=E('channelControls');
 const defaults={schema:1,mode:1,fading:2,sample_rate_khz:8000,tap_count:0,rician_k_cdb:1500,scatter_millihz:2000,loss_cdb:1200,cfo_hz:0,phase_cdeg:0,delay_ns:0,delay_scale_percent:100,echo_decay_cdb:300,reserved0:0,reserved1:0,reserved2:0};
 for(let i=0;i<8;i++)Object.assign(defaults,{[`tap${i}_power_cdb`]:-300*i,[`tap${i}_delay_ns`]:i*125,[`tap${i}_phase_cdeg`]:0,[`tap${i}_cfo_hz`]:0});
 let current={...defaults},bindings=[];
 const oldWidth=rail.querySelector(':scope>.param-rows');if(oldWidth)oldWidth.hidden=true;
 function field(parent,key,label,options,range,scale=1){
  const l=document.createElement('label');l.className='rail-input';const text=document.createElement('span');text.textContent=label;l.append(text);
  const x=document.createElement(options?'select':'input');x.id='ch_'+key;x.dataset.channelField=key;
  if(options)x.innerHTML=options.map(([v,t])=>`<option value="${v}">${t}</option>`).join('');else {x.type='number';[x.min,x.max,x.step]=range;}
  l.append(x);parent.append(l);bindings.push({key,x,scale});
  x.addEventListener('input',()=>{current[key]=Math.round(Number(x.value)*scale);sync();validConfig=false;clearTimeout(configTimer);configTimer=setTimeout(previewConfig,200);});return l;
 }
 const bandwidth=field(f,'sample_rate_khz','信号带宽 B',[[8000,'4 MHz'],[16000,'8 MHz']]);f.prepend(bandwidth);
 bandwidth.title='矩形脉冲频谱首零点间宽度；当前固定4点/符号，采样率随带宽联动。';
 const sampling=document.createElement('div');sampling.className='rail-input';
 sampling.innerHTML='<span>采样率 Fs</span><output id="channelSampleRate">8 MSa/s · 联动</output>';
 sampling.title='每秒的模型采样点数；固定4点/符号，Fs=2B，不是FPGA工作时钟。';bandwidth.after(sampling);
 field(f,'mode','信道来源',[[1,'场景驱动'],[2,'自主设置'],[0,'主路径＋单回波']]);
 field(f,'fading','小尺度模型',[[0,'无随机衰落'],[1,'Rayleigh'],[2,'Rician']]);
 field(f,'tap_count','传播路径数',[[0,'随场景 / 高度'],...Array.from({length:8},(_,i)=>[i+1,String(i+1)])]);
 const details=document.createElement('dialog');details.className='instrument-details';details.id='channelConfigDetails';
 details.innerHTML='<div class="dialog-heading"><h2>信道参数 · 写入后逐项读回</h2><button type="button">关闭 ×</button></div><div class="instrument-details-body"><p>y[n] = Σ hᵢ[n]·x[n−τᵢ] + w[n]。噪声单独叠加，不属于冲激响应 h。B 为矩形脉冲首零点间宽度，Fs=2B，4 点/符号；不是射频输出带宽。</p><div class="channel-advanced-grid"></div><p id="channelModelMeaning"></p><div class="tap-editor"><div class="tap-head">路径 · 相对功率 dB · 额外时延 ns · 初相位 ° · 频偏 Hz</div><div id="tapEditorRows"></div></div><p id="channelModelReadback">尚无板卡读回</p></div>';
 document.body.append(details);details.querySelector('button').onclick=()=>details.close();
 const advanced=details.querySelector('.channel-advanced-grid');
 field(advanced,'reserved0','程序地形遮挡',[[0,'关闭 · 参数组对照'],[1,'开启 · 主障碍绕射']]);
 field(advanced,'rician_k_cdb','Rician K / dB',null,[0,30,.1],100);
 field(advanced,'scatter_millihz','散射频移上界 / Hz',null,[0,5,.1],1000);
 field(advanced,'delay_scale_percent','场景时延倍率 / %',null,[25,400,1]);
 field(advanced,'echo_decay_cdb','后续路径功率递减 / dB',null,[0,24,.1],100);
 field(advanced,'loss_cdb','总衰减 / dB',null,[0,60,.1],100);
 field(advanced,'cfo_hz','公共频偏 / Hz',null,[-5000,5000,1]);
 field(advanced,'phase_cdeg','公共初相位 / °',null,[0,359.99,.1],100);
 field(advanced,'delay_ns','公共时延 / ns',null,[0,60000,1]);
 for(let i=0;i<8;i++){
  const r=document.createElement('div');r.className='tap-row';r.dataset.tap=i;r.innerHTML=`<b>${i}</b>`;E('tapEditorRows').append(r);
  field(r,`tap${i}_power_cdb`,'功率',null,[-60,0,.1],100);
  field(r,`tap${i}_delay_ns`,'时延',null,[0,60000,1]);
  field(r,`tap${i}_phase_cdeg`,'相位',null,[0,359.99,.1],100);
  field(r,`tap${i}_cfo_hz`,'频偏',null,[-5000,5000,1]);
 }
 const button=document.createElement('button');button.type='button';button.textContent='抽头与模型设置 ↗';button.className='channel-open';button.onclick=()=>{sync();details.showModal();};rail.append(button);
 const dopplerNote=rail.querySelector('.doppler-note');if(dopplerNote)rail.querySelector('.doppler-row').title=dopplerNote.textContent;
 const note=document.createElement('p');note.id='channelDraftStatus';note.className='hint';rail.append(note);
 function sync(){
  if(current.mode===0)current.sample_rate_khz=8000;
  E('channelSampleRate').textContent=`${current.sample_rate_khz/1000} MSa/s · 联动`;
  if(current.mode===2&&!current.tap_count)current.tap_count=2;
  for(const {key,x,scale} of bindings){if(document.activeElement!==x)x.value=current[key]/scale;
   let active=true;if(key==='sample_rate_khz')active=current.mode!==0;
   else if(key==='fading'||key==='tap_count')active=current.mode!==0;
   else if(key==='rician_k_cdb')active=current.mode!==0&&current.fading===2;
   else if(key==='scatter_millihz')active=current.mode!==0&&current.fading!==0;
   else if(key==='delay_scale_percent'||key==='echo_decay_cdb'||key==='reserved0')active=current.mode===1;
   else if(/^(loss_cdb|cfo_hz|phase_cdeg|delay_ns|tap\d_)/.test(key))active=current.mode===2;
   if(/^tap\d_/.test(key)&&Number(key[3])>=current.tap_count)active=false;
   x.disabled=!active||!!history;x.title=active?'编辑值在下一次开始实验时写入；本轮实收结果不会被改写':'此字段不参与当前模型，保留编辑值但不生效';
  }
  if(E('customMode'))E('customMode').checked=current.mode===2;
  const model=['无随机衰落','Rayleigh：32 个独立散射项','Rician：直达项 + 32 个散射项'][current.fading];
  E('channelModelMeaning').textContent=current.mode===0?'主路径＋单回波：固定 8 MSa/s，只用于旧接口对照。':`${model}。总平均抽头功率先归一，再施加损耗。帧内由 FPGA 推进相位与幅度斜率；这是经过误差检查的局部近似。场景路径数：旷野2、乡村3、郊区4、城市6、山地7、丘陵5、高原3；空地+1，低于200m再+1，高于650m减1，上限8。为等效统计路径，不是射线追踪或实测反射次数。地形开启时：同一 DEM 取 63 个剖面点，用 P.526 主障碍刀刃近似增加损耗，地面站天线离地 10 m；不含建筑遮挡或多重绕射。公共数字缩放同时作用于信号和原始噪声，保留相对抽头及 SNR，防止强峰值被截断。自主模式完全忽略场景对信道系数的影响；场景仍供节点运动和业务显示使用。`;
  const o=window.frameObservation?.();E('channelModelReadback').textContent=o?`实读配置 #${o.channel_id??'旧版'} · ${o.sample_rate_hz/1e6} MSa/s · ${o.channel.taps?.length||2} 抽头 · 公共数字缩放 ${(o.channel.digital_scale??1).toFixed(6)} · 系数越界 ${o.channel.coefficient_limited||0} · 接收样本削顶 ${o.clipping??'—'}`:'开始实板实验后，此处显示同帧读回；当前只是编辑配置。';
  note.textContent=history?'历史配置 · 只读':S.busy?'可准备下一轮参数；当前实验继续使用已确认的参数。':'编辑 → 开始实板实验 → 逐项读回确认';
 }
 window.readChannelConfig=()=>({...current});
 window.setChannelConfig=c=>{current=c?{...defaults,...c}:{...defaults};sync();};
 window.setChannelMode=mode=>{current.mode=mode;sync();};
 const old=window.renderInstruments;window.renderInstruments=()=>{old?.();sync();};sync();
})();
