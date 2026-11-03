from pathlib import Path
import sys,json,hashlib,datetime
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'tools'),str(root/'reference')]
from product_config import formation_points
from product_scene import position
p=root/'ui/index.html';s=p.read_text(encoding='utf-8')
s=s.replace('href="workbench.css">','href="workbench.css"><link rel="stylesheet" href="instrument.css">')
s=s.replace('<script src="app.js">','<script src="instrument-layout.js"></script><script src="channel-math.js"></script><script src="app.js">')
s=s.replace('<script src="presentation.js">','<script src="instrument.js"></script><script src="presentation.js">')
p.write_text(s,encoding='utf-8')
p=root/'ui/app.js';s=p.read_text(encoding='utf-8')
s=s.replace("const map=$('sharedMapPanel');map.classList.toggle('compact-map',id!=='mission');$(id==='mission'?'sceneMapSlot':'homeMapSlot').append(map);",'')
s=s.replace('function drawMap(){','function drawMap(){if(window.drawInstrumentMap){window.drawInstrumentMap();return;}')
s=s.replace("$('ask').disabled=modelBusy||replay;}","$('ask').disabled=modelBusy||replay;if(window.syncInstrumentChoices)window.syncInstrumentChoices();}")
s=s.replace("if(id==='evidence'){drawTech();}","if(id==='evidence'){drawTech();if(window.renderInstruments)window.renderInstruments();}")
s=s.replace("$('linkSelect').onchange=()=>{drawTech();", "$('linkSelect').onchange=()=>{drawTech();")
s=s.replace("api('/api/watch',{link_id:Number($('linkSelect').value)})", "!history&&api('/api/watch',{link_id:Number($('linkSelect').value)})")
# A history selection must not alter the live watch configuration.
s=s.replace("!history&&api('/api/watch',{link_id:Number($('linkSelect').value)}).catch", "(!history?api('/api/watch',{link_id:Number($('linkSelect').value)}):Promise.resolve()).catch")
s=s.replace("if(tab==='evidence')drawTech();});init()", "if(tab==='evidence')drawTech();if(window.renderInstruments)window.renderInstruments();});init()")
p.write_text(s,encoding='utf-8')
p=root/'ui/workbench.js';s=p.read_text(encoding='utf-8')
s=s.replace('echo_phase_radians:a[128]', 'echo_cfo_hz:signed32(a[132])*8e6/2**32,echo_phase_radians:a[128]')
s=s.replace("p[11]&8?'CRC 通过':'未交付'", "p[11]&4?'CRC / 格式通过':'未交付'")
s=s.replace("stages[3].className=p[11]&8?", "stages[3].className=p[11]&4?")
s=s.replace("};\naction('editScenario'", " if(window.renderInstruments)window.renderInstruments();\n};\naction('editScenario'")
p.write_text(s,encoding='utf-8')
p=root/'ui/maps.js';s=p.read_text(encoding='utf-8').replace('window.drawOfflineMap=', 'window.offlineMapImage=env=>images[env];\n window.drawOfflineMap=');p.write_text(s,encoding='utf-8')
points=[[(position(i,0)[0]-5000,position(i,0)[1]-5000) for i in range(1,17)]]+[formation_points(i) for i in range(1,9)]
(root/'ui/formation-icons.json').write_text(json.dumps(points),encoding='utf-8')
p=root/'start.ps1';s=p.read_text(encoding='utf-8-sig').replace('[int]$HttpPort=8878','[int]$HttpPort=8879');p.write_text(s,encoding='utf-8-sig')
p=root/'tools/server.py';s=p.read_text(encoding='utf-8').replace("version='CHANNEL-WORKBENCH-2'", "version='CHANNEL-INSTRUMENT-3'");p.write_text(s,encoding='utf-8')
print('UI_INTEGRATED')
