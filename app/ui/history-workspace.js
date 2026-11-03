/* Keep record selection and all actions visible; long evidence scrolls locally. */
(() => {
 const E=id=>document.getElementById(id),grid=document.querySelector('#history .historygrid');
 const records=E('records').closest('.panel'),compare=E('compare').closest('.panel'),exports=document.querySelector('.exportPanel');
 const right=document.createElement('div');right.className='history-workspace';
 const tabs=document.createElement('div');tabs.className='workspace-tabs';tabs.setAttribute('role','tablist');
 const panes=document.createElement('div');panes.className='history-panes';
 const buttons=[];
 for(const [name,panel] of [['实验比较',compare],['证据与重算',exports]]){
  const b=document.createElement('button');b.type='button';b.textContent=name;b.setAttribute('role','tab');
  b.onclick=()=>{for(const [other,p] of buttons){const on=p===panel;other.setAttribute('aria-selected',String(on));p.hidden=!on;}};
  buttons.push([b,panel]);tabs.append(b);panes.append(panel);
 }
 // Action row stays above the preview, rather than being pushed off the page.
 const recompute=exports.querySelector('#recomputeRecord'),note=exports.querySelector('#recomputeResult'),view=exports.querySelector('#exportView');
 view.before(recompute,note);right.append(tabs,panes);grid.replaceChildren(records,right);
 buttons[0][0].click();
})();
