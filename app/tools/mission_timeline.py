"""Ground-observed state transitions, written even if no dashboard is open."""
import json
from datetime import datetime

class MissionTimeline:
    def __init__(self, folder):
        self.file = folder / 'mission_timeline.jsonl'
        self.rows = []
        self.open = {}
        self.add('start', '实验开始', 0)

    def add(self, kind, label, ms, issue=None):
        row = dict(kind=kind, label=label, model_ms=ms,
                   wall=datetime.now().astimezone().isoformat(timespec='milliseconds'))
        if issue is not None:
            row.update({k:issue[k] for k in ('node','link') if k in issue})
        with self.file.open('a',encoding='utf8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
        self.rows.append(row)

    def observe(self, snap, prev):
        ms=snap['round']*100
        current={(i['kind'],i.get('node',i.get('link'))):i for i in snap['recovery']['issues']}
        for key, i in current.items():
            if key not in self.open:
                self.open[key]=i
                self.add('fault',i['title'],ms,i)
        for key in list(self.open.keys()-current.keys()):
            kind,idx=key
            if kind=='link':
                if not prev or snap['links'][idx][3]<=prev['links'][idx][3]:
                    continue
                label=f'链路 {idx+1} → '+(str(idx+2) if (idx+1)%4 else '地面')+' 恢复确认'
            elif kind=='heartbeat':
                label=f'节点 {idx} 心跳恢复'
            else:
                label='业务积压回落'
            self.add('recover',label,ms,self.open.pop(key))
