"""Actual board/network acceptance. All results and media are read over UART.
No simulator fallback; no TX byte is used to repair received media.
"""
import argparse,hashlib,json,sys,time,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
import serial
from serial_json import JsonSerial
from product_scene import channel,position
from product_config import validate,encode,config_hash,wire_id
import channel_config
from firmware_contract import VERSION,PROTOCOL,BUILD
from media_stream import Stream
from observation_scan import attach_bank

def _sanitize(s):
    """Validate without rewriting received data.

    FPGA endpoints deliberately start sequence counters at 0x80000000; they
    are valid uint32 identities, not overflow sentinels. Preserve raw evidence.
    """
    for row in s.get('nodes',[]):
        if len(row)!=11 or not all(isinstance(v,int) for v in row):
            raise ValueError('Invalid node telemetry shape/type')
        if not 1<=row[0]<=16 or not 0<=row[8]<=0xffffffff:
            raise ValueError('Invalid node identity or uint32 sequence')
    return s

def run(port='COM4',seconds=900,ideal=0,seed=20261009,output=None,progress=None,cancel=None,config=None,control=None,batch=200,strict=True,intervention=False,continuous=False,finish=None,repeat_media=False,stop_round=None):
    out=Path(output) if output else ROOT/'results'/time.strftime('network_%Y%m%d_%H%M%S')
    out.mkdir(parents=True,exist_ok=True);transcript=(out/'uart.jsonl').open('w',encoding='utf-8');snaplog=(out/'snapshots.jsonl').open('w',encoding='utf-8')
    started=time.monotonic();snapshots=[];config=validate(config or {});assert 1<=batch<=200;manifest=json.loads((ROOT/'media/source_manifest.json').read_text())
    release=json.loads((ROOT/'release.json').read_text(encoding='utf-8-sig'))
    image_hashes={k:hashlib.sha256((ROOT/release[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s:
        s.reset_input_buffer();client=JsonSerial(s,max_line=32768,on_error=lambda r:(out/'serial_failure.json').write_text(json.dumps(r,indent=2)))
        def cmd(text,timeout=20,allow_missing=False,allow_reject=False):
            r=client.request(text,timeout);transcript.write(json.dumps({'wall_s':time.monotonic()-started,'command':text,'response':r})+'\n');transcript.flush()
            assert r.get('ok')==1 or allow_reject or (allow_missing and r.get('error')=='MISSING_RECEIVED_FRAGMENT'),(text,r)
            return r
        ping=cmd('PING');assert ping['version']==VERSION and ping['protocol']==PROTOCOL and ping['arm_build']==BUILD
        if intervention:assert ping.get('intervention_schema')==1,'Load intervention firmware first'
        cmd('LINKOBS 1')  # All pages consume the same captured DATA frame.
        memory_before=cmd('MEMORY')
        cmd('NETSTOP');applied=cmd('SCENECFG '+encode(config).hex());assert applied['config_id']==wire_id(config);cmd('NETACKDROP 0');cmd('NETFEC 1');cmd('NETLOAD 0')
        channel_config.configure(cmd,config.get('channel'))
        for t in (0,334,670,710,899):
            for link in (0,3,11,19,27):
                c=channel(link,t,20261009,config,protocol=ping['protocol']);r=cmd(f'SCENE {link} {t*1000}')
                assert abs(r['distance_mm']-round(c['distance_m']*1000))<=1,(c,r)
                assert abs(r['cfo_millihz']-round(c['cfo_hz']*1000))<=2,(c,r)
                assert abs(r['sigma']-round(c['sigma']))<=1 and r['seed']==c['noise_seed'],(c,r)
                assert abs(r['gain0_q15']-round(min(1,c['gain0'])*32768))<=1,(c,r)
                assert abs(r['gain1_q15']-round(min(1,c['gain1'])*32768))<=1,(c,r)
                assert r['delay_samples']==round(c['delay_samples']),(c,r)
        media={3:(ROOT/'media'/manifest['audio']['file']).read_bytes(),4:(ROOT/'media'/manifest['video']['file']).read_bytes()}
        cmd(f'MEDIACLEAR {len(media[3])} {len(media[4])}')
        for kind,data in media.items():
            for off in range(0,len(data),192):cmd(f'MEDIASET {kind} {off} {data[off:off+192].hex()}')
        start=cmd(f'NETSTART {0 if continuous else seconds} {seed} {ideal}');actual_start=time.monotonic();stream=Stream(out,media) if repeat_media else None;stopping=False
        while True:
            if cancel and cancel() and not continuous:cmd('NETSTOP');raise InterruptedError('Run stopped; no acceptance result published')
            # ARM still executes every 0.1 s communication round. Transfer one
            # cumulative snapshot per 20 model seconds to avoid UART overhead.
            if control:control(cmd,snapshots[-1] if snapshots else None)
            # The FPGA still computes all packets in every 0.1 s round. The
            # applied-register readback (PDP / taps / CFR) is the only evidence
            # that the channel actually moved, so it is sampled on EVERY batch
            # instead of every second batch: the incremental UART cost is ~2.5 KB
            # per batch while the counters block is already sent every batch.
            # Without this the channel charts look frozen for most of a run.
            full=1
            stopping=bool(continuous and ((cancel and cancel()) or (finish and finish()) or (stop_round is not None and snapshots and snapshots[-1]['round']>=stop_round)))
            if stopping:cmd('NETSTOP')
            result=cmd('NETSTATUS' if stopping else f'{"NETSTEP" if full else "NETFAST"} {batch}',timeout=60)
            attach_bank(result,cmd('WALLIQ'))
            result['config']=config
            result['hardware_nodes']=cmd('HNSTATUS')['hardware_nodes']
            audio=cmd('HBAUDIO')
            assert audio['run_id']==result['run_id']
            for node,seq,encoded in audio['samples']:
                assert result['nodes'][node-1][8]==seq and len(bytes.fromhex(encoded))==48
            result['heartbeat_audio']=audio['samples']
            runtime=cmd('SCENERUNTIME')
            assert runtime['run_id']==result['run_id'] and runtime['model_ms']==result['round']*100
            result['scene_runtime']=runtime['runtime']
            result['command_results']=cmd('CMDSTATUS')['commands'] if control else []
            if intervention and result['command_results']:result['command_trace']=cmd('CMDTRACE')
            assert result['config_id']==wire_id(config)
            assert result['type']=='NETWORK' and result['run_id']==start['run_id'] and result['version']==VERSION
            assert result['channel_id']==channel_config.wire_id(config.get('channel'))
            assert not snapshots or result['round']>snapshots[-1]['round'] or (stopping and result['round']==snapshots[-1]['round'])
            assert result['delivered']<=result['generated'];assert all(x[1]<=x[0] and x[2]<=x[1] and x[8]<=x[7] for x in result['links'])
            _sanitize(result)
            if stream and not stopping:stream.collect(result,cmd)
            if stream:
                result['repeat_media']=True;result['media_archive']=stream.objects[-8:];result['media_archive_count']=len(stream.objects)
                result['media_latest_complete']=[next((x for x in reversed(stream.objects) if x['kind']==kind and x['complete']),None) for kind in (3,4)]
            snapshots.append(result);snaplog.write(json.dumps(result)+'\n');snaplog.flush()
            if progress:progress(result)
            else:print(f"NETWORK_PROGRESS sim_s={result['round']/10:.1f} delivered={result['delivered']} media={result['media']}",flush=True)
            if not result['running']:break
        wall=time.monotonic()-actual_start
        assert (continuous or result['round']==seconds*10) and len(result['nodes'])==16 and len(result['links'])==32
        planned_seconds=seconds;seconds=result['round']/10
        assert result['scene_profile']=='full_phy_v1' and result['profile']=='DBPSK_SCR_INT_CONV_TURBO2'
        if strict:assert all(n[9]>0 for n in result['nodes'] if n[0]!=config['external_node']),'Every node must have an actual received heartbeat'
        assert result['slot_misses']==0, f"TDMA slot budget exceeded {result['slot_misses']} times"
        for n in result['nodes']:
            expected=position(n[0],n[10]/1000,seed,config,protocol=result.get('protocol',17))
            if n[9] and not result.get('command_results') and n[0]!=config['external_node']:
                assert all(abs(n[4+i]-round(expected[i]*1000))<=1 for i in range(3)),('Received coordinate does not match source-time reference',n,expected)
        if ideal and seconds<330 and not intervention and not continuous:
            assert result['delivered']==result['generated'] and result['queue_drops']==0 and result['retry_drops']==0,'Ideal admissible workload must deliver every packet'
        received={}
        for kind,name in ((3,'received_audio.wav'),(4,'received_video.webm')):
            index=0 if kind==3 else 2
            complete=result['media'][index]==len(media[kind])
            data=bytearray();fragments=[];missing=[];stride=128 if complete else 64
            for off in range(0,len(media[kind]),stride):
                size=min(stride,len(media[kind])-off)
                r=cmd(f'MEDIAGET {kind} {off} {size}',allow_missing=not complete)
                if r.get('ok')==1:
                    chunk=bytes.fromhex(r['hex']);assert len(chunk)==size
                    # Received fragments are checked; missing data is never filled
                    # from the source or synthesized as zero bytes.
                    assert chunk==media[kind][off:off+size]
                    data.extend(chunk);fragments.append(dict(offset=off,hex=chunk.hex()))
                else:missing.append(dict(offset=off,length=size))
            assert len(data)==result['media'][index], 'Received media map/count mismatch'
            if complete:assert bytes(data)==media[kind],f'Claimed complete media differs from source kind={kind}'
            if strict:assert complete,f'Media incomplete kind={kind}'
            target=name if complete else 'incomplete_'+name+'.json'
            artifact=bytes(data) if complete else json.dumps(dict(expected_bytes=len(media[kind]),received_fragments=fragments,missing_ranges=missing),indent=2).encode()
            (out/target).write_bytes(artifact);received[name]={'complete':complete,'file':target,'bytes':len(data),'received_unique_bytes':result['media'][index],'missing_fragments':len(missing),'sha256':hashlib.sha256(artifact).hexdigest(),'source':'FPGA RX -> ARM hop queues -> ground reassembly -> UART'}
        if received['received_audio.wav']['complete']:
            with wave.open(str(out/'received_audio.wav')) as w:assert w.getnframes()>0 and w.getframerate()==8000
        frames=0
        if received['received_video.webm']['complete']:
            import cv2
            cap=cv2.VideoCapture(str(out/'received_video.webm'))
            while cap.read()[0]:frames+=1
            cap.release();assert frames==20
        if strict and seconds>=720 and config['faults'] and not result.get('command_results'):
            before=next(v for v in snapshots if v['round']>=3300);during=next(v for v in snapshots if v['round']>=3600);after=next(v for v in snapshots if v['round']>=3900)
            assert during['nodes'][1][7]<=330000,'Node 2 must not deliver a new heartbeat during outage'
            assert after['nodes'][1][7]>370000,'Node 2 heartbeat must recover'
            assert sum(x[4] for x in result['links'])>0,'Retry path exercised'
            recovered=next(v for v in snapshots if v['round']>=7400)
            assert recovered['nodes'][11][7]>700000,'Relay 12 must deliver a real heartbeat after degradation ends'
            assert all(seconds*1000-n[7]<10000 for n in result['nodes']),'Final heartbeat recovery missing'
            assert 2 in [a[0] for a in result['alarm_events']] and 4 in [a[0] for a in result['alarm_events']],'Recovery alarms must be actually received'
        command_trace=cmd('CMDTRACE')
        (out/'command_trace.json').write_text(json.dumps(command_trace,indent=2))
        memory_after=cmd('MEMORY');total_wall=time.monotonic()-started
        assert memory_after['stack_guard_ok'] and memory_after['heap_failures']==0,memory_after
        # 内存读数证明的是「安全边界没有被越过」（栈守卫页完好、堆无分配失败），
        # 不是动态占用曲线。两次读数一致并不代表白测，但没有必要让读者误以为
        # 应该看到变化——这里直接写清楚。
        memory_note=('stack/heap 读数来自板上保守边界估计：stack_guard_ok=1 表示栈守卫页完好，'
                     'heap_failures=0 表示全程无分配失败。前后一致说明实验没有逼近边界，'
                     '它证明的是安全性余量，不是动态用量曲线。')
        # 加速与时延的口径必须写进报告，否则「8 倍加速」会被读成「少跑了 8 倍」，
        # 「最大时延 40 秒」会被当成实时链路故障，而它实际来自 60 秒上界的
        # store-and-forward 缓冲设计。
        timing_note=('duration_s 是模型时间；wall_run_seconds 是墙钟。板卡按真实调制/解调节奏'
                     '连续执行 NETFAST 批处理，不省略任何一帧的处理，仿真时间与墙钟之比只反映'
                     '批处理的流水效率。delay_max_ns 含 store-and-forward：链路中断时帧最长'
                     '缓存 60 秒模型时间后仍投递，超出即丢弃并计入 loss_expired。')
        report={'pass':True,'version':f"{ping['version']:08x}",'protocol':result.get('protocol',17),'config':config,'config_sha256':config_hash(config),'config_id':wire_id(config),'duration_s':seconds,'wall_run_seconds':wall,'wall_total_seconds':total_wall,'acceleration':seconds/wall,'seed':seed,'ideal':ideal,'final':result,'media':received,'video_decoded_frames':frames,'memory_before':memory_before,'memory_after':memory_after,'memory_note':memory_note,'timing_note':timing_note,'performance_gates':{'complete_within_120s':total_wall<=120,'delivery_above_99pct':result['delivered']/result['generated']>.99},'required_remaining':[], 'scope':'full-FEC DBPSK; rectangular pulse, pilot CFO, Gardner timing, complex DFE; bounded 60-second store/forward; not a certified channel model'}
        report.update(image_hashes=image_hashes,arm_build=ping['arm_build'],telemetry_rounds=batch,strict_acceptance=strict,continuous=continuous,requested_duration_s=planned_seconds,stop_round=result['round'] if continuous else None,repeat_media=repeat_media,media_objects=stream.objects if stream else [],
                      all_media_complete=all(x['complete'] for x in received.values()),
                      explanation='pass means the experiment and evidence checks completed; delivery and duration gates are separate and can fail for weak or overloaded user scenarios')
        (out/'config.json').write_text(json.dumps(dict(config=config,sha256=config_hash(config),telemetry_rounds=batch),indent=2))
        transcript.flush();snaplog.flush()
        report['evidence_sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('uart.jsonl','snapshots.jsonl')}
        report['source_media_sha256']={manifest[label]['file']:hashlib.sha256(media[kind]).hexdigest() for label,kind in (('audio',3),('video',4))}
        (out/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    transcript.close();snaplog.close();print('HARDWARE_NETWORK_PASS evidence='+str(out),flush=True);return report,out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');p.add_argument('--seconds',type=int,default=900);p.add_argument('--ideal',type=int,default=0);p.add_argument('--seed',type=int,default=20261009);p.add_argument('--out');a=p.parse_args()
    run(a.port,a.seconds,a.ideal,a.seed,a.out)
