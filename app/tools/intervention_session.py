"""Single-owner board workflow. Manual pauses freeze model time, never fake recovery."""
import copy,json,threading,time,struct
import network_intervention as ni
import action_observation as ao

def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
class Session:
    def __init__(self,rid,out,plan,progress,cancel,replay=None):
        self.id=rid;self.out=out;self.plan=plan;self.progress=progress;self.cancel=cancel
        self.replay=replay;self.mu=threading.RLock();self.wake=threading.Event()
        self.phase='preparing';self.pending=None;self.events=[];self.snapshots=[];self.report=None
        self.error=None;self.target_round=plan['baseline_window_s']*10;self.condition_id=0;self.view=None
        self.replay_actions=copy.deepcopy(replay['events']) if replay else []
        self.replay_index=0;self.finish=False;self.continuous=bool(plan.get('continuous'));self.user_paused=False;self.updated=time.time()
        save(out/'intervention_plan.json',plan)
    def public(self):
        with self.mu:return copy.deepcopy(dict(id=self.id,plan=self.plan,phase=self.phase,view=self.view,
             latest=self.snapshots[-1] if self.snapshots else None,events=self.events,
             report=self.report,error=self.error,replaying=self.replay is not None,updated=self.updated,
             commands=ao.commands(self.snapshots,self.events),recommendations=ao.recommendations(self.snapshots,self.plan,self.events)))
    def submit(self,request,rid):
        a=ni.action(request)
        with self.mu:
            if rid!=self.id or self.phase not in (('waiting','running') if self.continuous else ('waiting',)) or self.replay or self.pending:
                raise ValueError('请等待本轮观测完成；仅能修改当前实验')
            if len(self.events)>=4096:raise ValueError('本记录最多 4096 个操作，请保存并开始新实验')
            if 'observed_round' in request and not self.snapshots[-1]['round']-(100 if self.continuous else 0)<=request['observed_round']<=self.snapshots[-1]['round']:
                raise ValueError('观测时刻已变化，请按当前结果重新确认')
            if a['kind']=='command':
                if not isinstance(request.get('observed_round'),int) or not self.snapshots[-1]['round']-(100 if self.continuous else 0)<=request['observed_round']<=self.snapshots[-1]['round']:raise ValueError('观测时刻已变化，请按当前结果重新确认')
            if not self.continuous and a['kind']!='finish' and self.snapshots[-1]['round']>=self.plan['seconds']*10:
                raise ValueError('实验已达到总时长')
            self.pending=a;self.phase='queued';self.updated=time.time();self.wake.set()
            return dict(ok=True,status='HOST_QUEUED_NOT_APPLIED',action=a)
    def _apply(self,cmd,a,round_index):
        event=dict(index=len(self.events)+1,action=a,effective_round=round_index,
                   requested_wall=time.time(),condition_id=None,readback_ms=None)
        if a['kind'] in ('change','restore'):
            self.condition_id+=1
            wire=struct.pack('<5I',self.condition_id,self.plan['link'],int(a['kind']=='change'),a['gain_permille'],a['sigma']).hex()
            response=cmd('LINKCOND '+wire)
            assert response['effective_round']==round_index and response['id']==self.condition_id
            event.update(condition_id=self.condition_id,receipt=response)
        if a['kind']=='pause':self.user_paused=True
        if a['kind']=='resume':self.user_paused=False
        if a['kind']=='finish':self.finish=True
        else:self.target_round=min(self.plan['seconds']*10,round_index+a['window_s']*10)
        if a['kind']=='command':
            cid=1+sum(e['action']['kind']=='command' for e in self.events)
            c=a['command'];response=cmd('GCOMMAND '+struct.pack('<5I',cid,c['target'],c['opcode'],c['value'],c['ttl_ms']).hex())
            assert response['command_id']==cid and response['status']=='QUEUED_NOT_EXECUTED'
            event.update(command_id=cid,receipt=response)
        self.events.append(event);save(self.out/'interventions.json',self.events)
    def control(self,cmd,snapshot):
        current=snapshot['round'] if snapshot else 0
        if snapshot is None:cmd('NETWATCH '+str(self.plan['link']))
        with self.mu:
            if self.replay:
                while self.replay_index<len(self.replay_actions) and self.replay_actions[self.replay_index]['effective_round']==current:
                    self._apply(cmd,self.replay_actions[self.replay_index]['action'],current);self.replay_index+=1
                if self.replay_index<len(self.replay_actions):
                    assert self.replay_actions[self.replay_index]['effective_round']>=current,'Missed replay boundary'
            elif self.pending:
                a=self.pending;self.pending=None;self._apply(cmd,a,current)
            self.phase='running';self.updated=time.time()
    def on_progress(self,s):
        with self.mu:
            ni.verify_observation(s,self.plan,self.events)
            previous=self.snapshots[-1] if self.snapshots else None
            self.snapshots.append(s);self.view=ni.view(s,previous,self.plan,self.events)
            o=s.get('observation')
            if o:
                for e in self.events:
                    if e.get('condition_id')==o['meta'][0] and e['readback_ms'] is None:
                        e['readback_ms']=o['applied'][1];e['registers']=o['applied']
            save(self.out/'interventions.json',self.events)
            self.updated=time.time()
            waiting=not self.replay and not self.finish and s['running'] and (self.user_paused if self.continuous else s['round']>=self.target_round)
            if waiting:self.wake.clear();self.phase='waiting'
        self.progress(s,self)
        if waiting:
            while not self.wake.wait(.1):
                # Return to the runner, which issues NETSTOP before closing UART.
                if self.cancel():break
    def run(self,runner,port):
        try:
            r,_=runner(port,self.plan['seconds'],0,self.plan['seed'],output=self.out,
                       progress=self.on_progress,cancel=self.cancel,config=self.plan['config'],
                       control=self.control,batch=self.plan['batch_rounds'],strict=False,intervention=True,continuous=self.continuous,finish=lambda:self.finish,repeat_media=self.continuous,stop_round=self.replay['report'].get('stop_round') if self.replay else None)
            summary=ni.evaluate(self.snapshots,self.plan,self.events)
            r['intervention']=summary;r['intervention_schema']=1
            r['actions']=ao.commands(self.snapshots,self.events)
            r['measurement_sha256']=ni.digest([ni.measurement(s) for s in self.snapshots])
            r['action_timeline_sha256']=ni.digest([dict(round=e['effective_round'],action=e['action']) for e in self.events])
            if self.replay:
                assert self.replay_index==len(self.replay_actions)
                r['reproduction']=ni.compare(self.replay,dict(snapshots=self.snapshots,report=r))
                r['reproduction']['original_id']=self.replay['id']
            save(self.out/'acceptance.json',r)
            with self.mu:self.report=r;self.phase='complete';self.updated=time.time()
            return r
        except BaseException as e:
            with self.mu:self.error=str(e);self.phase='stopped' if isinstance(e,InterruptedError) else 'error';self.updated=time.time()
            save(self.out/'failure.json',dict(error=str(e),phase=self.phase));raise

def record(path):
    load=lambda name:json.loads((path/name).read_text('utf-8'))
    snaps=[json.loads(line) for line in (path/'snapshots.jsonl').read_text('utf-8').splitlines()] if (path/'snapshots.jsonl').exists() else []
    p=load('intervention_plan.json');events=load('interventions.json') if (path/'interventions.json').exists() else []
    report=load('acceptance.json') if (path/'acceptance.json').exists() else None
    views=[ni.view(s,snaps[i-1] if i else None,p,events) for i,s in enumerate(snaps)]
    return dict(id=path.name,plan=p,events=events,snapshots=snaps,views=views,report=report,
                complete=bool(report and report.get('pass')),source='recorded_hardware',
                reproducible=bool(report and report.get('pass') and report.get('action_timeline_sha256')),
                failure=load('failure.json') if (path/'failure.json').exists() else None)
