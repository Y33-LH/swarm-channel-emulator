/* All terrain is generated locally; no imagery is loaded. */
(()=>{const s=document.createElement('select');s.id='basemapMode';s.setAttribute('aria-label','地形显示');s.innerHTML='<option value="terrain">程序生成地形</option><option value="grid">工程网格</option>';document.querySelector('.mapoptions').prepend(s);s.onchange=()=>drawMap();window.offlineMapStatus=()=>[];window.offlineMapImage=()=>null;})();
