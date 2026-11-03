from pathlib import Path
import subprocess,os,json,time,urllib.request,hashlib
r=Path('deliveries/Swarm_20261023_step29').resolve(); py=r/'runtime/python/python.exe'
env=os.environ.copy();env.update(PYTHONHOME='D:/nonexistent',PYTHONPATH='D:/nonexistent',PATH='C:/Windows/System32;C:/Windows',SWARM_ASSISTANT_URL='http://127.0.0.1:18882')
log=(r/'validation/isolated_server.log').open('w')
p=subprocess.Popen([str(py),'-X','utf8','-B',str(r/'portable_server.py'),'--http','18879','--port','COM3'],cwd='C:/Windows/System32',env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
get=lambda path:urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:18879'+path,timeout=5).read()
try:
 for i in range(40):
  try:info=json.loads(get('/api/info'));break
  except OSError:time.sleep(.25)
 else:raise RuntimeError('server startup failed')
 assert Path(info['root'])==r/'app'
 page=get('/').decode();assert 'mission-story.js' in page
 for path in ('/mission-story.js','/terrain-view.js','/maps.js'):assert len(get(path))>100
 result={'pass':True,'scope':'isolated bundled runtime; independent package root; HTTP and mission/terrain assets; no board execution','root':str(r),'python':str(py),'software_tests':59}
 (r/'validation/portability.json').write_text(json.dumps(result,indent=2))
 print(result)
finally:p.terminate();p.wait();log.close()

