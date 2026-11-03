/* Expanded channel workspace; preserve original controls and their handlers. */
(()=>{
 const E=id=>document.getElementById(id),rail=document.querySelector('.param-rail:not(.right)'),primary=document.querySelector('.channel-primary');
 rail.tabIndex=0;rail.setAttribute('aria-label','信道参数滚动栏');
 function section(title){const p=document.createElement('section');p.className='panel channel-section';const h=document.createElement('h3');h.textContent=title;p.append(h);rail.append(p);return p;}
 const scene=document.querySelector('.scene-primary');scene.querySelectorAll('.rail-input').forEach(x=>x.hidden=true);scene.querySelector('.rail-actions').hidden=true;
 for(const [kind,name] of [['environment','环境'],['weather','天气'],['formation','编队']]){
  const h=document.createElement('h4');h.textContent=name;scene.append(h,E(kind+'Cards'),E(kind+'Description'));
 }
 const body=E('channelConfigDetails').querySelector('.instrument-details-body');
 const advanced=section('模型与传播参数');advanced.append(body.querySelector('.channel-advanced-grid'));
 const taps=section('自主路径输入');taps.classList.add('compact-taps');taps.append(body.querySelector('.tap-editor'));
 for(const row of taps.querySelectorAll('.tap-row'))for(const label of row.querySelectorAll('label')){const input=label.querySelector('input');input.setAttribute('aria-label','路径 '+row.dataset.tap+' '+label.querySelector('span').textContent);}
 const tapHead=taps.querySelector('.tap-head');tapHead.innerHTML='<span>路径</span><span>功率 dB</span><span>时延 ns</span><span>相位 °</span><span>频偏 Hz</span>';
 const tapNote=document.createElement('p');tapNote.className='hint';tapNote.textContent='仅自主设置模式生效；输入值，不是实时读数。';taps.querySelector('h3').after(tapNote);
 const readback=section('本帧实际应用 · 板卡读回');readback.append(E('channelModelReadback'));
 const measured=document.createElement('div');measured.id='railAppliedTaps';readback.append(measured);
 advanced.append(E('channelFixed'));
 // Keep the model-description target available to existing render code, but do not display it.
 E('channelModelMeaning').hidden=true;
 primary.querySelector('.channel-open').hidden=true;
 // All channel choices are visible buttons; original selects remain the single source of truth.
 const mirrors=[];
 for(const id of ['ch_sample_rate_khz','ch_mode','ch_fading','ch_tap_count','ch_reserved0']){
  const select=E(id),label=select.closest('label'),grid=document.createElement('div');grid.className='channel-choice-grid';label.classList.add('expanded-choice');select.hidden=true;
  for(const o of select.options){const b=document.createElement('button');b.type='button';b.textContent=o.textContent;b.dataset.value=o.value;b.onclick=()=>{select.value=o.value;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));};grid.append(b);}
  label.append(grid);mirrors.push({select,grid});
 }
 // Keep channel controls first, all scene icons next, then all physical parameters.
 rail.append(advanced,taps,readback);
 for(const id of ['channelProfile','channelStatistics']){const p=E(id)?.closest('.panel');if(p)rail.append(p);}
 rail.append(scene);
 const mini=[...rail.querySelectorAll(':scope>.panel')].find(p=>p.querySelector('#mapMiniTop'));if(mini)rail.append(mini);
 rail.append(taps);
 const refresh=()=>{
  for(const {select,grid} of mirrors)for(const b of grid.children){b.disabled=select.disabled;b.setAttribute('aria-pressed',String(b.dataset.value===select.value));b.title=select.title;}
  const o=window.frameObservation?.(),ts=o?.channel?.taps;
  const fmt=(v,n=2)=>Number.isFinite(v)?v.toFixed(n):'—';
  measured.innerHTML=ts?.length?'<table><thead><tr><th>路径</th><th>幅度</th><th>时延 ns</th><th>相位 °</th><th>频偏 Hz</th></tr></thead><tbody>'+ts.map((t,i)=>`<tr><td>${i+1}</td><td>${fmt(t.gain,4)}</td><td>${fmt(t.delay_samples/(o.sample_rate_hz||8000000)*1e9,1)}</td><td>${fmt(t.phase_radians*180/Math.PI,1)}</td><td>${fmt(t.cfo_hz,1)}</td></tr>`).join('')+'</tbody></table>':'暂无同帧传播路径读回';
 };
 const prev=window.renderInstruments;window.renderInstruments=()=>{prev?.();refresh();};refresh();
})();
