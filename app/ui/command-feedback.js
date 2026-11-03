/* Ground receipt is not the execution timestamp. Changes are measured separately. */
(() => {
 'use strict';
 window.commandReceiptText=function(c,s){
  const [id,node,op,value,state]=c,subject='节点 '+node;
  if(state!==2)return subject+' · '+({1:'已发送，等待回执',3:'拒绝执行',4:'指令过期',5:'未获确认'}[state]||'状态待确认');
  if(op===5){
   const row=s.nodes.find(n=>n[0]===node),metres=row?.[9]?row[6]/1000:null;
   return '执行成功，'+subject+(metres!==null&&row[10]>=c[5]&&Math.abs(metres-value)<2?'实收高度约 '+Math.round(metres)+' 米。':'目标高度已设为 '+value+' 米。');
  }
  return '执行成功，'+subject+({2:'心跳间隔已调至 '+c[7]+' 毫秒。',3:c[8]?'已暂停媒体。':'已恢复媒体。',4:'媒体速率已调至 '+c[9]+' 片/秒。'}[op]||'已回报状态。');
 };
 window.commandFeedbackHtml=function(node){
  const s=V.snapshot;
  return (s?.command_results||[]).filter(c=>c[1]===node).slice(-3).reverse()
   .map(c=>'<p>'+esc(window.commandReceiptText(c,s))+'</p>').join('');
 };
 const renderNodeBefore=window.renderNode;
 window.renderNode=function(){renderNodeBefore();document.getElementById('commandStatus').innerHTML=window.commandFeedbackHtml(selected);};
 const prepareBefore=window.prepareCommand;
 window.prepareCommand=function(a){selected=a.target;renderNode();prepareBefore(a);};
 const updateBefore=window.updateButtons;
 window.updateButtons=function(){updateBefore();if(S.recomputing&&S.busy){const b=document.getElementById('sendCommand');b.disabled=true;b.title='正在按原操作重算，不能插入新指令';}};
})();
