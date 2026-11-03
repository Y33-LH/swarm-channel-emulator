"""Refresh only after verifying rebuilt firmware and source correspondence."""
from pathlib import Path
import argparse,subprocess,sys
r=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description='核对已构建SDK及RTL，再更新开发文件摘要；不宣称验收通过。')
p.add_argument('--sdk-workspace',required=True,help='app内实际SDK目录，例如 app/results/sdk_continuous1')
a=p.parse_args();ws=Path(a.sdk_workspace)
if not ws.is_absolute():ws=r/ws
subprocess.run([sys.executable,'-X','utf8',str(r/'app/tools/development_manifest.py'),str(ws.resolve())],cwd=r/'app',check=True)
subprocess.run([sys.executable,'-X','utf8',str(r/'app/tools/refresh_bundle_inventory.py')],cwd=r/'app',check=True)
