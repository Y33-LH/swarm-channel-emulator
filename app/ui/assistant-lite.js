/* 本地证据问答（精简恢复版）：提问 → 先出规则结论 → 本地模型筛选证据后补全。
   取代已移除的 experiment-workflow.js 中的 window.runExperimentAssistant。
   流程：POST /api/assistant 得 job（含 provisional 规则答案）→ 轮询 /api/assistant/job 直到模型完成。 */
(() => {
 const E = id => document.getElementById(id);
 let asking = false, lastJob = null;
 const subject=job=>{
  const evidence=(job.result||job.provisional)?.evidence||[];
  const node=evidence.find(r=>r.evidence?.slow_period_ms||r.id?.startsWith('heartbeat_resolved_'))?.evidence.node;
  return node?`节点 ${node} · 第 ${Math.ceil(node/4)} 组`:`链路 ${job.context.link}`;
 };
 window.isAssistantPending=()=>asking;

 const context = () => ({
  record_id: history?.id || S.network_record_id,
  mode: history ? 'history' : 'current',
  model_ms: V.snapshot?.round * 100,
  link: Number(E('linkSelect')?.value || 0)
 });
 const relevant = job => {
  const c = context();
  return c.record_id === job.record_id && c.mode === job.context.mode && c.model_ms === job.as_of_model_ms && c.link===job.context.link;
 };
 const sameScope = job => {
  const c=context();
  return c.record_id===job.record_id && c.mode===job.context.mode && c.link===job.context.link
   && (c.mode!=='history' || c.model_ms===job.as_of_model_ms);
 };
 function discardAnswer() {
  lastJob=null;
  if(E('answer'))E('answer').textContent='实验、链路或回放时刻已改变。请针对当前画面重新提问；先前回答不作为当前状态。';
  if(E('assistantStatus'))E('assistantStatus').textContent='等待针对当前上下文重新分析';
 }
 window.refreshAssistantContext=()=>{
  if(!lastJob)return;
  if(!sameScope(lastJob)){discardAnswer();return;}
  const title=E('answer')?.querySelector('.wf-context');
  if(title)title.textContent=`${lastJob.context.mode==='history'?'历史只读':'提问时刻'} · ${(lastJob.as_of_model_ms/1000).toFixed(1)}s · ${subject(lastJob)}${relevant(lastJob)?'':' · 实验已前进'}`;
 };

 function showAnswer(job, response, pending) {
  // A delayed model response must not reinsert future history or another run's facts.
  if(!sameScope(job)){discardAnswer();return;}
  lastJob = job;
  const box = E('answer'); if (!box) return;
  box.replaceChildren();
  const title = document.createElement('p');
  title.className = 'wf-context';
  title.textContent = `${job.context.mode === 'history' ? '历史只读' : '提问时刻'} · ${(job.as_of_model_ms / 1000).toFixed(1)}s · ${subject(job)}`;
  title.title=job.record_id||'';
  const text = document.createElement('p');
  text.textContent = response.answer;
  box.append(title, text);
  for (const item of response.evidence || []) {
   if (!item.action) continue;
   const b = document.createElement('button');
   b.className = 'wide wf-proposal';
   b.textContent = `核对${commandName(item.action.opcode)} → 节点 ${item.action.target} · 参数 ${item.action.value}`;
   b.disabled = job.context.mode === 'history';
   b.onclick = async () => {
    try {
     const c=context();
     if(c.record_id!==job.record_id||c.mode!==job.context.mode||c.link!==job.context.link)throw Error('页面已切换实验或链路，请重新分析当前数据');
     const p = await api('/api/assistant/prepare', { id: job.id, evidence_id: item.id, refresh:true });
     prepareCommand(p.action);
     if(p.revalidated)toast('已按最新实收数据重新核对参数；请检查确认窗口中的目标与数值。');
    } catch (e) { toast(e.message, true); }
   };
   box.append(b);
  }
  const st = E('assistantStatus');
  if (st) st.textContent = pending ? '规则结论已就绪 · 本地模型正在筛选依据'
   : response.model_used ? '本地模型已参与证据筛选 · 数值与操作范围来自实板记录' : '规则分析 · 本次未使用大模型';
 }

 window.runExperimentAssistant = async () => {
  if (asking) return;
  asking = true;
  const btn = E('ask'); if (btn) btn.disabled = true;
  try {
   const c = context();
   if (!c.record_id || c.model_ms == null) throw Error('先运行实验或选择一条历史记录');
   const f = E('attachment')?.files?.[0];
   if (f && f.size > 128000) throw Error('请使用不超过128KB的小段文字资料');
   let job = await api('/api/assistant', { question: E('question').value, attachment: f ? await f.text() : '', context: c });
   showAnswer(job, job.provisional, true);          // 规则结论立刻可见，模型不阻塞
   for (let i = 0; job.status === 'working' && i < 90; i++) {
    await new Promise(r => setTimeout(r, 500));
    job = await api('/api/assistant/job?id=' + job.id);
   }
   if (job.status === 'complete') showAnswer(job, job.result, false);
   else if (E('assistantStatus')) E('assistantStatus').textContent = '规则结论保留；模型未及时完成，请稍后重新分析';
  } catch (e) {
   toast(e.message, true);
   if (E('assistantStatus')) E('assistantStatus').textContent = '问答失败：' + e.message;
  } finally {
   asking = false;
   if (typeof updateButtons === 'function') updateButtons();
  }
 };
})();
