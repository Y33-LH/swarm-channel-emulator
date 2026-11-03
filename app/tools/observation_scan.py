"""Keep selected DATA frames and validate the independent board IQ bank."""
import base64

def attach_bank(snapshot, bank):
    for key in ('run_id', 'round', 'watch_link'):
        if bank[key] != snapshot[key]:
            raise ValueError(f'WALLIQ snapshot mismatch: {key}')
    seen = set()
    end_ms = snapshot['round'] * 100
    for link, ms, generation, packed in bank['cells']:
        if link in seen or not 0 <= link < 16 or not 0 <= ms <= end_ms or not 0 <= generation <= 0xffffffff:
            raise ValueError('Invalid uplink IQ identity')
        seen.add(link)
        size = len(base64.b64decode(packed, validate=True))
        if size % 8 or size > 16 * 8:
            raise ValueError('Invalid receiver IQ pair count')
    for ms, *gains in bank['tap_history']:
        if not 0 <= ms <= end_ms or not 1 <= len(gains) <= 8:
            raise ValueError('Invalid observed tap history')
    snapshot['wall_iq'] = bank['cells']
    snapshot['tap_history'] = bank['tap_history']

def retain(cache, observation, snapshot):
    current={str(k):v for k,v in cache.items() if
        v.get('run_id')==snapshot.get('run_id') and
        v.get('config_id')==snapshot.get('config_id') and
        v.get('channel_id')==snapshot.get('channel_id') and
        v.get('model_ms',0)<=snapshot['round']*100}
    if observation:
        current[str(observation['link_id'])]=observation
    return current
