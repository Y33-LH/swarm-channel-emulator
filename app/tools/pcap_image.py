"""Derive a Zynq PCAP word stream from the exact release .bit file.

The parser is checked against Xilinx Bootgen 2018.3 -process_bitstream bin.
No cached image from a different release is used by the loading fallback.
"""
from pathlib import Path
import hashlib


def convert(data):
    def length(offset, width):
        if offset + width > len(data):
            raise ValueError('Truncated FPGA bitstream header')
        return int.from_bytes(data[offset:offset+width], 'big')
    magic_len = length(0, 2)
    if data[2:2+magic_len] != bytes.fromhex('0ff00ff00ff00ff000'):
        raise ValueError('Unrecognized Xilinx bitstream header')
    offset = 2 + magic_len
    if length(offset, 2) != 1:
        raise ValueError('Invalid bitstream field marker')
    offset += 2
    fields = {}
    for key in b'abcde':
        if offset >= len(data) or data[offset] != key:
            raise ValueError('Invalid bitstream field order')
        offset += 1
        width = 4 if key == ord('e') else 2
        size = length(offset, width)
        offset += width
        if offset + size > len(data):
            raise ValueError('Truncated bitstream field')
        fields[chr(key)] = data[offset:offset+size]
        offset += size
    if offset != len(data):
        raise ValueError('Unexpected bytes after bitstream payload')
    if not fields['b'].rstrip(b'\0').startswith(b'7z020'):
        raise ValueError('This loader requires a Zynq-7020 bitstream')
    raw = fields['e']
    if len(raw) % 4 or b'\xaa\x99\x55\x66' not in raw[:256]:
        raise ValueError('Invalid FPGA configuration sync/alignment')
    result = bytearray(len(raw))
    for offset in range(0, len(raw), 4):
        result[offset:offset+4] = raw[offset:offset+4][::-1]
    # Bootgen aligns the PCAP DMA stream to 64 bits using a configuration NOP.
    if len(result) % 8:
        result.extend(bytes.fromhex('00000020'))
    return bytes(result)


def derive(bit, destination):
    bit, destination = Path(bit), Path(destination)
    source = bit.read_bytes()
    output = convert(source)
    destination.write_bytes(output)
    return dict(bit_sha256=hashlib.sha256(source).hexdigest(),
                pcap_sha256=hashlib.sha256(output).hexdigest(), bytes=len(output))


if __name__ == '__main__':
    import sys, json
    print(json.dumps(derive(sys.argv[1], sys.argv[2])))
