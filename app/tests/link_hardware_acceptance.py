"""Exercise real HTTP -> UART -> FPGA -> same-frame observation -> replay."""
from pathlib import Path
import hashlib,json,sys,time,zipfile
import requests
ROOT=Path(__file__).resolve().parents[1]
session=requests.Session();session.trust_env=False
BASE=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18878'
PORT=sys.argv[2] if len(sys.argv)>2 else 'COM9'
out=ROOT/'results'/time.strftime('link_qualification_%Y%m%d_%H%M%S')
out.mkdir()
def call(path,data=None,expected=200):
    r=session.get(BASE+path,timeout=15) if data is None else session.post(BASE+path,json=data,timeout=15)
    assert r.status_code==expected,(path,r.status_code,r.text)
    return r.json()
def wait():
    deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        d=call('/api/link/state')
        if not d['busy']:
            assert d['status']=='complete',d
            return d['experiment']
        time.sleep(.3)
    raise TimeoutError('worker')
try:
    try:
        old=session.get('http://127.0.0.1:8879/api/state',timeout=3).json()
        assert not old['busy'],'Baseline board task active'
    except requests.ConnectionError:pass
    info=call('/api/info');assert Path(info['root'])==ROOT
    call('/api/connect',dict(port=PORT));wait()
    for bad in ({'frames':0},{'link_id':32},{'config':{'sigma':-1}}):
        call('/api/link/start',bad,400)
    cases=[]
    def run(name,data):
        call('/api/link/start',data,202)
        call('/api/link/start',data,409)
        current=wait()
        assert current['phase']=='complete',current
        r=call('/api/link/record?id='+current['id'])
        assert r['complete'] and r['report']['restored_previous_registers']
        assert len(r['observations'])==data.get('frames',3)
        for obs in r['observations']:
            assert obs['config_verified'] and obs['same_frame_verified']
            assert obs['channel']['source']=='FPGA_REGISTER_READBACK'
            assert obs['link']['link_id']==data.get('link_id',0)
            assert len(obs['iq']['received'])==len(obs['iq']['equalized'])==obs['sample_count']
        print(name,r['id'],r['summary'],flush=True)
        cases.append(dict(name=name,id=r['id'],summary=r['summary']))
        return r
    config=dict(link_id=0,text='位置正常，保持通信',frames=3,seed=20261020,config=dict(sigma=0))
    clean=run('clean',config);assert clean['summary']['delivered']==3
    noise=run('noise',dict(config,config=dict(sigma=2800)))
    comparison=call('/api/link/compare?left='+clean['id']+'&right='+noise['id'])
    assert comparison['single_setting_comparison'] and comparison['same_stimulus']
    severe=run('strong_noise',dict(config,frames=2,config=dict(gain=.05,sigma=8192)))
    assert severe['summary']['failed']>0
    assert all(not o['result']['rx_hex'] for o in severe['observations'] if not o['delivered'])
    reverse=run('reverse_air_ground',dict(config,link_id=19,frames=1,config=dict(sigma=0,echo_gain=.1,echo_delay=4)))
    assert reverse['summary']['delivered']==1
    call('/api/link/reproduce',dict(id=clean['id']),202)
    rerun=wait()
    repro=rerun['report']['reproduction']
    assert repro['exact_measurement_reproduced'],repro
    print('REPRODUCED',rerun['id'],flush=True)
    # A recorded view must be read-only; generation/last experiment cannot change.
    before=call('/api/link/state')['experiment']['id']
    for _ in range(3):call('/api/link/record?id='+clean['id'])
    assert call('/api/link/state')['experiment']['id']==before
    archive=call('/api/link/export?id='+clean['id'])
    with zipfile.ZipFile(archive['path']) as z:
        hashes=json.loads(z.read('contents_sha256.json'))
        assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
    # Abort a longer run; keep partial frames without calling it a full pass.
    call('/api/link/start',dict(config,frames=10),202)
    time.sleep(.4);call('/api/stop',{})
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        stopped=call('/api/link/state')
        if not stopped['busy']:break
        time.sleep(.2)
    assert stopped['status']=='stopped',stopped
    partial=call('/api/link/record?id='+stopped['experiment']['id'])
    assert not partial['complete'] and partial['failure']['stopped']
    call('/api/link/reproduce',dict(id=partial['id']),400)
    recovery=run('after_abort',dict(config,frames=1))
    assert recovery['summary']['delivered']==1
    result=dict(pass_interface=True,source='physical_board_UART',cases=cases,
                reproduction=repro,export=archive,abort_preserved=partial['id'],
                manifest_sha256=hashlib.sha256((ROOT/'release.json').read_bytes()).hexdigest(),
                scope='single-hop task only; UI usability and full network qualify separately')
    (out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LINK_HARDWARE_PASS',out,flush=True)
except BaseException as e:
    (out/'failure.json').write_text(json.dumps(dict(error=str(e)),ensure_ascii=False,indent=2),encoding='utf-8')
    raise
