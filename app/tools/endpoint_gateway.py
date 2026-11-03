"""External-node protocol boundary. Software tests never imply a second board exists.

The PC clock-master issues SYNC at a paused ARM batch boundary. An endpoint
responds at exactly that model time. Wall-time messages cannot be silently
treated as accelerated simulation time. Physical transports are attached later.
"""
import re,struct

class EndpointGateway:
    def __init__(self,node,run_id,physical=False):
        if type(node)!=int or not 1<=node<=16:raise ValueError('endpoint node must be 1..16')
        self.node=node;self.run_id=run_id;self.physical=bool(physical);self.identity=None;self.sequence=-1
    def register(self,message):
        if set(message)!={'v','type','node','identity','capabilities'} or message['v']!=1 or message['type']!='HELLO' or message['node']!=self.node:raise ValueError('invalid registration')
        if not isinstance(message['identity'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',message['identity']):raise ValueError('invalid identity')
        caps=message['capabilities']
        if not isinstance(caps,list) or not caps or any(x not in ('heartbeat','alarm','bytes','command_result') for x in caps):raise ValueError('unsupported capabilities')
        self.identity=message['identity'];self.sequence=-1
        return dict(v=1,type='REGISTERED',node=self.node,run_id=self.run_id,source='physical_transport' if self.physical else 'software_protocol_test')
    def sync(self,model_ms):
        if self.identity is None:raise ValueError('not registered')
        return dict(v=1,type='SYNC',run_id=self.run_id,model_ms=model_ms,clock='model_ms',node=self.node)
    def accept(self,message,model_ms):
        required={'v','type','node','identity','run_id','model_ms','sequence','kind','payload_hex'}
        if set(message)!=required or self.identity is None:raise ValueError('invalid endpoint frame')
        if message['v']!=1 or message['type']!='DATA' or message['node']!=self.node or message['identity']!=self.identity or message['run_id']!=self.run_id:raise ValueError('endpoint/run mismatch')
        seq=message['sequence']
        if type(seq)!=int or not 0<=seq<2**32 or seq<=self.sequence:raise ValueError('stale or repeated sequence')
        if type(message['model_ms'])!=int or message['model_ms']!=model_ms:raise ValueError('wrong model clock; wait for SYNC')
        kind=message['kind'];raw=message['payload_hex']
        if kind not in (1,2,5) or not isinstance(raw,str) or not re.fullmatch(r'(?:[0-9a-f]{2}){1,64}',raw):raise ValueError('invalid payload')
        payload=bytes.fromhex(raw)
        if kind==1:
            if len(payload)!=16:raise ValueError('heartbeat length')
            x,y,z,tick=struct.unpack('<4i',payload)
            if not 0<=x<=10000000 or not 0<=y<=10000000 or not 50000<=z<=900000 or tick!=model_ms//100:raise ValueError('invalid heartbeat position/time')
        self.sequence=seq
        return dict(command=f'EXTINJECT {self.node} {kind} {raw}',endpoint_sequence=seq,run_id=self.run_id,
                    model_ms=model_ms,source='physical_transport' if self.physical else 'software_protocol_test',
                    status='validated_not_delivered')
    def disconnect(self):self.identity=None
