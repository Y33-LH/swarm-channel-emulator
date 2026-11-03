from pathlib import Path
import runpy,sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'app/tools'))
runpy.run_path(str(root/'app/tools/server.py'),run_name='__main__')
