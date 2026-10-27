#!/usr/bin/env python3
"""Disassemble every 8-byte slot of a corpus with uCsim's STM8 simulator (sstm8, run as a black box).

  ucsim_stream.py <corpus.bin> <out.txt> [jobs]

Each 64 KB piece (8192 slots) is loaded as Intel hex at 0x8000 (flash) and every slot is disassembled with
`dc <addr> <addr>` (one instruction).  Output, one line per slot: "<slot> <length> <text>"
(length 0 and text 'UNKNOWN' when uCsim rejects the opcode).
Environment: UCSIM_STM8 (default: ~/.cache/ghidra-rare-scratch/tools/sdcc-root/usr/bin/ucsim_stm8).
"""
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

UCSIM = os.environ.get('UCSIM_STM8') or os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/sdcc-root/usr/bin/ucsim_stm8')
SLOT = 8
PER = 65536 // SLOT


BASE = 0x8000          # flash: the only flat, writable-by-load, 128 KB area of the simulated STM8


def ihex(data):
    out = []
    hi = None
    for i in range(0, len(data), 16):
        c = data[i:i + 16]
        a = BASE + i
        if a >> 16 != hi:
            hi = a >> 16
            b = bytes([2, 0, 0, 4, hi >> 8, hi & 255])
            out.append(':' + (b + bytes([(-sum(b)) & 255])).hex().upper())
        b = bytes([len(c), a >> 8 & 255, a & 255, 0]) + c
        out.append(':' + (b + bytes([(-sum(b)) & 255])).hex().upper())
    out.append(':00000001FF')
    return '\n'.join(out) + '\n'


LINE = re.compile(r'0x([0-9a-f]+)\s+\S?\s*((?:[0-9a-f]{2} )+)\s*(.*?)(?:\x1b\[0K)?$')


def piece(args):
    k, data, tmp = args
    hx = os.path.join(tmp, f'p{k}.hex')
    open(hx, 'w').write(ihex(data))
    n = len(data) // SLOT
    res = {}
    for s0 in range(0, n, 1024):       # -e takes the commands as one argument: keep it short
        cmds = ';'.join(f'dc {BASE + i * SLOT} {BASE + i * SLOT}' for i in range(s0, min(n, s0 + 1024)))
        r = subprocess.run([UCSIM, '-e', cmds, hx], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors='replace')
        for l in r.stdout.split('\n'):
            m = LINE.match(l.rstrip('\r'))
            if m:
                a = int(m.group(1), 16)
                by = m.group(2).split()
                res[(a - BASE) // SLOT] = (len(by), m.group(3).strip())
    lines = []
    for i in range(n):
        ln, t = res.get(i, (0, 'MISSING'))
        if t.startswith('UNKNOWN'):
            ln, t = 0, 'UNKNOWN'
        lines.append(f'{k * PER + i} {ln} {t}\n')
    return lines


def main():
    data = open(sys.argv[1], 'rb').read()
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    tmp = tempfile.mkdtemp(prefix='ucsim.', dir=os.environ.get('TMPDIR', '/tmp'))
    pieces = [(k, data[o:o + 65536], tmp) for k, o in enumerate(range(0, len(data), 65536))]
    with ThreadPoolExecutor(jobs) as ex, open(sys.argv[2], 'w') as out:
        for lines in ex.map(piece, pieces):
            out.writelines(lines)
    import shutil
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
