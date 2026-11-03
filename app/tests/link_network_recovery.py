"""Existing full network remains usable after isolated-link experiments."""
from pathlib import Path
import hashlib,json,time
import requests
root=Path(__file__).resolve().parents[1]
s=requests.Session();s.trust_env=False
url="http://127.0.0.1:8880"
out=root/"results"/time.strftime("link_network_regression_%Y%m%d_%H%M%S")
out.mkdir()
def get(path):return s.get(url+path,timeout=10).json()
def post(path,data,code=200):
    r=s.post(url+path,json=data,timeout=15)
    assert r.status_code==code,(path,r.status_code,r.text)
    return r.json()
def wait(limit=200):
    end=time.monotonic()+limit;last=-1
    while time.monotonic()<end:
        d=get("/api/state")
        if not d["busy"]:
            assert d["status"]=="complete",d.get("error")
            return d
        current=(d.get("snapshot") or {}).get("round",0)
        if current!=last:
            print("NETWORK_MODEL_SECONDS",current/10,flush=True);last=current
        time.sleep(2)
    raise TimeoutError("network regression")
try:
    assert Path(get("/api/info")["root"])==root
    assert not get("/api/state")["busy"]
    post("/api/start",dict(seconds=900,ideal=0,seed=20261009,telemetry_rounds=200))
    post("/api/link/start",dict(frames=1),409)
    network=wait();report=network["report"]
    assert report["pass"] and report["all_media_complete"],report
    assert report["final"]["delivered"]/report["final"]["generated"]>.99
    post("/api/link/start",dict(link_id=0,frames=1),202)
    wait(30)
    link=get("/api/link/state")["experiment"]
    assert link["complete"] and link["summary"]["delivered"]==1
    assert link["report"]["restored_previous_registers"]
    assert not any(r["id"].startswith("link_") for r in get("/api/records"))
    result=dict(pass_regression=True,network_id=network["network_record_id"],
                after_network_link_id=link["id"],media_complete=report["all_media_complete"],
                network_delivery=report["final"]["delivered"]/report["final"]["generated"],
                network_wall_seconds=report["wall_total_seconds"],performance_gates=report["performance_gates"],
                manifest_sha256=hashlib.sha256((root/"release.json").read_bytes()).hexdigest(),
                scope="one 900-model-second regression, not three-run release stability")
    (out/"acceptance.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("LINK_NETWORK_REGRESSION_PASS",result,flush=True)
except BaseException as e:
    (out/"failure.json").write_text(json.dumps(dict(error=str(e))),encoding="utf-8")
    raise
