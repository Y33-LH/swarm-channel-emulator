"""Generate the frozen B-v1 PN convention, not a hand-entered test waveform."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def pn(degree, taps):
    state = (1 << degree)-1
    result=[]
    for _ in range((1 << degree)-1):
        result.append(state & 1)
        feedback=0
        for p in taps: feedback ^= (state >> p)&1
        state=(state >> 1)|(feedback << (degree-1))
    assert state == (1 << degree)-1
    return result
if __name__ == '__main__':
    short=pn(7,[0,3]); training=pn(8,[0,4,5,6])
    preamble=short*2+training+[(0xD391C5A7 >> b)&1 for b in range(31,-1,-1)]+[0]
    assert len(preamble)==542
    (ROOT/'rtl/preamble.mem').write_text(''.join(f'{b:x}\n' for b in preamble),encoding='ascii')
    value=sum(b<<i for i,b in enumerate(preamble))
    (ROOT/'rtl/preamble_constant.vh').write_text(f"localparam [541:0] preamble = 542'h{value:x};\n",encoding='ascii')
    diff=0
    for a,b in zip(short,short[1:]): diff=(diff<<1)|(a^b)
    (ROOT/'rtl/pn_diff.vh').write_text(f"localparam [125:0] PN_DIFF = 126'h{diff:032x};\n",encoding='ascii')
    (ROOT/'reference/preamble.json').write_text(json.dumps({'pn127':short,'training255':training,'preamble':preamble,'diff_hex':hex(diff)}),encoding='ascii')
    print('PREAMBLE_GENERATED symbols=542 PN periods=127,255')
