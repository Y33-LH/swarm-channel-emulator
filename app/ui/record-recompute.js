/* Recorded playback and hardware recomputation are separate user actions. */
(() => {
 const panel=document.querySelector('.exportPanel'),button=document.createElement('button');
 button.id='recomputeRecord';button.textContent='按原操作重新上板计算';button.className='wide';
 const note=document.createElement('p');note.className='hint';note.id='recomputeResult';
 panel.append(button,note);
 button.onclick=async()=>{
  try{
   const id=history?.id||S.network_record_id;if(!id)throw Error('请先选择已经结束的实验记录');
   await api('/api/recompute',{id});
   stopReplay();history=null;historyRequest++;lastRenderKey='';showTab('evidence');
   toast('已提交实板重算：使用原始条件与操作时刻，结束后比较实际接收结果。');
  }catch(e){toast(e.message,true);}
 };
 const previous=window.renderView;window.renderView=function(){previous();update();};
 function update(){
  button.disabled=!!S.busy||!(history?.report||S.report);
  button.title=S.busy?'请等待当前任务结束':'要求当前固件、原始配置、源媒体和证据摘要一致';
  const r=(history?.report||S.report)?.reproduction;
  note.textContent=S.recomputing&&S.busy?'正在重新计算，不是播放旧结果。额外干预已锁定，可中止。':r?
   `实板重算${r.exact_match?'一致':'存在差异'}：对照 ${r.compared_snapshots} 个快照，${r.mismatches.length} 处差异；全部媒体对象${r.all_media_objects_equal?'一致':'未通过一致性检查'}。`:
   '回放只读取旧结果；重算将按原操作时间轴再次运行 FPGA，并比较快照与实际接收文件。';
 }
 update();
})();
