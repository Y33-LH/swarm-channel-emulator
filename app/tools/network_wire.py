"""Lossless compact cumulative telemetry; no synthesis of missing measurements."""
import base64, struct

def expand_network(obj):
    if obj.get('type') != 'NETWORK':
        return obj
    if 'applied_data' in obj:
        if obj.get('applied_codec')!='le32-32x15-v1' or obj.get('applied_links'):
            raise ValueError('Invalid applied-channel telemetry envelope')
        raw=base64.b64decode(obj['applied_data'],validate=True)
        if len(raw)!=32*15*4:raise ValueError('Invalid applied-channel byte count')
        obj['applied_links']=[list(x) for x in struct.iter_unpack('<15I',raw)]
        del obj['applied_data'];del obj['applied_codec']
    if 'links_data' in obj:
        if obj.get('links_codec') != 'uvarint-32x21-v1' or obj.get('links'):
            raise ValueError('Invalid link telemetry envelope')
        raw=base64.b64decode(obj['links_data'],validate=True)
        if len(raw)>6720:raise ValueError('Link telemetry too large')
        values=[];value=shift=0
        for byte in raw:
            if shift>63 or (shift==63 and byte>1):raise ValueError('Counter overflow')
            value|=(byte&127)<<shift
            if byte&128:shift+=7
            else:
                if shift and byte==0:raise ValueError('Noncanonical integer')
                values.append(value);value=shift=0
        if shift or len(values)!=32*21:raise ValueError('Incomplete link telemetry')
        if any(x>0xffffffff for i,x in enumerate(values) if i%21!=10):raise ValueError('32 bit counter overflow')
        obj['links']=[values[i:i+21] for i in range(0,len(values),21)]
        del obj['links_data'];del obj['links_codec']
    if 'watch_iq_data' in obj:
        if obj.get('watch_iq_codec')!='le32-pairs-v1' or obj.get('watch_iq'):
            raise ValueError('Invalid IQ telemetry envelope')
        raw=base64.b64decode(obj['watch_iq_data'],validate=True)
        if len(raw)%8 or len(raw)>512:raise ValueError('Invalid IQ byte count')
        obj['watch_iq']=[list(x) for x in struct.iter_unpack('<II',raw)]
        del obj['watch_iq_data'];del obj['watch_iq_codec']
    return obj
