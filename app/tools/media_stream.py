"""Archive independently identified reference clips received through the FPGA.

The source is an uploaded test fixture, NOT a camera/microphone. Serial retrieval
is read-only; compare to TX for validation, never fill a missing fragment from TX.
"""
import hashlib,json
from pathlib import Path

NAMES={3:'received_audio.wav',4:'received_video.webm'}

def capture(command,kind,sequence,expected,out,model_ms):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    data=bytearray();fragments=[];missing=[]
    for offset in range(0,len(expected),64):
        count=min(64,len(expected)-offset)
        r=command(f'MEDIAGET {kind} {offset} {count} {sequence}',allow_missing=True)
        if r.get('ok')==1:
            chunk=bytes.fromhex(r['hex'])
            assert len(chunk)==count and chunk==expected[offset:offset+count], 'Received object bytes differ from source'
            data.extend(chunk);fragments.append(dict(offset=offset,hex=chunk.hex()))
        else:missing.append(dict(offset=offset,length=count))
    complete=not missing
    name=NAMES[kind] if complete else 'incomplete_'+NAMES[kind]+'.json'
    content=bytes(data) if complete else json.dumps(dict(received_fragments=fragments,missing_ranges=missing),indent=2).encode()
    (out/name).write_bytes(content)
    row=dict(kind=kind,object_id=sequence,complete=complete,bytes=len(data),expected_bytes=len(expected),file=name,
             sha256=hashlib.sha256(content).hexdigest(),model_ms=model_ms,missing_fragments=len(missing),
             source='FPGA_RX_GROUND_REASSEMBLY',fixture='Repeated uploaded reference clip; not live sensor data')
    (out/'object.json').write_text(json.dumps(row,indent=2))
    return row

class Stream:
    def __init__(self,out,source):
        self.out=Path(out);self.source=source;self.objects=[];self.seen=set()
    def collect(self,snapshot,command):
        for kind,seq,sent,total,pending in snapshot.get('media_objects',[]):
            if not total or sent!=total or pending or (kind,seq) in self.seen:continue
            folder=self.out/'media_objects'/f'{kind}_{seq:08x}'
            row=capture(command,kind,seq,self.source[kind],folder,snapshot['round']*100)
            row['path']=str((folder/row['file']).relative_to(self.out)).replace('\\','/')
            assert row['bytes']==snapshot['media'][0 if kind==3 else 2], 'RX map/count mismatch'
            self.objects.append(row);self.seen.add((kind,seq))
            with (self.out/'media_objects.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            # No in-flight old frame can be overwritten; firmware checks this too.
            r=command(f'MEDIAADVANCE {kind} {seq}')
            assert r['object_id']==seq+2
        snapshot['repeat_media']=True
        snapshot['media_archive']=self.objects[-8:]
        snapshot['media_latest_complete']=[next((x for x in reversed(self.objects) if x['kind']==kind and x['complete']),None) for kind in (3,4)]
        snapshot['media_archive_count']=len(self.objects)
