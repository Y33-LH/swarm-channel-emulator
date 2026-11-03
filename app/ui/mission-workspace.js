/* One experiment, several purposeful views. Switching a pane never resets the
 * selected node, experiment, or received data. */
(() => {
 'use strict';
 const E=id=>document.getElementById(id),right=document.querySelector('.p2-right'),left=document.querySelector('.p2-left');
 function tabs(host,entries){
  const nav=document.createElement('div');nav.className='workspace-tabs';nav.setAttribute('role','tablist');
  const body=document.createElement('div');body.className='workspace-panes';
  for(const [title,items] of entries){
   const b=document.createElement('button');b.textContent=title;b.type='button';b.setAttribute('role','tab');
   const pane=document.createElement('div');pane.className='workspace-pane';pane.setAttribute('role','tabpanel');
   items.filter(Boolean).forEach(x=>pane.append(x));body.append(pane);nav.append(b);
   b.onclick=()=>{[...nav.children].forEach(x=>x.setAttribute('aria-selected',String(x===b)));[...body.children].forEach(x=>x.hidden=x!==pane);window.returnSound.pauseHidden();window.renderLiveReturn?.();requestAnimationFrame(()=>window.drawMap?.());};
  }
  host.append(nav,body);nav.firstElementChild.click();return nav;
 }
 const table=right.querySelector('.nodelist-panel');
 const textPanel=document.createElement('section');textPanel.id='recoveryCommands';textPanel.className='panel';
 tabs(right,[['节点 / 指令',[right.querySelector('.nodePanel')]],['全队状态',[table]],['建议',[right.querySelector('.advicePanel')]],['文字指令',[textPanel]],['AI问答',[right.querySelector('.assistantPanel')]],['事件',[right.querySelector('.eventsPanel')]]]);
 const assistant=right.querySelector('.assistantPanel details');if(assistant)assistant.open=true;
 const command=E('controlDetails');if(command)command.open=true;
 const replay=left.querySelector('.media-panel');replay.querySelector('h3').textContent='单节点回放记录';
 E('replayNarration').textContent='从地面实收快照生成位置动画与解说；它用于阅读记录，不是节点传回的视频或语音。';
 const live=window.createLiveReturn();
 tabs(left,[['真实回传',[live]],['回放记录',[replay]]]);
 const previous=window.renderView;
 window.renderView=function(){previous();window.syncRecordReplay?.();};
 window.syncRecordReplay?.();
})();
