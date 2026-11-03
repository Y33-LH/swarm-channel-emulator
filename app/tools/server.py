"""Offline product console; measured data is exclusively from UART or identified records.

The verified step15 release is read-only. One worker owns the serial port. Pause is
between NETSTEP batches, so simulation time is stopped rather than falsified.
"""
import argparse, base64, binascii, csv, hashlib, html, io, json, math, mimetypes
import os, re, subprocess, sys, threading, time, uuid, zipfile, traceback
from functools import lru_cache
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT
sys.path[:0] = [str(BASE/'tests'), str(BASE/'tools'), str(BASE/'tools/python_deps'), str(BASE/'reference')]
import serial
from serial.tools import list_ports
from serial_json import JsonSerial, SerialResponseError
from network_acceptance import run as network_run
from capacity_acceptance import run as capacity_run
from product_scene import channel, position
from product_config import DEFAULT,FIELDS,validate,encode,config_hash,catalog
from product_advice import analyze,validate_action,AdviceTracker
from product_metrics import link_windows,comparison
import queue,struct
from product_assistant import available as assistant_available,answer as assistant_answer
from acceptance import frame
import link_experiment as le
import network_intervention as ni
import intervention_session as nis
import selfcheck
import firmware_errors
import action_observation as ao
import workflow_context as wc
import experiment_comparison as ec
import network_reproduction as nr
from observation_scan import retain
from mission_timeline import MissionTimeline
from recovery_workflow import diagnose, parse as parse_recovery
intervention_current=None

from firmware_contract import VERSION,PROTOCOL,VERSION_HEX,BUILD
RESULTS = ROOT/'results'
RESULTS.mkdir(exist_ok=True)
(ROOT/'configs').mkdir(exist_ok=True)
mu = threading.RLock()
owner = threading.Lock()
assistant_owner = threading.Lock()
assistant_jobs = {}
halt = threading.Event()
paused = threading.Event()
state = dict(status='idle', task=None, port='COM4', connected=False, error=None,
             snapshot=None, snapshots=[], record_id=None, network_record_id=None, report=None, lab=None, lab_batch=None,
             started=None, events=[], pause_requested=False)
# Retain the immediately preceding accepted version's observations read-only.
_parent_roots=[ROOT.parent/name/'results' for name in ('step24_action_context','step25_experiment_workflow','step26_usability')]
BASE_RECORDS = {p.name:p for base in _parent_roots for p in base.glob('*') if p.is_dir() and p.name.startswith(('causal_','network_')) and (p/'metadata.json').exists()}
control_queue=queue.Queue(maxsize=16)
intervene_queue=queue.Queue(maxsize=8)
message_queue=queue.Queue(maxsize=8)  # 业务报文（EXTINJECT kind=5 任意字节经真实多跳链路）
biz_holder={'current':None}
initial_config=dict(DEFAULT,environment=1,formation=7,spacing_m=1050,speed_mmps=20000,reserved=48)
state.update(config=initial_config,advice=[],commands=[],control_pending=[],config_sha256=config_hash(initial_config))
state.update(watch_link=0)
state.update(link_experiment=None)
state.update(business_messages=[])
state.update(phy_live=None,phy_links={},watch_pin_until=0,interventions=[],cond_serial=0)
LIMITS = [['B', '接收同步、频偏与均衡', 'PN 捕获、Gardner 插值定时、重复 PN 估频及补偿、训练辅助复数 DFE；实际 IQ 可读回。', '矩形脉冲；有界测试范围，非任意信道保证'], ['B', '完整 FPGA 纠错链', 'PN9 扰码、8行交织、K7卷积码、双RSC Turbo、两轮Max-Log-MAP、软Viterbi。', '同时报告纠错前编码位 BER 与纠错后正文 BER'], ['A/B', '容量、业务 EVM、采样记录', '逐级真实负载扫描；完整业务符号参考 EVM；512 个原始/均衡后接收符号样本。', '容量只适用于记录中固定路由、TDMA、负载及信道条件'], ['全组', '交付范围', '单板数字基带实验系统；16逻辑节点、地面站、三环境、心跳告警和音视频分片。', '最终比赛报告与视频仍需按当届组委会要求提交']]

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def event(text, level='info'):
    with mu:
        state['events'].append(dict(time=time.strftime('%H:%M:%S'), text=text, level=level))
        state['events'] = state['events'][-80:]

