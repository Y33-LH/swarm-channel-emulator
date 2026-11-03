"""The rendered DEM must match the reference used by ARM; no browser involved."""
from pathlib import Path
import sys,json,subprocess,random,math
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'reference')]
import terrain_model as tm
node=Path(sys.argv[1]);rng=random.Random(20261101)
points=[[rng.uniform(0,10000),rng.uniform(0,10000),env,t]
 for env in range(8) for t in (0,299,300,310,320,599,600,610,620,900,5000) for _ in range(7)]
js="const fs=require('fs'),m=require('./ui/terrain-model.js');process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(p=>m.elevation(...p))));"
r=subprocess.run([str(node),'-e',js],input=json.dumps(points),text=True,capture_output=True,cwd=ROOT,check=True)
actual=json.loads(r.stdout);expected=[tm.elevation(*p) for p in points]
error=max(abs(a-b) for a,b in zip(actual,expected));assert len(actual)==len(points) and error<1e-9,error
out=ROOT/'results/terrain_ui_reference.json';out.write_text(json.dumps(dict(passed=True,points=len(points),max_error_m=error,
 scope='Browser JavaScript DEM mathematics versus Python propagation DEM, including continuous scenario transition boundaries. This is not a visual rendering or flight-safety certification.'),indent=2))
print('TERRAIN_UI_REFERENCE_PASS',len(points),error)
