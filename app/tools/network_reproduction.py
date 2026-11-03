"""Replay user interventions at the original ARM round, never replay RX data.

Only the small documented control vocabulary is accepted. Configuration,
media source, images and evidence digests must match before occupying hardware.
"""
import hashlib,json
from pathlib import Path
import network_intervention as ni
from firmware_contract import BUILD

CONTROL={'NETWATCH','GCOMMAND','LINKCOND','EXTINJECT','EXTRX'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def timeline(rows):
    active=False;current=0;result=[]
    for row in rows:
        command=row['command'];verb=command.split()[0];response=row['response']
        if verb=='NETSTART':active=True;current=0
        elif active and verb in ('NETSTEP','NETFAST'):current=response['round']
        elif verb=='NETSTOP':active=False
        elif active and verb in CONTROL:
            result.append(dict(round=current,command=command,response=response))
    return result

def load(path,root):
    path=Path(path);root=Path(root)
    report=json.loads((path/'acceptance.json').read_text('utf-8'))
    if not report.get('pass') or report.get('arm_build')!=BUILD:
        raise ValueError('该记录不是当前固件完成的实验；可回放，不可冒充当前版精确重算')
    manifest=json.loads((root/'release.json').read_text('utf-8-sig'))
    if any(report['image_hashes'][k]!=sha(root/manifest[k]) for k in ('bit','elf','init')):
        raise ValueError('当前板卡镜像与原实验不同，不能进行同版本重算')
    for name in ('uart.jsonl','snapshots.jsonl'):
        if report.get('evidence_sha256',{}).get(name)!=sha(path/name):
            raise ValueError('原实验缺少完整性摘要或已被修改：'+name)
    for name,digest in report.get('source_media_sha256',{}).items():
        if sha(root/'media'/name)!=digest:raise ValueError('源媒体已改变：'+name)
    if not report.get('source_media_sha256'):raise ValueError('记录缺少源媒体摘要，请使用新版本生成记录')
    rows=[json.loads(x) for x in (path/'uart.jsonl').read_text().splitlines()]
    return dict(id=path.name,report=report,snapshots=[json.loads(x) for x in (path/'snapshots.jsonl').read_text().splitlines()],actions=timeline(rows))

class Control:
    def __init__(self,actions):self.actions=actions;self.index=0
    def __call__(self,cmd,snapshot):
        current=(snapshot or {}).get('round',0)
        while self.index<len(self.actions) and self.actions[self.index]['round']==current:
            item=self.actions[self.index]
            response=cmd(item['command'],allow_reject=True)
            if response!=item['response']:
                raise AssertionError(('Replayed control response differs',current,item['command'],item['response'],response))
            self.index+=1
        if self.index<len(self.actions) and self.actions[self.index]['round']<current:
            raise AssertionError('Missed original control boundary')

def run(original,runner,port,out,progress=None,cancel=None):
    report=original['report'];control=Control(original['actions'])
    current,folder=runner(port,report['requested_duration_s'],report['ideal'],report['seed'],output=out,
        config=report['config'],batch=report['telemetry_rounds'],strict=False,control=control,progress=progress,cancel=cancel,
        continuous=report.get('continuous',False),repeat_media=report.get('repeat_media',False),stop_round=report.get('stop_round'))
    if control.index!=len(control.actions):raise AssertionError('Not all original controls were replayed')
    snapshots=[json.loads(x) for x in (Path(out)/'snapshots.jsonl').read_text().splitlines()]
    result=ni.compare(original,dict(report=current,snapshots=snapshots))
    objects=lambda r:[(x['kind'],x['object_id'],x['complete'],x['sha256']) for x in r.get('media_objects',[])]
    result['all_media_objects_equal']=objects(report)==objects(current)
    result['exact_match']=result['exact_match'] and result['all_media_objects_equal']
    result.update(original_id=original['id'],replayed_control_operations=len(control.actions),
        scope='Actual hardware recomputation with original images/configuration/seed/media and exact control boundaries; no recorded received bytes are fed to the receiver')
    current['reproduction']=result
    (Path(out)/'acceptance.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
    return current,folder