def check_release():
    manifest = json.loads((BASE/'release.json').read_text(encoding='utf-8-sig'))
    for item in manifest['artifacts']:
        p = BASE/item['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('当前发布文件校验失败：'+item['path'])
    return manifest

def record_dir(rid):
    if rid in BASE_RECORDS: return BASE_RECORDS[rid]
    if not re.fullmatch(r'[a-z]+_\d{8}_\d{6}_[a-f0-9]{6}', rid): raise ValueError('无效记录编号')
    p = RESULTS/rid
    if not p.is_dir(): raise ValueError('记录不存在')
    return p

def new_record(kind, **extra):
    rid = kind+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    out = RESULTS/rid
    out.mkdir()
    save(out/'metadata.json', dict(id=rid, kind=kind, created=time.strftime('%Y-%m-%d %H:%M:%S'),
         board_version=VERSION_HEX, serial_port=state['port'], source='hardware_uart',
         release_sha256=hashlib.sha256((BASE/'release.json').read_bytes()).hexdigest(),**extra))
    return rid, out

def read_record(rid, include_controls=True):
    p = record_dir(rid)
    snaps = [json.loads(x) for x in (p/'snapshots.jsonl').read_text().splitlines()] if (p/'snapshots.jsonl').exists() else []
    if (p/'mission_timeline.jsonl').is_file():
        previous=None
        for snap in snaps:
            if 'nodes' in snap:
                snap['recovery']=diagnose(snap,previous)
                previous=snap
    report = json.loads((p/'acceptance.json').read_text(encoding='utf-8')) if (p/'acceptance.json').exists() else None
    meta = json.loads((p/'metadata.json').read_text(encoding='utf-8')) if (p/'metadata.json').exists() else dict(kind='network', source='verified_hardware_record')
    failure = json.loads((p/'failure.json').read_text(encoding='utf-8')) if (p/'failure.json').exists() else None
    controls=None
    if include_controls and (p/'uart.jsonl').exists() and report:
        try:
            raw=(p/'uart.jsonl').read_bytes()
            if report.get('evidence_sha256',{}).get('uart.jsonl')==hashlib.sha256(raw).hexdigest():
                controls=[x for x in nr.timeline([json.loads(line) for line in raw.decode('utf-8').splitlines()]) if x['command'].split()[0]!='NETWATCH']
        except (ValueError,KeyError,TypeError):pass
    timeline_file=p/'mission_timeline.jsonl'
    timeline=[json.loads(line) for line in timeline_file.read_text('utf8').splitlines()] if timeline_file.exists() else []
    return dict(id=rid, path=str(p), meta=meta, mission_timeline=timeline, report=report, snapshots=snaps, failure=failure,control_history=controls,
                complete=bool(report and report.get('pass')), source='recorded_hardware')

def records():
    ids = list(BASE_RECORDS) + [p.name for p in RESULTS.iterdir() if p.is_dir() and (p/'metadata.json').exists()]
    rows = []
    for rid in ids:
        if rid.startswith(('link_','causal_')): continue  # Dedicated frame records have their own reader and controls.
        try:
            d = read_record(rid); r = d['report'] or {}
            rows.append(dict(id=rid, kind=d['meta'].get('kind'), complete=d['complete'],
                failed=bool(d['failure']), seconds=r.get('duration_s'), seed=r.get('seed'),
                ideal=r.get('ideal'), final=r.get('final'), received_ok=r.get('received_ok'), path=d['path']))
        except (ValueError, OSError): pass
    return rows[::-1]

def metrics(s):
    if not s: return {}
    links = s['links']; total = lambda i: sum(x[i] for x in links)
    ratio = lambda a,b: a/b if b else None
    # Coded-channel bits and decoded information bits have different lengths.
    # Subtracting their error counts is not a corrected-bit measurement.
    pre_bits, pre_errors = total(13), total(14)
    applied = s.get('applied_links') or []
    sigmas = [a[5] for a in applied if a and len(a)>5] if applied else []
    return dict(generated=s['generated'], delivered=s['delivered'], delivery=ratio(s['delivered'],s['generated']),
        attempts=total(0), capture=ratio(total(1),total(0)), bits=total(7), errors=total(8), ber=ratio(total(8),total(7)),
        pre_bits=pre_bits, pre_errors=pre_errors, pre_ber=ratio(pre_errors,pre_bits), fec_corrected_bits=None,
        sigma_applied=(min(sigmas),max(sigmas)) if sigmas else None,
        hop_success=ratio(total(3),total(19) if links and len(links[0])>19 else sum(x[0] for x in links[:16])),
        retries=total(4), dedup=total(6), mean_ms=ratio(s['delay_sum_ns']/1e6,s['delivered']),
        max_ms=s['delay_max_ns']/1e6, goodput_bps=ratio(s['payload_bytes']*8,s['round']/10),
        evm_percent=ratio(sum(x[11]*x[12]/10000 for x in links),total(11)), capacity_bps=None,
        timely_delivery=ratio(s.get('timely_delivered',0),s['generated']),late=s.get('late_delivered',0),p95_upper_ms=None if s.get('p95_upper_ms')==4294967295 else s.get('p95_upper_ms'),
        capture_failures=total(0)-total(1),crc_failures=total(1)-total(2),ack_failures=total(16) if links and len(links[0])>16 else None,
        expired=s.get('expired'),attempt_limit=s.get('attempt_limit'))

def node_story(d, node):
    """单个节点的全程业务时间线：来自该记录的实收快照；真值列为 ARM 模型参考。"""
    snaps=d['snapshots'];rep=d['report'] or {};cfg=snaps[-1].get('config') or rep.get('config') or {}
    seed=snaps[-1].get('seed',rep.get('seed'));dur=snaps[-1]['round']/10
    proto=(snaps[-1] if snaps else {}).get('protocol',rep.get('protocol',17))
    rows=[]
    for s in snaps:
        v=next((x for x in s['nodes'] if x[0]==node),None)
        if not v:continue
        ln=s['links'][node-1] if len(s.get('links',[]))>=node else None
        rows.append(dict(t=round(s['round']/10,1),truth=[round(x/1000,1) for x in v[1:4]],rx=[round(x/1000,1) for x in v[4:7]],
            updates=v[9],arrival_ms=v[7],generation_ms=v[10] if len(v)>10 else v[7],attempts=ln[0] if ln else 0,ok=ln[3] if ln else 0,retries=ln[4] if ln else 0,
            media=list(s.get('media',[])) if node in (1,5) else None))
    chain=(node-1)//4
    env_names=['三环境轮换','旷野','乡村','郊区','城市','山地','丘陵','高原']
    env=cfg.get('environment')
    scene_name=env_names[env] if isinstance(env,int) and 0<=env<len(env_names) else '已记录场景'
    seg=[dict(t=0.0,text=f'{scene_name}。节点 {node}，经第 {chain+1} 组上行至地面站。')]
    # Narrate observed changes and returned command receipts only. A configured
    # fault schedule alone is not evidence that this node lost communication.
    stale=False;seen_commands=set()
    commands_by_round={s['round']:s.get('command_results',[]) for s in snaps}
    for row in rows:
        age=row['t']-row['generation_ms']/1000 if row['updates'] else None
        now_stale=row['t']>3 and (age is None or age>3)
        if now_stale and not stale:
            seg.append(dict(t=row['t'],text=f'节点 {node} 的心跳未按时到达地面站。'))
        elif stale and not now_stale and row['updates']:
            seg.append(dict(t=row['t'],text=f'地面站重新收到节点 {node} 的新鲜心跳。'))
        stale=now_stale
        for cmd in commands_by_round[round(row['t']*10)]:
            if cmd[1]!=node or cmd[4] not in (2,3,4) or cmd[0] in seen_commands: continue
            seen_commands.add(cmd[0])
            outcome={2:'执行成功',3:'拒绝执行',4:'已过期'}[cmd[4]]
            seg.append(dict(t=row['t'],text=f'地面收到节点 {node} 对指令 {cmd[0]} 的回执，{outcome}。'))
    if rows:seg.append(dict(t=dur,text=f"本段结束，地面共收到 {rows[-1]['updates']} 次节点心跳。"))
    return dict(record=d['id'],node=node,duration_s=dur,round=snaps[-1]['round'],protocol=proto,config=cfg,seed=seed,
                samples=rows,narration=seg,chain=chain+1,source='record_snapshots_ground_received')

_NARRATION_LOCK=threading.Lock()

def node_audio(d,node,story):
    """Freeze one record cursor. One playback timeline, at most one voice at any sample."""
    import tempfile, wave
    import numpy as np
    folder=record_dir(d['id'])
    base=folder/f"node_audio_v2_{node}_{story['round']}"
    out=base.with_suffix('.wav');meta=base.with_suffix('.json')
    with _NARRATION_LOCK:
        if out.is_file() and meta.is_file():
            return out,json.loads(meta.read_text(encoding='utf-8'))
        sr=8000
        # A single synthesizer process uses an installed Chinese voice throughout.
        # Without one, preserve event captions and generate distinct short cues.
        cues=story['narration']
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            work=Path(tmp)
            script="""$ErrorActionPreference='Stop';[Console]::InputEncoding=[Text.Encoding]::UTF8;
Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;
try {$zh=$v.GetInstalledVoices()|Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh*'}|Select-Object -First 1;
if(!$zh){exit 2};$v.SelectVoice($zh.VoiceInfo.Name);$v.Rate=1;
$lines=ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd()); $i=0;
foreach($line in $lines){$v.SetOutputToWaveFile([IO.Path]::Combine((Get-Location).Path,($i.ToString()+'.wav')));
$v.Speak($line);$v.SetOutputToNull();$i++}} finally {$v.Dispose()}"""
            try:
                subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],cwd=work,
                    input=json.dumps([c['text'] for c in cues],ensure_ascii=False).encode('utf-8'),
                    check=True,timeout=max(30,4*len(cues)),capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except (OSError,subprocess.SubprocessError):
                pass  # Any fully written utterances remain usable.
            cursor=0;spoken=[];beats=[];previous=0
            for row in story['samples']:
                if row['updates']>previous:beats.append(round(row['arrival_ms']*sr/1000))
                previous=row['updates']
            bi=0
            def gap(w,end):
                nonlocal cursor,bi
                while cursor<end:
                    size=min(sr,end-cursor);chunk=np.zeros(size,dtype='<i2')
                    while bi<len(beats) and beats[bi]<cursor+size:
                        offset=beats[bi]-cursor;bi+=1
                        if offset<0:continue
                        length=min(size-offset,400);t=np.arange(length)/sr
                        chunk[offset:offset+length]=(1600*np.sin(2*math.pi*700*t)*np.exp(-t*65)).astype('<i2')
                    w.writeframesraw(chunk.tobytes());cursor+=size
            with wave.open(str(work/'mix.wav'),'wb') as w:
                w.setparams((1,2,sr,0,'NONE','not compressed'))
                for i,c in enumerate(cues):
                    voice=None;p=work/f'{i}.wav'
                    if p.is_file():
                        try:
                            with wave.open(str(p)) as v:
                                if v.getsampwidth()==2:
                                    samples=np.frombuffer(v.readframes(v.getnframes()),dtype='<i2').reshape(-1,v.getnchannels()).mean(axis=1)
                                    if len(samples):
                                        voice=np.interp(np.arange(0,len(samples),v.getframerate()/sr),np.arange(len(samples)),samples).astype('<i2')
                        except (EOFError,OSError,ValueError,wave.Error):pass
                    is_voice=voice is not None
                    if not is_voice:
                        t=np.arange(sr//4)/sr
                        hz=430 if '未按时' in c['text'] or '拒绝' in c['text'] else 660
                        voice=(3800*np.sin(2*math.pi*hz*t)*np.exp(-t*12)).astype('<i2')
                    start=max(round(c['t']*sr),cursor+(sr//4 if spoken else 0))
                    gap(w,start);w.writeframesraw(voice.tobytes());cursor+=len(voice)
                    spoken.append(dict(t=start/sr,end=cursor/sr,event_t=c['t'],text=c['text'],speech=is_voice))
                gap(w,round(story['duration_s']*sr))
            info=dict(narration=spoken,audio_duration_s=cursor/sr,speech=any(c['speech'] for c in spoken))
            save(work/'mix.json',info)
            (work/'mix.wav').replace(out);(work/'mix.json').replace(meta)
        return out,info

def scene(s):
    if not s: return []
    if s.get('applied_links'):
        result=[]
        signed=lambda x:x-2**32 if x>=2**31 else x
        for i,a in enumerate(s['applied_links']):
            tx=i%16+1;rx=tx+1 if tx%4 else 0
            if i>=16:tx,rx=rx,tx
            if not a[0]:
                result.append(dict(link_id=i,tx=tx,rx=rx,applied=False,reference='NOT_YET_APPLIED'));continue
            result.append(dict(link_id=i,tx=tx,rx=rx,channel_class='air_ground' if i%4==3 else 'air_air',applied=True,
                model_ms=a[1],distance_m=a[14]/1000,last_waveform='ACK' if a[2] else 'DATA',gain0=a[3]/32768,gain1=a[4]/32768,sigma=a[5],
                delay_samples=a[6],echo_delay_samples=a[7],phase_radians=a[8]*math.tau/2**32,echo_phase_radians=a[9]*math.tau/2**32,
                cfo_hz=signed(a[10])*s.get('sample_rate_hz',8e6)/2**32,echo_cfo_hz=signed(a[11])*s.get('sample_rate_hz',8e6)/2**32,node_available=not a[12],noise_seed=a[13],
                reference='ARM_GEOMETRY_AND_FPGA_REGISTER_READBACK_NOT_RX_ESTIMATE'))
        return result
    return cached_scene(s['round'],s['seed'],s.get('ideal',0),tuple((s.get('config') or DEFAULT)[k] for k in FIELDS),s.get('protocol',17))

@lru_cache(maxsize=128)
def cached_scene(round_index,seed,ideal,config_values,protocol=20):
    s=dict(round=round_index,seed=seed,ideal=ideal)
    if s.get('ideal'):
        return [dict(link_id=i, tx=(i%16)+1 if i<16 else (0 if i%4==3 else i%16+2),
            rx=(0 if i%4==3 else i%16+2) if i<16 else i%16+1,
            channel_class='air_ground' if i%4==3 else 'air_air', gain0=1, gain1=0,
            sigma=0, cfo_hz=0, echo_cfo_hz=0, delay_samples=0, echo_delay_samples=0,
            phase_radians=0, echo_phase_radians=0, reference='ideal_applied') for i in range(32)]
    return [dict(channel(i,s['round']/10,s['seed'],dict(zip(DEFAULT,config_values)),protocol=protocol),reference='ARM_MODEL_REFERENCE_NOT_RX_ESTIMATE') for i in range(32)]

def client_open():
    s = serial.Serial(state['port'],230400,timeout=.2,write_timeout=5)
    s.reset_input_buffer()
    return s, JsonSerial(s)

def ping():
    s, c = client_open()
    try:
        r = c.request('PING',5)
        if r.get('version') != VERSION or r.get('protocol') != PROTOCOL or r.get('arm_build') != BUILD or r.get('intervention_schema') != 1:
            raise RuntimeError('固件版本不匹配，请加载本版固件。')
        with mu: state.update(connected=True, ping=r)
        return r
    finally: s.close()

def begin(task, fn, *args):
    with mu:
        if not owner.acquire(False): raise RuntimeError('板卡正在被其他任务使用，请先等待或停止网络实验。')
    halt.clear(); paused.clear()
    with mu:
        state.update(status='preparing', task=task, error=None, started=time.time(), pause_requested=False)
        # Retire the previous experiment before the worker verifies large artifacts.
        # A preparation response must never pair a new task with old observations.
        if task in ('network','causal'):
            state.update(snapshot=None,snapshots=[],report=None,record_id=None,network_record_id=None,
                         commands=[],advice=[],metrics={},scene=[],link_windows=[],mission_timeline=[])
    def work():
        try:
            fn(*args)
            with mu: state['status']='complete'
            event('任务完成：'+task)
        except BaseException as e:
            detail=firmware_errors.explain(str(e))
            with mu:
                state.update(status='stopped' if isinstance(e,InterruptedError) else 'error', error=detail or type(e).__name__)
                if task in ('connect','firmware') or (isinstance(e,(OSError,SerialResponseError)) and not isinstance(e,InterruptedError)): state['connected']=False
            # 失败必须留下可读记录：过去出现过 status=error 但事件栏空空如也的情况，
            # 用户完全不知道发生了什么，只能去翻 results/<id>/failure.json。
            event(detail or str(e) or type(e).__name__,'error')
        finally:
            paused.clear()
            with mu: state['pause_requested']=False
            owner.release()
    threading.Thread(target=work,daemon=True).start()

def submit_assistant(d):
    question=d.get('question','');attachment=d.get('attachment','')
    if not isinstance(question,str) or not 1<=len(question.strip())<=2000:raise ValueError('问题须为 1–2000 字符')
    if not isinstance(attachment,str) or len(attachment)>32000:raise ValueError('资料最多 32000 字符')
    with mu:
        saved=json.loads(json.dumps(state));session=intervention_current
    context=wc.select(d,saved,session,read_record,lambda rid:nis.record(record_dir(rid)))
    provisional=assistant_answer(question,context['snapshot'],context['config'],attachment,d.get('model'),context['identity'],False)
    if not assistant_owner.acquire(False):raise ValueError('已有问题正在分析；实验继续运行，无需暂停')
    with mu:
        jid=uuid.uuid4().hex
        job=dict(id=jid,status='working',question=question,created_at=time.time(),
                 record_id=context['identity']['record_id'],run_id=(context['snapshot'] or {}).get('run_id'),
                 as_of_model_ms=(context['snapshot'] or {}).get('round',0)*100,
                 source='cached_received_snapshot',actions_executed=0,context=context['identity'],provisional=provisional)
        assistant_jobs[jid]=job
        for old in list(assistant_jobs)[:-16]:del assistant_jobs[old]
    def work():
        try:
            response=assistant_answer(question,context['snapshot'],context['config'],attachment,d.get('model'),context['identity'])
            with mu:job.update(status='complete',result=response,finished_at=time.time())
        except Exception as e:
            with mu:job.update(status='error',error=str(e),finished_at=time.time())
        finally:
            try:
                folder=RESULTS/'assistant_jobs';folder.mkdir(exist_ok=True);save(folder/(jid+'.json'),job)
            finally:assistant_owner.release()
    threading.Thread(target=work,daemon=True,name='read_only_assistant').start()
    return {k:v for k,v in job.items() if k!='result'}

def prepare_assistant(d):
    with mu:
        job=json.loads(json.dumps(assistant_jobs.get(d.get('id'))))
        snap=json.loads(json.dumps(state.get('snapshot')));rid=state.get('network_record_id');task=state.get('task');cfg=json.loads(json.dumps(state.get('config')))
    if not job:raise ValueError('分析记录已过期，请重新提问')
    c=job['context']
    if c['mode']=='history':raise ValueError('历史问答只读，不可发送指令')
    if not owner.locked() or task not in ('network','causal') or task!=c['kind'] or rid!=job['record_id'] or not snap or snap['run_id']!=job['run_id']:
        raise ValueError('当前实验已结束或切换，请重新提问')
    if c['kind']=='causal':
        if not intervention_current or intervention_current.phase!='waiting' or snap['round']*100!=job['as_of_model_ms']:
            raise ValueError('观测时刻已变化或仍在计算，请等待暂停后重新分析当前数据')
    elif snap['round']*100-job['as_of_model_ms']>10000 and not d.get('refresh'):
        raise ValueError('建议已超过10模型秒，请重新分析当前状态后确认')
    rows=(job.get('result') or job['provisional'])['evidence']
    revalidated=False
    if c['kind']=='network' and d.get('refresh') and snap['round']*100!=job['as_of_model_ms']:
        # Re-evaluate the original explicit question against current received
        # state. Relative-height proposals must not reuse an old confirmed target.
        # This only prepares a confirmation; it never executes an operation.
        current=wc.select({'context':{'record_id':rid,'mode':'current','link':c['link']}},
                          {'task':task,'network_record_id':rid,'snapshot':snap,'config':cfg},None,None,None)
        fresh=assistant_answer(job['question'],current['snapshot'],current['config'],'',None,current['identity'],False)
        rows=fresh['evidence'];c=current['identity'];revalidated=True
    row=next((r for r in rows if r['id']==d.get('evidence_id')),None)
    if not row or not row.get('action'):raise ValueError('这条分析不包含可执行建议')
    command=ao.validate_command(row['action']) if c['kind']=='causal' else validate_action(row['action'])
    return dict(action=command,context=c,observed_round=snap['round'],status='REQUIRES_USER_CONFIRMATION',actions_executed=0,revalidated=revalidated)

def experiment_record(rid):
    r=read_record(rid)
    if rid.startswith('causal_'):r.update(nis.record(record_dir(rid)))
    return r

def experiment_rows():
    rows=[]
    for p in sorted([*RESULTS.iterdir(),*BASE_RECORDS.values()],key=lambda p:p.name,reverse=True):
        if not p.is_dir() or not p.name.startswith(('network_','causal_')) or not (p/'metadata.json').exists():continue
        load=lambda name:json.loads((p/name).read_text('utf-8')) if (p/name).exists() else {}
        rep=load('acceptance.json');plan=load('intervention_plan.json');events=load('interventions.json') or []
        rows.append(dict(id=p.name,kind=load('metadata.json')['kind'],complete=bool(rep.get('pass')),config=rep.get('config') or plan.get('config'),
                         seconds=rep.get('duration_s'),seed=rep.get('seed'),link=plan.get('link'),previous_version=p.name in BASE_RECORDS,
                         has_actions=bool(ec.actions(dict(events=events)) or (rep.get('final') or {}).get('command_results'))))
    return rows

def connect_task(port):
    if not re.fullmatch(r'COM\d+',port): raise ValueError('串口格式应为 COM4 等')
    with mu: state['port']=port
    check_release(); ping(); event(f'已连接实板，PL {VERSION_HEX} / 协议 {PROTOCOL} / 230400 波特率')

def resolve_openocd():
    """解析无 SDK 回退用的 OpenOCD 工具位置，返回 (tools_dir, exe_path)，找不到则为 (None, None)。

    优先级：① 环境变量 → ② 项目自带 app/openocd/ → ③ 作者本机旧绝对路径。
    抽出为独立函数，便于迁移到新机器后用 _check_openocd.py 直接验证，而不是改一次猜一次。
    """
    def first(pred, candidates):
        for cand in filter(None, candidates):
            if pred(Path(cand)):
                return Path(cand)
        return None

    tools = first(Path.is_dir, [
        os.environ.get('SWARM_OPENOCD_TOOLS'),
        str(BASE/'openocd'),
        r'D:\SwarmLab\tools',
    ])
    exe = first(Path.is_file, [
        os.environ.get('SWARM_OPENOCD'),
        str(tools/'openocd/xpack-openocd-0.12.0-7/bin/openocd.exe') if tools else None,
        r'D:\SwarmLab\tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe',
    ])
    return tools, exe

def program_task(port):
    with mu: state.update(port=port,connected=False)
    m = check_release(); rid,out = new_record('firmware')
    if os.environ.get('SWARM_BOARD_PROFILE') != 'wildfire7020': raise RuntimeError('请先在启动菜单确认板卡为匹配的野火7020；不能直接用于PYNQ。')
    sdk = Path(os.environ.get('SWARM_XSCT',''))
    if sdk.is_file():
        event('正在通过 JTAG 加载匹配的 FPGA 与 ARM 固件（xsct）…')
        with (out/'program.log').open('w',encoding='utf-8') as log:
            result = subprocess.run([str(sdk),os.path.relpath(BASE/'program_run.tcl',out),os.path.relpath(BASE/m['bit'],out),os.path.relpath(BASE/m['init'],out),os.path.relpath(BASE/m['elf'],out)],
                cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=150,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or 'PROGRAM_RUN_FINISHED' not in (out/'program.log').read_text(encoding='utf-8',errors='replace'):
            raise RuntimeError('JTAG 加载失败，查看 '+str(out/'program.log'))
    else:
        # 无 Xilinx SDK 时的回退见 resolve_openocd()：按优先级解析 OpenOCD 工具位置
        _tools, _exe = resolve_openocd()
        if not _tools or not _exe:
            raise RuntimeError('未找到 SDK 2018.3（SWARM_XSCT），也未找到 OpenOCD 回退工具。'
                               '请设置 SWARM_OPENOCD_TOOLS/SWARM_OPENOCD 环境变量，'
                               '或把 OpenOCD 套件放到项目内 '+str(BASE/'openocd')+'（可用 _bundle_openocd.py 收纳）。')
        oocd, tools = _exe, _tools
        event('未安装 Xilinx SDK，改用 OpenOCD 经板载 FT2232 JTAG 加载同一份固件…')
        # PCAP 镜像随工具套件收纳（原先写死在 cfg 里指向项目外路径），优先显式传入，避免换机器后找不到
        from pcap_image import derive
        _pcap = out/'system_wrapper_pcap.bin'
        save(out/'pcap_source.json', derive(BASE/m['bit'], _pcap))
        env=dict(os.environ,SWARM_BIT=str(BASE/m['bit']),SWARM_INIT=str(BASE/m['init']),
                 SWARM_ELF=str(BASE/m['elf']),
                 **({'SWARM_PCAPBIN':str(_pcap)} if _pcap.is_file() else {}))
        with (out/'program.log').open('w',encoding='utf-8') as log:
            result = subprocess.run([str(oocd),'-s',str(tools/'openocd/xpack-openocd-0.12.0-7/openocd/scripts'),
                '-f',str(tools/'swarm_ft2232.cfg'),'-f','target/zynq_7000.cfg','-f',str(tools/'ps7_shim.tcl'),'-f',str(tools/'swarm_load.cfg')],
                cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW,env=env)
        log_text=(out/'program.log').read_text(encoding='utf-8',errors='replace')
        if result.returncode or 'PROGRAM_RUN_FINISHED' not in log_text:
            _zadig=_tools/'zadig.exe'
            hint='若日志含 libusb_open 失败：JTAG 驱动未切换，请用 Zadig 将 FT2232 的对应接口切为 WinUSB（需管理员运行）' + \
                 ('，本机套件内含：'+str(_zadig)+'。' if _zadig.exists() else '。')
            raise RuntimeError('JTAG 加载失败（OpenOCD 回退），查看 '+str(out/'program.log')+'。'+hint)
    p=ping(); save(out/'acceptance.json',dict(pass_load=True, **{'pass':True}, ping=p))

def business_frames(text,msg_id):
    """业务报文分帧：BT 头 + 消息号 + 序号 + 总数，每帧净荷 ≤59 字节（固件上限 64）。"""
    raw=text.encode('utf-8')
    if not 1<=len(raw)<=236: raise ValueError('报文须为 1–236 字节（中文约 78 字以内）')
    total=(len(raw)+58)//59
    return [b'BT'+bytes([msg_id%256,seq+1,total])+raw[seq*59:(seq+1)*59] for seq in range(total)]

def process_business(cmd,snapshot,out):
    """在通信批次边界注入/回收业务报文帧；每边界最多注入一帧，避免淹没业务队列。"""
    cur=biz_holder['current']
    if cur is None:
        try: cur=message_queue.get_nowait()
        except queue.Empty: return
        biz_holder['current']=cur
        cur.update(stage='inject',next_seq=0,received={},injected_at_model=(snapshot or {}).get('round',0)*100,
                   last_progress_model=(snapshot or {}).get('round',0)*100)
        event(f"业务报文 {cur['msg_id']} 开始经节点 {cur['node']} 的真实链路发送（{cur['total']} 帧）。")
    node=cur['node']
    if cur['stage']=='inject':
        if cur['next_seq']<cur['total']:
            try: cmd(f"EXTINJECT {node} 5 {cur['frames'][cur['next_seq']].hex()}")
            except AssertionError: return  # 队列满等暂态错误，下一边界重试
            cur['next_seq']+=1
            cur['last_progress_model']=(snapshot or {}).get('round',0)*100
        if cur['next_seq']>=cur['total']: cur['stage']='collect'
    # 每个边界都尝试回收地面实收帧
    try: r=cmd('EXTRX')
    except AssertionError: r=None
    if r and r.get('ok')==1:
        b=bytes.fromhex(r['frame_hex'])
        ln=b[28]|(b[29]<<8)
        if b[1]==5 and ln>=5 and b[32:34]==b'BT' and b[34]==cur['msg_id']%256:
            seq,tot=b[35],b[36]
            if 1<=seq<=tot==cur['total'] and seq not in cur['received']:
                cur['received'][seq]=b[37:32+ln]
                cur['last_progress_model']=(snapshot or {}).get('round',0)*100
                cur.setdefault('first_rx_model',(snapshot or {}).get('round',0)*100)
    model_now=(snapshot or {}).get('round',0)*100
    done=len(cur['received'])==cur['total']
    stalled=model_now-cur['last_progress_model']>60000
    if done or stalled:
        text=None;ok=done
        if done:
            try: text=b''.join(cur['received'][i] for i in range(1,cur['total']+1)).decode('utf-8')
            except UnicodeDecodeError: ok=False
        entry=dict(msg_id=cur['msg_id'],node=node,text=cur['text'],frames_total=cur['total'],
                   frames_received=len(cur['received']),complete=ok,received_text=text if ok else None,
                   injected_model_ms=cur['injected_at_model'],last_rx_model_ms=model_now,
                   note='EXTINJECT 入队 → 逐跳 FPGA 调制/信道/解调 → 地面实收重组；未收齐的帧不做任何补齐')
        with mu: state['business_messages'].append(entry)
        try:
            with (out/'business_messages.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
        except OSError: pass
        event((f"业务报文 {cur['msg_id']} 地面实收重组完成，与发送原文逐字节一致。" if ok else
               f"业务报文 {cur['msg_id']} 未收齐（{len(cur['received'])}/{cur['total']} 帧），缺失帧已留证。"),'info' if ok else 'warn')
        biz_holder['current']=None

# 逐链路明细表用「滚动窗口」而不是「相邻两批」：相邻两批只差 0.2 模型秒，
# 每链路 DATA 尝试只有 2~18 次，计数噪声大且看上去恒定不动。改成最近
# 10 模型秒（100 round）的滚动窗口后，计数规模可读，且随信道/重传真实起伏。
WINDOW_ROUNDS = 100

def window_baseline(snapshots, snap):
    """最近 WINDOW_ROUNDS 之前的那个快照；不足则从本轮第一个快照累计。"""
    if not snapshots: return None
    rid = snap.get('run_id'); target = snap.get('round', 0) - WINDOW_ROUNDS
    for s in reversed(snapshots):
        if s.get('run_id') != rid: break
        if s.get('round', 0) <= target: return s
    head = snapshots[0]
    return head if head.get('run_id') == rid else None

from observation_contract import coherent_observation

def queue_node_command(action,origin,rid,run):
    with mu:
        if state['network_record_id']!=rid or (state.get('snapshot') or {}).get('run_id')!=run:
            raise ValueError('实验已切换，请重新确认指令')
        cid=state['issued_commands']+1
        if cid>0xfffffffe:raise ValueError('指令编号已耗尽，请保存本轮实验')
        request=dict(command_id=cid,action=action,origin=origin,run_id=run,record_id=rid,confirmed_at=time.time())
        control_queue.put_nowait(request)
        state['issued_commands']=cid
        return request

def network_task(seconds, ideal, seed,config,batch=200,reproduce=None,drill_start=None):
    check_release(); rid,out = new_record('network',heartbeat_drill=drill_start is not None)
    advisor=AdviceTracker()
    timeline=MissionTimeline(out)
    ending='实验完成'
    with mu: state.update(mission_timeline=timeline.rows,snapshot=None,snapshots=[],report=None,record_id=rid,network_record_id=rid,config=config,config_sha256=config_hash(config),commands=[],advice=[],issued_commands=0,business_messages=[],phy_live=None,phy_links={},interventions=[],workflow_events=[],cond_serial=0,watch_pin_until=0,recomputing=bool(reproduce))
    save(out/'config.json',dict(config=config,sha256=config_hash(config),telemetry_rounds=batch,heartbeat_drill=drill_start is not None))
    drill_request=None
    while not control_queue.empty():control_queue.get_nowait()
    while not intervene_queue.empty():intervene_queue.get_nowait()
    while not message_queue.empty():message_queue.get_nowait()
    biz_holder['current']=None
    event('上传音视频片段并检查场景参数；实板实验即将开始。')
    carried=dict(links=None,ms=None)
    def progress(s):
        with mu:
            # The applied-register readback is a slow variable: when a snapshot
            # arrives without it, the last real readback is forwarded to the UI
            # together with the model time it was taken, so the channel charts
            # stay drawn instead of blanking. The archived record keeps the raw
            # snapshot; only the UI copy carries the stamp.
            if s.get('applied_links'):
                carried['links']=[list(x) for x in s['applied_links']];carried['ms']=s.get('round',0)*100
            shown=s
            if not s.get('applied_links') and carried['links'] is not None:
                shown=dict(s);shown['applied_links']=[list(x) for x in carried['links']]
                shown['applied_ms']=carried['ms'];shown['applied_carried']=True
            previous=state['snapshots'][-1] if state['snapshots'] else None
            s['recovery']=diagnose(s,previous)
            shown['recovery']=s['recovery']
            if drill_start is not None:
                prior_status={c[0]:c[4] for c in (previous or {}).get('command_results',[])}
                for c in s.get('command_results',[]):
                    if c[4]==2 and c[2]==2 and prior_status.get(c[0])!=2:
                        source='演练设置' if drill_request and c[0]==drill_request['command_id'] else '指令生效'
                        timeline.add('receipt',f'{source} · 节点 {c[1]} 心跳周期 {c[7]} 毫秒',s['round']*100,dict(node=c[1]))
            timeline.observe(s,previous)
            cards,changes=advisor.update(s,previous,config,s.get('command_results',[]))
            # 明细表用 10 模型秒滚动窗口（相邻两批窗口太窄，计数看起来恒定）；
            # 建议引擎仍用相邻快照，才能捕捉到突变。
            win_prev = window_baseline(state['snapshots'], s) or previous
            observation=coherent_observation(s,rid)
            state['phy_links']=retain(state.get('phy_links',{}),observation,s)
            state.update(status='running',snapshot=shown,phy_live=state['phy_links'].get(str(state['watch_link'])),commands=s.get('command_results',[]),advice=cards,link_windows=link_windows(s,win_prev))
            state['snapshots'].append(s)
        prior_commands={x[0]:x[4] for x in (previous or {}).get('command_results',[])}
        for c in s.get('command_results',[]):
            if c[4]!=1 and c[4]!=prior_commands.get(c[0]):
                label={2:'地面收到执行成功回执',3:'地面收到拒绝回执',4:'地面收到过期回执',5:'到期仍未取得执行确认'}.get(c[4],'未知状态')
                event(f'指令 #{c[0]} · 节点 {c[1]}：{label}。'+(f'回执时间 {c[5]/1000:.3f} 模型秒。' if c[4] in (2,3,4) else '不能据此判断节点一定没有执行。'))
        if changes:
            with (out/'events.jsonl').open('a',encoding='utf-8') as f:
                for change in changes:
                    f.write(json.dumps(change,ensure_ascii=False)+'\n')
                    event(change['title']+('：已恢复' if change['event']=='advice_resolved' else '：请关注'),change.get('severity','info'))
        if paused.is_set():
            with mu: state['status']='paused'
            event('已在通信批次边界暂停；仿真时间冻结。')
            while paused.is_set() and not halt.is_set(): time.sleep(.05)
    def control(cmd,snapshot):
        nonlocal drill_request
        if drill_start is not None and snapshot and not halt.is_set():
            # Keep a human interaction window even on a faster demonstration PC.
            elapsed=time.monotonic()-drill_start
            delay=min(120,snapshot['round']*.2)-elapsed
            if delay>0:halt.wait(delay)
            if (not drill_request and not halt.is_set() and time.monotonic()-drill_start>=60
                    and snapshot['recovery']['healthy'] and all(n[9] for n in snapshot['nodes'])):
                try:
                    drill_request=queue_node_command(dict(target=9,opcode=2,value=10000,ttl_ms=10000),
                                                    'demonstration',rid,snapshot['run_id'])
                except queue.Full:pass  # Drain the queue below and retry at the next boundary.
        with mu:watch=state['watch_link']
        if not snapshot or snapshot.get('watch_link')!=watch:cmd('NETWATCH '+str(watch))
        while not control_queue.empty():
            request=control_queue.get_nowait()
            action=request['action']; cid=request['command_id']
            wire=struct.pack('<5I',cid,action['target'],action['opcode'],action['value'],action['ttl_ms']).hex()
            response=cmd('GCOMMAND '+wire,allow_reject=True)
            with (out/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(request=request,response=response))+'\n')
            if response.get('ok')!=1:
                event(f"指令 {cid} 未进入发送队列：{response.get('error','ARM拒绝')}；原实验继续运行。",'warning')
                continue
            event(f"指令 {cid} 已进入地面发送队列，等待目标节点回报。")
            with mu: state['workflow_events'].append(dict(effective_round=(snapshot or {}).get('round',0),command_id=cid,receipt=response,action=dict(kind='command',command=action)))
        try: process_business(cmd,snapshot,out)
        except Exception as e: event('业务报文处理异常：'+str(e),'warn')
        # ④ 链路干预：LINKCOND 在批次边界应用，PL 帧读回确认（与对照实验同一固件机制）
        while not intervene_queue.empty():
            iv=intervene_queue.get_nowait()
            with mu:
                state['cond_serial']=state.get('cond_serial',0)+1; serial_no=state['cond_serial']
            wire=struct.pack('<5I',serial_no,iv['link'],iv['enabled'],iv['gain_permille'],iv['sigma']).hex()
            response=cmd('LINKCOND '+wire)
            entry=dict(serial=serial_no,wall=time.strftime('%H:%M:%S'),round=(snapshot or {}).get('round'),**iv,response=response)
            with mu: state['interventions'].append(entry)
            with mu: state['workflow_events'].append(dict(effective_round=(snapshot or {}).get('round',0),receipt=response,action=dict(kind='change' if iv['enabled'] else 'restore',link=iv['link'])))
            with (out/'interventions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
            event(f"链路干预 #{serial_no}：链路 {iv['link']:02d} {'施加干扰' if iv['enabled'] else '恢复场景条件'}（幅度保留 {iv['gain_permille']/10}% / σ {iv['sigma']}），ARM 已受理，等待 PL 帧读回确认。")

    try:
        if reproduce:
            event('按原时间轴重新上板计算；本次不接受额外干预，结束后逐快照比较。')
            r,_=nr.run(reproduce,network_run,state['port'],out,progress,halt.is_set)
        else:
            r,_=network_run(state['port'],seconds,ideal,seed,output=out,progress=progress,cancel=halt.is_set,config=config,control=control,batch=batch,strict=False,continuous=seconds==0,repeat_media=True)
        with mu: state.update(report=r,connected=True)
        event('实验完成；完整接收的媒体已逐字节校验，可播放。未完整接收的文件保留失败统计。')
        if reproduce:event('原条件实板重算：'+('逐快照及媒体对象一致' if r['reproduction']['exact_match'] else '存在差异，请查看比较结果'),'info' if r['reproduction']['exact_match'] else 'warn')
    except BaseException as e:
        ending='实验中止' if isinstance(e,InterruptedError) else '实验出错'
        save(out/'failure.json',dict(error=str(e) or type(e).__name__,traceback=traceback.format_exc(),stopped=isinstance(e,InterruptedError)))
        raise
    finally:
        with mu:
            timeline.add('end',ending,(state.get('snapshot') or {}).get('round',0)*100)
        # 收尾交代：仍在链路上或仍在队列里的业务报文不能静默消失——落一条未收齐记录并告知。
        pending_biz=[]
        if biz_holder['current'] is not None: pending_biz.append(biz_holder['current'])
        while not message_queue.empty():
            try: pending_biz.append(message_queue.get_nowait())
            except queue.Empty: break
        for cur in pending_biz:
            got=len(cur.get('received') or {}); tot=cur.get('total') or cur.get('frames_total') or len(cur.get('frames') or [])
            entry=dict(msg_id=cur['msg_id'],node=cur['node'],text=cur['text'],frames_total=tot,
                       frames_received=got,complete=False,received_text=None,
                       injected_model_ms=cur.get('injected_at_model',0),last_rx_model_ms=cur.get('last_progress_model',0),
                       note='实验结束/中止时该报文仍在传输或排队，未收齐，不做任何补齐。')
            with mu: state['business_messages'].append(entry)
            try:
                with (out/'business_messages.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
            except OSError: pass
            event(f"业务报文 {cur['msg_id']} 未收齐：实验结束时仍在链路上（{got}/{tot} 帧）。请在实验中段发送，给多跳链路留足传输时间。",'warn')
        biz_holder['current']=None

def lab_task(data):
    check_release(); rid,out=new_record('lab')
    with mu: state['lab']=None
    text=str(data.get('text','蜂群实板通信验证'))
    payload=text.encode('utf-8')
    if not 1<=len(payload)<=64: raise ValueError('UTF-8 文本必须为 1–64 字节；中文约 21 字以内。')
    specs={'gain':(0,1,1),'sigma':(0,8192,0),'delay':(0,512,0),'phase':(-180,180,0),
           'cfo':(-6000,6000,0),'echo_gain':(0,1,0),'echo_delay':(0,32,2),'echo_phase':(-180,180,90),'seed':(1,4294967295,7),'fec':(0,1,1),'modem_profile':(0,1,0)}
    cfg={}
    for k,(lo,hi,default) in specs.items():
        v=float(data.get(k,default))
        if not math.isfinite(v) or not lo<=v<=hi: raise ValueError('参数超出本版实验范围：'+k)
        cfg[k]=v
    if cfg['fec'] not in (0,1): raise ValueError('纠错模式只允许 0 或 1')
    if cfg['modem_profile'] not in (0,1): raise ValueError('请选择已构建的解调方案')
    for k in ('seed','delay','echo_delay'):
        if cfg[k]!=int(cfg[k]):raise ValueError('参数须为整数：'+k)
    tag=int(time.time()*1000)&0xffffffff; tx=frame(payload,tag)
    reg={796:0,12:0,48:5000000,64:round(cfg['gain']*32768),68:round(cfg['sigma']),72:0,
         80:0,84:round(cfg['phase']/360*2**32),88:int(cfg['seed']),92:round(cfg['cfo']/8e6*2**32),96:0,
         112:int(cfg['delay']),116:0,120:round(cfg['echo_gain']*32768),124:int(cfg['echo_delay']),
         128:round(cfg['echo_phase']/360*2**32),132:round(cfg['cfo']/8e6*2**32),136:0,140:0,192:int(cfg['fec']),776:int(cfg['modem_profile'])}
    s,c=client_open()
    try:
        with (out/'uart.jsonl').open('w',encoding='utf-8') as log:
            def cmd(t):
                r=c.request(t,10);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();return r
            def good(t):
                r=cmd(t)
                if r.get('ok')!=1: raise RuntimeError(str(r))
                return r
            p=good('PING')
            if p['version']!=VERSION: raise RuntimeError('固件版本不匹配')
            good('NETSTOP');good('RELEASE')
            for a,v in reg.items():good(f'WRITE {a} {v&0xffffffff}')
            for a,v in reg.items():
                if good(f'READ {a}')['value']!=(v&0xffffffff):raise RuntimeError('参数写入与读回不一致：'+str(a))
            good(f'LOAD {tag} {tx.hex()}');good('START');end=time.monotonic()+6
            while not good('STATUS')['status']&2:
                if time.monotonic()>end:raise TimeoutError('FPGA 完成超时')
            r=cmd('RESULT');regs={a:good(f'READ {a}')['value'] for a in (100,104,156,160,164,168,172,176,180,184)}
            phy=good('PHYSTATS'); iq={}
            for bank in (0,1):
                points=[]
                for off in range(0,phy['iq_count'],64):
                    chunk=good(f'IQ {off} {min(64,phy["iq_count"]-off)} {bank}')
                    if chunk['generation']!=r['generation']:raise RuntimeError('采样记录与接收帧编号不一致')
                    points.extend(chunk['iq'])
                iq['equalized' if bank else 'received']=points
            rx=bytes.fromhex(r.get('rx_hex','')); expected_crc=binascii.crc_hqx(tx,0xffff)
            match=r.get('ok')==1 and rx==tx and r['crc_calc']==r['crc_recv']==expected_crc
            if r.get('ok') and not match: raise AssertionError('有效接收帧与原文不一致，停止发布成功结果。')
            if not r.get('ok') and rx: raise AssertionError('错误帧未被屏蔽')
            row=dict(**{'pass':bool(match)}, execution_completed=True, received_ok=bool(r.get('ok')), match=bool(match),
                phy=phy, iq=iq, estimated_cfo_hz=phy['cfo_phase_step']*8e6/2**32 if phy['timing_updates'] else None, payload_evm_percent=100*math.sqrt(phy['evm_error_sum']/(phy['evm_symbols']*8192**2)) if phy['evm_symbols'] else None,
                text=text, received_text=rx[32:32+len(payload)].decode('utf-8',errors='replace') if match else None,
                tx_hex=tx.hex(), rx_hex=rx.hex(), independent_crc=expected_crc, result=r, registers=regs, config=cfg,
                applied_registers={str(a):v&0xffffffff for a,v in reg.items()},
                errors=regs[160], bits=regs[164], firmware=f'{VERSION:08x}',
                failure_stage=None if match else ('帧头未捕获，纠错尚未开始' if not regs[100] else '已捕获帧头，但译码后 CRC 未通过' if r.get('result_code')==1 else '接收未完成，结果码 '+str(r.get('result_code'))),
                nominal_sample_snr_db=10*math.log10((8192*cfg['gain'])**2/(2*cfg['sigma']**2)) if cfg['gain']>0 and cfg['sigma']>0 else None,
                scope='完整96字节比较；错误帧不作为有效业务交付',id=rid)
            save(out/'acceptance.json',row)
            with mu: state.update(lab=row,connected=True)
            event('实板收发：'+('96 字节完全一致，独立 CRC 一致' if match else '信道导致接收失败，错误帧已拦截'))
            good('RELEASE')
    except BaseException as e:
        save(out/'failure.json',dict(error=str(e)));raise
    finally:s.close()

def lab_batch_task(data):
    """Ten independent-noise, single-attempt frames; preserve every failure."""
    check_release();rid,out=new_record('labnoise')
    text=str(data.get('text','蜂群通信验证'))
    if not 1<=len(text.encode('utf-8'))<=64:raise ValueError('UTF-8 文本必须为 1–64 字节')
    fec=data.get('fec',1)
    if fec not in (0,1):raise ValueError('纠错模式只允许 0 或 1')
    seeds=[]
    while len(seeds)<10:
        seed=uuid.uuid4().int&0xffffffff
        if seed and seed not in seeds:seeds.append(seed)
    cfg=dict(gain=.6,sigma=2800,phase=25,cfo=400,fec=fec,text=text)
    report=dict(id=rid,firmware=f'{VERSION:08x}',source='physical_board_UART',total=10,completed=0,delivered=0,rows=[],seeds=seeds,config=cfg,retries=0,finished=False)
    save(out/'plan.json',dict(config=cfg,seeds=seeds,retries=0))
    with mu:state['lab_batch']=json.loads(json.dumps(report))
    try:
        for seed in seeds:
            lab_task(dict(cfg,seed=seed))
            with mu:row=dict(state['lab'])
            report['rows'].append(dict(id=row['id'],seed=seed,match=row['match'],failure_stage=row['failure_stage']))
            report['completed']+=1;report['delivered']+=int(row['match'])
            save(out/'progress.json',report)
            with mu:state['lab_batch']=json.loads(json.dumps(report))
        report.update(finished=True,rate=report['delivered']/10,target_met=report['delivered']>=9)
        save(out/'acceptance.json',report)
        event(f'噪声连续测试：{report["delivered"]}/10 帧完整接收；每帧只发送一次。')
    except BaseException as e:
        report.update(error=str(e),finished=False);save(out/'failure.json',report);raise
    finally:
        with mu:state['lab_batch']=json.loads(json.dumps(report))

def link_record(rid):
    p=record_dir(rid)
    if not rid.startswith('link_'):raise ValueError('请选择单链路实验记录')
    plan=le.validate_saved_plan(json.loads((p/'plan.json').read_text(encoding='utf-8')))
    observations=[]
    f=p/'observations.jsonl'
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            o=json.loads(line)
            if o['plan_sha256']!=plan['plan_sha256'] or o['measurement_sha256']!=le.digest(le.measurement(o)):
                raise ValueError('观测记录完整性核验失败')
            i=len(observations)
            if (i>=plan['frames'] or o['frame_index']!=i or o['experiment_id']!=rid or
                o['link']!=plan['link'] or o['tx_hex']!=plan['trials'][i]['tx_hex'] or
                o['applied_registers']!=plan['trials'][i]['registers']):
                raise ValueError('观测记录与计划／链路／帧顺序不一致')
            observations.append(o)
    report=json.loads((p/'acceptance.json').read_text(encoding='utf-8')) if (p/'acceptance.json').exists() else None
    failure=json.loads((p/'failure.json').read_text(encoding='utf-8')) if (p/'failure.json').exists() else None
    return dict(id=rid,plan=plan,observations=observations,summary=le.summary(observations),
                report=report,failure=failure,path=str(p),source='recorded_hardware',
                complete=bool(report and report.get('execution_completed')))

def link_task(plan,reproduce_id=None):
    manifest=check_release()
    le.validate_saved_plan(plan)
    original=link_record(reproduce_id) if reproduce_id else None
    if original and not original['complete']:raise ValueError('未完成的实验不能声明完整重现')
    images={k:hashlib.sha256((BASE/manifest[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
    if original and original['report']['images']!=images:
        raise ValueError('原实验固件与当前镜像不同，不能作为同版本重现')
    rid,out=new_record('link')
    save(out/'plan.json',plan)
    rows=[];started=time.monotonic()
    with mu:
        state['link_experiment']=dict(id=rid,plan=plan,phase='preparing',observations=[],
                                     summary=le.summary([]),updated_at=time.time(),reproduce_of=reproduce_id)
    def progress(change):
        with mu:state['link_experiment'].update(change,updated_at=time.time())
    s=None;client=None;previous=None
    event(f'独立单链路实验：{plan["link"]["tx"]} → {plan["link"]["rx"]}；不推进整机网络。')
    try:
        s,client=client_open()
        with (out/'uart.jsonl').open('w',encoding='utf-8') as log:
            def cmd(t):
                r=client.request(t,10)
                log.write(json.dumps(dict(at=time.time(),command=t,response=r))+'\n');log.flush()
                return r
            p=cmd('PING')
            if p.get('version')!=VERSION or p.get('protocol') != PROTOCOL or p.get('arm_build') != BUILD or p.get('pl_hz')!=62500000:
                raise RuntimeError('固件、协议或PL时钟不匹配，请加载当前固件')
            for t in ('NETSTOP','RELEASE'):
                if cmd(t).get('ok')!=1:raise RuntimeError('未能取得空闲FPGA')
            previous={}
            for k in plan['trials'][0]['registers']:
                r=cmd('READ '+k)
                if r.get('ok')!=1 or r.get('offset')!=int(k):raise RuntimeError('无法保存原参数')
                previous[k]=r['value']
            save(out/'previous_registers.json',previous)
            with (out/'observations.jsonl').open('w',encoding='utf-8') as obs:
                for trial in plan['trials']:
                    progress(dict(phase='applying',frame_index=trial['index']))
                    row=le.acquire(cmd,plan,trial,rid,halt.is_set,progress)
                    obs.write(json.dumps(row,ensure_ascii=False)+'\n');obs.flush()
                    rows.append(row)
                    progress(dict(phase='observed',observations=list(rows),summary=le.summary(rows)))
            # RELEASE first, then restore the exact previous configuration; keep
            # the stopped NET scheduler stopped. Never restore stale runtime state.
            if cmd('RELEASE').get('ok')!=1:raise RuntimeError('释放结果失败')
            for k,v in previous.items():
                if cmd(f'WRITE {k} {v}').get('ok')!=1:raise RuntimeError('恢复原参数失败')
            for k,v in previous.items():
                if cmd('READ '+k).get('value')!=v:raise RuntimeError('恢复参数读回不一致')
            report=dict(execution_completed=True,pass_interface=True,source='physical_board_UART',
                        plan_sha256=plan['plan_sha256'],summary=le.summary(rows),images=images,
                        version=f'{VERSION:08x}',restored_previous_registers=True,
                        wall_seconds=time.monotonic()-started,scope=le.SCOPE)
            if original:
                report['reproduction']=le.compare(original,dict(id=rid,plan=plan,observations=rows,report=report))
            save(out/'acceptance.json',report)
            progress(dict(phase='complete',report=report,path=str(out),complete=True))
            with mu:state['connected']=True
            event(f'单跳业务完整接收 {report["summary"]["delivered"]}/{plan["frames"]} 帧；观测已保存。')
    except BaseException as e:
        detail=dict(error=str(e),stopped=isinstance(e,InterruptedError),observed_frames=len(rows))
        # An intact transport can be cleaned up. A poisoned JSON session is never retried.
        if client is not None and not client.failed and previous:
            try:
                client.request('ABORT',5);client.request('RELEASE',5)
                for k,v in previous.items():
                    if client.request(f'WRITE {k} {v}',5).get('ok')!=1:raise RuntimeError('恢复写入失败')
                detail['restored_previous_registers']=all(client.request('READ '+k,5).get('value')==v for k,v in previous.items())
            except Exception as cleanup:detail['cleanup_error']=str(cleanup)
        save(out/'failure.json',detail)
        progress(dict(phase='stopped' if isinstance(e,InterruptedError) else 'error',failure=detail))
        raise
    finally:
        if s is not None:s.close()

def capacity_task():
    check_release();rid,out=new_record('capacity')
    with mu:state.update(capacity=None,record_id=rid)
    def progress(value):
        with mu:state.update(status='running',capacity=value)
    try:
        report=capacity_run(state['port'],out,progress,halt.is_set)
        report['id']=rid;save(out/'acceptance.json',report)
        with mu:state.update(capacity=report,connected=True)
        event('负载扫描完成，已定位本测试条件下的可持续负载与饱和区间。')
    except BaseException as e:
        with mu:state['capacity']={**(state.get('capacity') or {}),'status':'stopped' if isinstance(e,InterruptedError) else 'error'}
        save(out/'failure.json',dict(error=str(e) or type(e).__name__));raise

def verify_task():
    check_release();rid,out=new_record('verify')
    event('执行完整真实收发验收，包括边界长度、CRC 拒收、超时恢复与 1024 帧压力测试。')
    with (out/'console.log').open('w',encoding='utf-8') as log:
        r=subprocess.run([sys.executable,'-X','utf8','-B',str(BASE/'tests/acceptance.py'),'--port',state['port'],'--out',str(out)],
            stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode:raise RuntimeError('完整验收失败：'+str(out/'console.log'))
    report=json.loads((out/'acceptance.json').read_text())
    with mu:state['verification']=dict(id=rid,report=report)
    event(f"完整收发验收通过，{report['checks']} 项检查。")

def csv_bytes(snaps):
    f=io.StringIO(newline='');names=['model_seconds','generated','delivered','delivery','timely_delivery','late','capture','bits','errors','ber','hop_success','retries','mean_ms','p95_upper_ms','max_ms','goodput_bps','evm_percent','capture_failures','crc_failures','ack_failures','expired','attempt_limit']
    w=csv.DictWriter(f,fieldnames=names,extrasaction='ignore');w.writeheader()
    for s in snaps:w.writerow(dict(model_seconds=s['round']/10,**metrics(s)))
    return ('\ufeff'+f.getvalue()).encode('utf-8')

def report_html(d):
    r=d['report'] or {};s=r.get('final');m=metrics(s);esc=lambda x:html.escape(str(x))
    rows=''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in m.items())
    if d['meta'].get('kind')=='lab':
        rows=''.join(f'<tr><td>{esc(k)}</td><td>{esc(r.get(k))}</td></tr>' for k in ('received_ok','match','text','received_text','errors','bits','independent_crc','config','estimated_cfo_hz','payload_evm_percent','phy'))
    if d['meta'].get('kind')=='capacity':
        rows=''.join(f'<tr><td>{esc(k)}</td><td>{esc(r.get(k))}</td></tr>' for k in ('scope','measured_sustainable_payload_bps','max_tested_sustainable_rate_pps','thresholds','interval','wall_s'))
        rows+=''.join(f'<tr><td>每源 {x["rate_pps_per_source"]} 包/秒</td><td>{esc({k:v for k,v in x.items() if k!="final"})}</td></tr>' for x in r.get('rows',[]))
    gaps=''.join(f'<li>{esc(x[0]+"："+x[1]+"。"+x[2]+" 边界："+x[3])}</li>' for x in LIMITS)
    objects=r.get('media_objects') or []
    media=dict(repeated_objects=objects,initial_transfer=r.get('media',{}),
        meaning='重复发送的已知校准音视频；不是无人机现场采集。只允许完整重组且逐字节核对通过的对象播放。',
        complete_objects=sum(bool(o.get('complete')) for o in objects),
        incomplete_objects=sum(not bool(o.get('complete')) for o in objects))
    return f'''<!doctype html><meta charset="utf-8"><title>蜂群信道实验报告</title><style>body{{font:16px Arial,"Microsoft YaHei";max-width:1000px;margin:48px auto;color:#123}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #abc;padding:9px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}h1{{color:#056}}@media print{{body{{margin:12mm}}}}</style>
    <h1>面向蜂群自组网的无线通信多节点信道模拟器</h1><h2>实板实验记录</h2><p>记录：{esc(d['id'])}；来源：{esc(d['source'])}；本条记录通过其自身检查：{esc(d['complete'])}（不代表整机最终验收）。</p>
    <p>PL {esc(r.get('version',d['meta'].get('version','见本次原始记录')))} / Vivado SDK 2018.3。16 个无人机逻辑节点 + 1 地面站，空空/空地两类信道，共用一个 FPGA 核心。</p>
    <p>时长 {esc(r.get('duration_s'))} 仿真秒；种子 {esc(r.get('seed'))}；理想模式 {esc(r.get('ideal'))}；通信计算 {esc(r.get('wall_run_seconds'))} 秒；含参数检查、媒体上传与读回的全流程 {esc(r.get('wall_total_seconds'))} 秒。</p>
    <table><tr><th>实测指标（累计）</th><th>数值</th></tr>{rows}</table>
    <p>pre_ber 为纠错前比较的编码位误码率，ber 为纠错后比较的正文位误码率，分母分别为 pre_bits 与 bits；两种位域的误码数不能直接相减。未捕获帧不进入 BER 分母，必须同时看 capture_failures。捕获率分母含 DATA 与 ACK 尝试；逐跳成功率为 DATA 获 ACK 次数 / DATA 尝试；吞吐按模型时间计算，不是计算机墙钟吞吐。EVM 为均衡后全部业务符号相对已知发送符号的参考 EVM 的逐帧均值；发送参考只用于独立测量，不参与接收判决。None 表示没有有效测量，不能解释为零。</p>
    <h2>音视频证据</h2><pre>{esc(json.dumps(media,ensure_ascii=False,indent=2))}</pre>
    <h2>边界与后续工作</h2><ul>{gaps}</ul><p>用于教学与可重复数字基带实验；无射频发射。场景参数为受控演示参数组，未认证为标准统计信道。不能据此保证竞赛分数。</p>
    <h2>原始记录位置</h2><p>{esc(d['path'])}</p>'''.encode('utf-8')


def intervention_task(p,replay=None):
    global intervention_current
    check_release();rid,out=new_record('causal')
    with mu:state.update(snapshot=None,snapshots=[],report=None,record_id=rid,network_record_id=rid,advice=[],commands=[],config=p['config'])
    def progress(s,session):
        with mu:
            state.update(status='paused' if session.phase=='waiting' else 'running',snapshot=s, commands=s.get('command_results',[]), link_windows=link_windows(s,state['snapshots'][-1] if state['snapshots'] else None), advice=[])
            state['snapshots'].append(s)
    session=nis.Session(rid,out,p,progress,halt.is_set,replay)
    with mu:intervention_current=session
    try:
        r=session.run(network_run,state['port'])
        with mu:state.update(report=r,connected=True)
        event('链路干预实验已保存；恢复状态依据地面实际接收的新心跳。')
    finally:
        save(out/'interventions.json',session.events)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,b,typ='application/json; charset=utf-8',code=200,filename=None):
        self.send_response(code);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store')
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        try:self.wfile.write(b)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def json(self,obj,code=200):self.send(json.dumps(obj,ensure_ascii=False).encode('utf-8'),code=code)
    def do_GET(self):
        try:
            u=urlparse(self.path);path=u.path;q=parse_qs(u.query)

            if path=='/api/causal/context':
                rid=q.get('id',[None])[0];index=int(q.get('index',['-1'])[0])
                if rid:
                    rec=nis.record(record_dir(rid));snaps=rec['snapshots'];p=rec['plan'];events=rec['events'];report=rec['report'];mode='history'
                else:
                    with mu:session=intervention_current
                    if not session:return self.json(dict(context=None))
                    with session.mu:
                        rid=session.id;snaps=list(session.snapshots);p=session.plan;events=list(session.events);report=session.report
                    mode='current'
                if not snaps:return self.json(dict(context=None))
                index=index if index>=0 else len(snaps)-1
                if not 0<=index<len(snaps):raise ValueError('观测索引超出范围')
                snaps=snaps[:index+1];snap=snaps[-1];previous=snaps[-2] if len(snaps)>1 else None
                # All three pages receive exactly one snapshot identity. The watched DATA
                # frame replaces ACK-overwritten parameter rows for that link only.
                import copy
                shown=copy.deepcopy(snap)
                if shown.get('observation'):shown['applied_links'][p['link']]=shown['observation']['applied']
                frame=shown.get('observation')
                context=dict(record_id=rid,run_id=snap['run_id'],index=index,model_ms=snap['round']*100,
                    link=p['link'],mode=mode,config_sha256=p['config_sha256'],
                    frame_generation=frame['meta'][15] if frame else None,
                    frame_ms=frame['applied'][1] if frame else None,
                    identity=f"{rid}:{index}:{p['link']}")
                visible_report=report if mode=='current' or index==len(rec['snapshots'])-1 else None
                if mode=='current':visible_report=report
                return self.json(dict(context=context,snapshot=shown,metrics=metrics(snap),scene=scene(shown),
                    link_windows=link_windows(snap,previous),advice=[],report=visible_report,
                    commands=ao.commands(snaps,events),recommendations=ao.recommendations(snaps,p,events)))
            if path=='/api/causal/state':
                with mu:session=intervention_current
                return self.json(dict(experiment=session.public() if session else None,busy=owner.locked(),connected=state['connected'],task=state['task']))
            if path=='/api/causal/records':
                rows=[]
                for p in sorted([*RESULTS.glob('causal_*'),*[p for k,p in BASE_RECORDS.items() if k.startswith('causal_')]],key=lambda p:p.name,reverse=True):
                    if not (p/'intervention_plan.json').exists():continue
                    load=lambda name:json.loads((p/name).read_text('utf-8')) if (p/name).exists() else None
                    rep=load('acceptance.json');rows.append(dict(id=p.name,plan=load('intervention_plan.json'),complete=bool(rep and rep.get('pass')),
                        reproducible=bool(rep and rep.get('pass') and rep.get('action_timeline_sha256')),report=rep,failure=load('failure.json'),previous_version=p.name in BASE_RECORDS))
                return self.json(rows)
            if path=='/api/causal/record':return self.json(nis.record(record_dir(q['id'][0])))
            if path=='/api/causal/export':
                p=record_dir(q['id'][0]);nis.record(p)
                dest=ROOT/'exports';dest.mkdir(exist_ok=True);target=dest/(p.name+'.zip')
                hashes={}
                with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                    for item in sorted(p.rglob('*')):
                        if item.is_file() and item.resolve().is_relative_to(p.resolve()):
                            name=item.relative_to(p).as_posix()
                            data=item.read_bytes();z.writestr(name,data);hashes[name]=hashlib.sha256(data).hexdigest()
                    z.writestr('contents_sha256.json',json.dumps(hashes,indent=2))
                return self.json(dict(ok=True,path=str(target),bytes=target.stat().st_size))

            if path=='/api/link/state':
                with mu:d=json.loads(json.dumps(state['link_experiment']))
                return self.json(dict(experiment=d,busy=owner.locked(),connected=state['connected'],
                                      task=state['task'],status=state['status']))
            if path=='/api/link/records':
                rows=[]
                for p in sorted(RESULTS.glob('link_*'),reverse=True):
                    if not (p/'plan.json').exists():continue
                    try:
                        d=link_record(p.name)
                        rows.append({k:d[k] for k in ('id','plan','summary','complete','failure')})
                    except (ValueError,KeyError,OSError):continue
                return self.json(rows)
            if path=='/api/link/record':return self.json(link_record(q['id'][0]))
            if path=='/api/link/compare':return self.json(le.compare(link_record(q['left'][0]),link_record(q['right'][0])))
            if path=='/api/link/export':
                d=link_record(q['id'][0]);p=record_dir(d['id'])
                dest=ROOT/'exports';dest.mkdir(exist_ok=True)
                f=dest/(d['id']+'.zip')
                with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:
                    hashes={}
                    for name in ('metadata.json','plan.json','observations.jsonl','uart.jsonl','acceptance.json','failure.json','previous_registers.json'):
                        item=p/name
                        if item.exists():
                            data=item.read_bytes();z.writestr(name,data);hashes[name]=hashlib.sha256(data).hexdigest()
                    z.writestr('contents_sha256.json',json.dumps(hashes,indent=2))
                return self.json(dict(ok=True,path=str(f),bytes=f.stat().st_size))
            if path=='/api/state':
                with mu:d=json.loads(json.dumps(state))
                d['busy']=owner.locked();d['assistant_busy']=assistant_owner.locked();d['metrics']=metrics(d['snapshot']);d['scene']=scene(d['snapshot'])
                return self.json(d)
            if path=='/api/catalog':return self.json(catalog())
            if path=='/api/assistant/status':return self.json(assistant_available())
            if path=='/api/experiments':return self.json(experiment_rows())
            if path=='/api/experiments/compare':
                result=ec.compare(experiment_record(q['left'][0]),experiment_record(q['right'][0]))
                if q.get('save')==['1']:
                    dest=ROOT/'exports'/('comparison_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.json')
                    dest.parent.mkdir(exist_ok=True)
                    save(dest,result);result['saved_path']=str(dest)
                return self.json(result)
            if path=='/api/assistant/job':
                with mu:job=json.loads(json.dumps(assistant_jobs.get(q.get('id',[''])[0])))
                if job is None:raise ValueError('分析任务不存在或已过期')
                return self.json(job)
            if path=='/api/selfcheck':return self.json(selfcheck.static_report())
            if path=='/api/info':
                file=BASE/'results/resources.json'
                r=json.loads(file.read_text()) if file.exists() else dict(resources=None,hardware_acceptance_pending=True)
                return self.json(dict(version='EXPERIMENT-WORKFLOW-1',firmware=VERSION_HEX,resources=r['resources'],resource_evidence=r,limits=LIMITS,
                    root=str(ROOT), ports=[dict(port=p.device,description=p.description) for p in list_ports.comports()],
                    presets=[dict(seconds=900,ideal=0,name='三环境 · 故障与恢复'),dict(seconds=120,ideal=1,name='理想直通 · 快速验证')]))
            if path=='/api/record_evidence':
                # ⑤ 完整证据在界面内直接呈现：逐文件哈希 + 验收要点，不下载
                rid=q['id'][0];d=read_record(rid);p=record_dir(rid);files=[]
                for f in sorted(p.rglob('*')):
                    if f.is_file() and f.resolve().is_relative_to(p.resolve()):
                        b=f.read_bytes()
                        files.append(dict(name=f.relative_to(p).as_posix(),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
                rep=d.get('report') or {}
                return self.json(dict(id=rid,complete=d.get('complete'),source=d.get('source'),
                    acceptance=dict(duration_s=rep.get('duration_s'),wall_total_seconds=rep.get('wall_total_seconds'),
                        acceleration=rep.get('acceleration'),seed=rep.get('seed'),
                        delivered=(rep.get('final') or {}).get('delivered'),generated=(rep.get('final') or {}).get('generated'),
                        all_media_complete=rep.get('all_media_complete'),protocol=rep.get('protocol'),
                        performance_gates=rep.get('performance_gates')),
                    config=rep.get('config'),files=files,limits=LIMITS,reproduction=rep.get('reproduction')))
            if path=='/api/records':return self.json(records())
            if path=='/api/evidence':
                # Acceptance is produced after freezing source. Never expose an
                # older measurement as acceptance of a rebuilt image.
                p=ROOT/'results/product_evidence.json'
                candidate=json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
                if candidate and candidate.get('tested_manifest_sha256')==hashlib.sha256((ROOT/'release.json').read_bytes()).hexdigest():
                    m=check_release()
                    if candidate.get('image_hashes')=={k:hashlib.sha256((ROOT/m[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}:
                        return self.json(candidate)
                return self.json(json.loads((ROOT/'docs/product_evidence.json').read_text(encoding='utf-8')))
            if path=='/api/record_view':
                d=read_record(q['id'][0]);i=int(q.get('index',['-1'])[0]);s=dict(d['snapshots'][i])
                index=i if i>=0 else len(d['snapshots'])+i
                previous=d['snapshots'][index-1] if index>0 else None
                s['recovery']=diagnose(s,previous)
                bank={}
                for sample in d['snapshots'][:index+1]:
                    bank=retain(bank,coherent_observation(sample,d['id']),sample)
                return self.json(dict(snapshot=s,metrics=metrics(s),scene=scene(s),phy_live=coherent_observation(s,d['id']),phy_links=bank,link_windows=link_windows(s,previous),
                                      advice=analyze(s,previous,s.get('config'),s.get('command_results',[]))))
            if path=='/api/compare':return self.json(ec.compare(experiment_record(q['left'][0]),experiment_record(q['right'][0])))
            if path=='/api/record':return self.json(read_record(q['id'][0]))
            if path=='/api/scene':
                rid=q['id'][0];d=read_record(rid);i=int(q['index'][0]);return self.json(scene(d['snapshots'][i]))
            if path=='/api/truth':
                # 稠密模型真值轨迹：供 UI 在两次实收心跳之间连续显示节点位置
                # （product_contract 允许，界面已标注；实收心跳仍是验收依据）。
                t=float(q.get('t',['0'])[0]);span=min(12,max(2,int(q.get('span',['9'])[0])))
                if q.get('record'):
                    d=read_record(q['record'][0]);rep=d['report'] or {}
                    cfg=rep.get('config') or {};seed=rep.get('seed',20261009);dur=rep.get('duration_s',900)
                    proto=(d['snapshots'][-1] if d['snapshots'] else {}).get('protocol',rep.get('protocol',17))
                    snapshots=d['snapshots']
                else:
                    with mu:snap=state.get('snapshot');cfg=state.get('config') or {};snapshots=list(state.get('snapshots') or [])
                    if not snap:raise ValueError('尚无运行中的实验或已载入的记录')
                    seed=snap.get('seed',20261009);dur=snap.get('duration_s',900);proto=snap.get('protocol',17)
                if not cfg:raise ValueError('缺少场景配置')
                from truth_track import track
                return self.json(track(snapshots,cfg,seed,dur,proto,t,span))
            if path in ('/api/node_story','/api/node_audio'):
                d=read_record(q['record'][0],include_controls=False);node=int(q['node'][0])
                if not 1<=node<=16:raise ValueError('节点编号 1–16')
                if 'round' in q:
                    end=int(q['round'][0])
                    d['snapshots']=[s for s in d['snapshots'] if s['round']<=end]
                if not d['snapshots']:raise ValueError('此记录尚无快照数据')
                story=node_story(d,node)
                if path=='/api/node_story' and q.get('audio')!=['1']:return self.json(story)
                f,mix=node_audio(d,node,story)
                if path=='/api/node_story':return self.json(dict(story,**mix))
                return self.send(f.read_bytes(),'audio/wav')
            if path in ('/api/export','/api/report','/api/csv'):
                d=read_record(q['id'][0]);rid=d['id']
                def artifact(b,typ,extension):
                    dest=ROOT/'exports';dest.mkdir(exist_ok=True);file=dest/(rid+extension);file.write_bytes(b)
                    if q.get('save')==['1']:return self.json(dict(ok=True,path=str(file),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
                    return self.send(b,typ,filename=None if q.get('preview')==['1'] else file.name)
                if path=='/api/report':return artifact(report_html(d),'text/html; charset=utf-8','.html')
                if path=='/api/csv':return artifact(csv_bytes(d['snapshots']),'text/csv; charset=utf-8','.csv')
                z=io.BytesIO();p=record_dir(rid);hashes={}
                with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as archive:
                    for name in ('acceptance.json','metadata.json','config.json','commands.jsonl','command_trace.json','events.jsonl','mission_timeline.jsonl','interventions.jsonl','business_messages.jsonl','failure.json','snapshots.jsonl','uart.jsonl','transcript.jsonl','vectors.jsonl','received_audio.wav','received_video.webm','console.log','program.log','media_objects.jsonl',*[f.relative_to(p).as_posix() for f in (p/'media_objects').rglob('*') if f.is_file() and f.resolve().is_relative_to(p.resolve())],*[f.name for f in p.glob('rate_*.json')],*[f.name for f in p.glob('incomplete_*.json')]):
                        f=p/name
                        if f.exists():
                            b=f.read_bytes();archive.writestr(name,b);hashes[name]=hashlib.sha256(b).hexdigest()
                    for name,data in (('metrics.csv',csv_bytes(d['snapshots'])),('report.html',report_html(d))):
                        if isinstance(data,str):data=data.encode('utf-8')
                        archive.writestr(name,data);hashes[name]=hashlib.sha256(data).hexdigest()
                    archive.writestr('provenance.json',json.dumps(dict(id=rid,source=d['source'],complete=d['complete'],sha256=hashes,remaining=LIMITS),ensure_ascii=False,indent=2))
                return artifact(z.getvalue(),'application/zip','.zip')
            if path.startswith('/media-object/'):
                _,_,rid,kind,sequence=path.split('/')
                if kind not in ('3','4') or not sequence.isdecimal():raise ValueError('媒体编号无效')
                folder=record_dir(rid)/'media_objects'/f'{kind}_{int(sequence):08x}'
                r=json.loads((folder/'object.json').read_text())
                if not r.get('complete') or r['object_id']!=int(sequence) or r['kind']!=int(kind):raise ValueError('该片段尚未完整接收')
                name='received_audio.wav' if kind=='3' else 'received_video.webm'
                f=folder/name
                if hashlib.sha256(f.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('接收片段校验失败')
            elif path.startswith('/media/'):
                _,_,rid,name=path.split('/')
                d=read_record(rid)
                if not d['complete'] or name not in ('received_audio.wav','received_video.webm'):raise ValueError('接收文件尚未完整验证')
                f=record_dir(rid)/name
                expected=d['report'].get('media',{}).get(name,{}).get('sha256')
                if not d['report'].get('media',{}).get(name,{}).get('complete',False):raise ValueError('媒体存在缺失分片，不能播放')
                if not expected or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:raise ValueError('接收媒体校验失败')
            else:
                f=(ROOT/'ui'/('index.html' if path=='/' else path.lstrip('/'))).resolve()
                if not f.is_relative_to((ROOT/'ui').resolve()):raise ValueError('非法路径')
            if not f.is_file():return self.json({'error':'页面不存在'},404)
            data=f.read_bytes()
            if f.name=='index.html' and f.parent==(ROOT/'ui').resolve():
                def asset_version(match):
                    name=match.group(2);asset=ROOT/'ui'/name
                    return match.group(1)+name+'?v='+hashlib.sha256(asset.read_bytes()).hexdigest()[:12]+match.group(3) if asset.is_file() else match.group(0)
                data=re.sub(r'(\b(?:src|href)=")([^"?]+\.(?:js|css))(")',asset_version,data.decode('utf-8')).encode('utf-8')
            return self.send(data,mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
        except Exception as e:self.json({'error':str(e)},400)
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.json({'error':'拒绝跨站硬件操作'},403)
            n=int(self.headers.get('Content-Length','0'))
            if n>2000000:raise ValueError('请求过大')
            d=json.loads(self.rfile.read(n) or '{}');path=urlparse(self.path).path

            if path=='/api/causal/start':
                p=ni.plan(d);begin('causal',intervention_task,p)
                return self.json(dict(ok=True,plan=p),202)
            if path=='/api/causal/action':
                if not intervention_current or not owner.locked() or state['task']!='causal':raise ValueError('没有活动的链路干预实验')
                return self.json(intervention_current.submit(d,d.get('id')),202)
            if path=='/api/causal/reproduce':
                rec=nis.record(record_dir(str(d.get('id',''))))
                if not rec['complete']:raise ValueError('请选择完整记录')
                ni.validate_reproduction(rec)
                hashes={k:hashlib.sha256((BASE/check_release()[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
                if hashes!=rec['report']['image_hashes']:raise ValueError('固件与原记录不同，不能宣称原条件重算')
                begin('causal',intervention_task,rec['plan'],rec)
                return self.json(dict(ok=True,status='recomputing_all_rounds'),202)

            if path=='/api/link/preview':return self.json(le.plan(d))
            if path=='/api/link/start':
                p=le.plan(d);begin('link',link_task,p)
                return self.json(dict(ok=True,plan_sha256=p['plan_sha256'],status='queued'),202)
            if path=='/api/link/reproduce':
                r=link_record(str(d.get('id','')))
                if not r['complete']:raise ValueError('请选择完整的单链路记录')
                begin('link',link_task,r['plan'],r['id'])
                return self.json(dict(ok=True,plan_sha256=r['plan']['plan_sha256'],status='queued'),202)
            if path=='/api/preview':
                cfg=validate(d.get('config') or {});seed=int(d.get('seed',20261013))
                if not 1<=seed<=4294967295:raise ValueError('种子超界')
                return self.json(dict(config=cfg,config_sha256=config_hash(cfg),nodes=[dict(id=i,xyz_m=position(i,0,seed,cfg,protocol=PROTOCOL)) for i in range(1,17)],
                                      source='configuration_preview_not_hardware',ground_xyz_m=[5000,5000,0]))
            if path=='/api/capture':
                raw=str(d.get('png',''))
                if not raw.startswith('data:image/png;base64,'):raise ValueError('需要 PNG 图像')
                b=base64.b64decode(raw.split(',',1)[1],validate=True)
                if not b.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('PNG 格式无效')
                dest=ROOT/'exports';dest.mkdir(exist_ok=True);f=dest/('map_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.png');f.write_bytes(b)
                return self.json(dict(ok=True,path=str(f)))
            if path=='/api/assistant':
                return self.json(submit_assistant(d),202)
            if path=='/api/assistant/prepare':return self.json(prepare_assistant(d))
            if path=='/api/experiments/variant':
                rec=experiment_record(str(d.get('id','')))
                if not rec.get('complete') or not rec.get('plan'):raise ValueError('请选择完整的链路与措施基线记录')
                ni.validate_reproduction(rec)
                if ec.actions(rec):raise ValueError('原记录含干预；请用无干预基线做单设置对照')
                key=d.get('field');value=d.get('value')
                if key not in ('environment','weather','formation','reference_snr_cdb','jitter_percent') or type(value)!=int:raise ValueError('不支持此对照设置')
                config={**rec['plan']['config'],key:value}
                if config==rec['plan']['config']:raise ValueError('设置未变化；重复实验请使用原条件重算')
                p=ni.plan(dict(link=rec['plan']['link'],seed=rec['plan']['seed'],seconds=rec['plan']['seconds'],config=config))
                begin('causal',intervention_task,p)
                return self.json(dict(ok=True,plan=p,baseline_id=rec['id']),202)
            if path=='/api/recompute':
                original=nr.load(record_dir(str(d.get('id',''))),ROOT)
                r=original['report'];begin('network',network_task,r['requested_duration_s'],r['ideal'],r['seed'],r['config'],r['telemetry_rounds'],original)
                return self.json(dict(ok=True,original_id=original['id'],status='queued_hardware_recomputation'),202)
            if path in ('/api/command','/api/intervene','/api/business/message') and state.get('recomputing') and owner.locked():
                raise ValueError('正在按原操作时间轴重算；请先结束本次重算再发新指令')
            if path=='/api/watch':
                link=d.get('link_id',d.get('link'))
                if type(link)!=int or not 0<=link<32:raise ValueError('请选择有效链路')
                with mu:
                    state['watch_link']=link;state['watch_pin_until']=time.monotonic()+30
                    state['phy_live']=state.get('phy_links',{}).get(str(link))
                return self.json(dict(ok=True,link_id=link,status='applies_at_next_batch'))
            if n>8192:raise ValueError('命令请求过大')
            if path=='/api/stop':
                if state['task'] not in ('network','capacity','link','causal') or not owner.locked():raise ValueError('没有可停止的实验任务')
                halt.set();paused.clear();event('已请求停止，等待当前 FPGA 通信批次完成。');return self.json({'ok':True})
            if path=='/api/pause':
                if state['task']!='network' or not owner.locked():raise ValueError('没有可暂停的网络任务')
                paused.set();state['pause_requested']=True;return self.json({'ok':True})
            if path=='/api/resume':
                with mu:
                    paused.clear();state['pause_requested']=False
                    if owner.locked() and state['task']=='network':state['status']='running'
                return self.json({'ok':True})
            if path in ('/api/connect','/api/program'):
                port=str(d.get('port','COM4'))
                if not re.fullmatch(r'COM\d+',port):raise ValueError('串口格式无效')
                begin('connect' if path.endswith('connect') else 'firmware',connect_task if path.endswith('connect') else program_task,port)
            elif path=='/api/start':
                seconds=int(d.get('seconds',900));ideal=int(d.get('ideal',0));seed=int(d.get('seed',20261009))
                if (seconds!=0 and not 60<=seconds<=900) or ideal not in (0,1) or not 1<=seed<=4294967295:raise ValueError('运行时长为持续运行（0）或60–900秒；种子非零')
                config=validate(d.get('config') or {})
                stale=[p for p in (firmware_errors.preflight(config,(state.get('ping') or {}).get('protocol',17)))]
                if stale:raise ValueError('；'.join(stale))
                # 「三环境连续演示」要跑满 900 秒才能看到环境演化：环境在 300 秒切到郊区、
                # 600 秒切到城市。短时长只会停留在第一段的旷野，用户据此比较参数会误判
                # 「改了参数没反应」。这里提前说明，而不是让用户对着一样的结果发懵。
                if config.get('environment')==0 and 0<seconds<600:
                    event('三环境连续演示需要在 900 秒里演化：环境分别在 300 秒与 600 秒切换。'
                          '当前只有 %d 秒，只会跑到第一段的旷野场景，'
                          '看不出后续两段的信道差异。如需对比环境差异，请直接选定单一环境，或用满 900 秒。'%seconds,'warning')
                batch=d.get('telemetry_rounds',200)
                if type(batch)!=int or batch not in (10,20,50,100,200):raise ValueError('遥测批次只允许 10/20/50/100/200 轮')
                drill=d.get('heartbeat_drill',False)
                if type(drill)!=bool:raise ValueError('心跳演练配置无效')
                if drill and (config['environment']!=5 or config['weather']!=0 or config['formation']!=0
                              or config['faults'] or config['external_node'] or ideal or (seconds and seconds<60)):
                    raise ValueError('单节点演练需要山地、晴天、X形、实测信道和至少60通信秒；请点击最终演示预设。')
                begin('network',network_task,seconds,ideal,seed,config,10 if drill else batch,None,time.monotonic() if drill else None)
            elif path=='/api/recovery/parse':
                plan=parse_recovery(d.get('text',''))
                return self.json(dict(ok=True,plan=plan))
            elif path=='/api/command':
                if not owner.locked() or state['task']!='network' or not state['snapshot']:raise ValueError('仅在活动实板网络实验中发送')
                if d.get('confirm') is not True:raise ValueError('需要用户确认指令')
                if d.get('record_id')!=state['network_record_id'] or d.get('run_id')!=state['snapshot']['run_id']:raise ValueError('实验已改变，请刷新后确认')
                action=validate_action(d.get('action'))
                try:request=queue_node_command(action,'operator',d['record_id'],d['run_id'])
                except queue.Full:raise ValueError('指令队列已满，请在下一次遥测更新后重试')
                return self.json(dict(ok=True,request=request,status='host_queued'))
            elif path=='/api/intervene':
                # ④ 链路干预嵌入业务主线：运行中对一条有向链路施加/撤销幅度与噪声干预
                if not owner.locked() or state['task']!='network' or state.get('status') not in ('running','paused'):
                    raise ValueError('仅在网络实验运行中可干预链路')
                link=int(d.get('link',-1))
                if not 0<=link<32: raise ValueError('链路编号 0–31')
                enabled=1 if d.get('enabled',1) else 0
                gp=int(d.get('gain_permille',400))
                sg=int(d.get('sigma',1500))
                if not 0<=gp<=1000 or not 0<=sg<=8193: raise ValueError('幅度保留 0–1000‰，噪声 σ 0–8192；8193表示保留场景噪声')
                try: intervene_queue.put_nowait(dict(link=link,enabled=enabled,gain_permille=gp,sigma=sg))
                except queue.Full: raise ValueError('干预队列已满，请等待上一个干预生效')
                return self.json(dict(ok=True,queued=True,link=link,enabled=enabled),202)
            elif path=='/api/business/message':
                if not owner.locked() or state['task']!='network' or state.get('status') not in ('running','paused'):
                    raise ValueError('仅在网络实验运行中可发送业务报文')
                node=int(d.get('node') or 0)
                ext=(state.get('config') or {}).get('external_node',0)
                # 固件 EXTINJECT 协议事实：注入节点必须等于本实验配置的外部业务端节点，
                # 否则 ARM 一律拒绝（EXTERNAL_RANGE_OR_STATE）。在这里前置拦截，
                # 避免「界面说已排队、固件实际拒绝、用户永远等不到回执」。
                if not 1<=ext<=16 or ext in (9,13):
                    raise ValueError('本实验未配置外部业务端节点，报文无处注入。'
                                     '请在第 2 页「更多实验参数 → 外部业务端节点」选一个 1–16 中除 9/13 外的节点后重新开跑；'
                                     '该节点的心跳与业务都由外部注入产生。')
                if node!=ext:
                    raise ValueError(f'发送节点须为本实验的外部业务端（节点 {ext:02d}）：'
                                     f'固件只接受从该节点注入的报文。请把 TX 选成节点 {ext:02d} 再发送。')
                text=str(d.get('text',''))
                with mu:
                    state['biz_seq']=state.get('biz_seq',0)+1;mid=state['biz_seq']
                frames=business_frames(text,mid)
                msg=dict(msg_id=mid,node=node,text=text,frames=frames,total=len(frames))
                try: message_queue.put_nowait(msg)
                except queue.Full: raise ValueError('有报文正在链路上传输，请待其完成后重试')
                return self.json(dict(ok=True,msg_id=mid,node=node,frames=len(frames),status='queued_for_real_link'),202)
            elif path=='/api/config/save':
                config=validate(d.get('config') or {});sha=config_hash(config);file=ROOT/'configs'/('user_'+sha[:16]+'.json');save(file,config)
                return self.json(dict(ok=True,config=config,sha256=sha,path=str(file)))
            elif path=='/api/lab':begin('lab',lab_task,d)
            elif path=='/api/lab/batch':begin('labnoise',lab_batch_task,d)
            elif path=='/api/verify':begin('verify',verify_task)
            elif path=='/api/capacity':begin('capacity',capacity_task)
            else:raise ValueError('未知操作')
            self.json({'ok':True})
        except Exception as e:self.json({'error':str(e)},409 if owner.locked() else 400)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--http',type=int,default=8877);p.add_argument('--port',default='COM4');a=p.parse_args();state['port']=a.port
    print(f'PRODUCT_UI http://127.0.0.1:{a.http} root={ROOT}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.http),Handler).serve_forever()
