#!/usr/bin/env python3
"""Assemble the module's disassembly with two independent STM8 assemblers and require the original bytes back.

  asm_roundtrip.py <ghidra.txt> <corpus.bin> [slot-size=8 [ok-slots-out.txt]]

asl = Alfred Arnold's macro assembler AS (cpu STM8), sdas = SDCC's sdasstm8.  Every slot the module decodes becomes
one assembler line at the slot's own address (relative targets are printed as absolute addresses by the module),
assembled by both tools.
Neither assembler can be told to use a long operand form for a small value, so "module long form, value < 256"
is its own class (the assembler chose the shorter encoding; the shorter encoding's bytes are checked by the other
classes).  Output classes: identical, short-form (explained), different, rejected (see the printed examples).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

TOOLS = os.path.expanduser('~/.cache/ghidra-rare-scratch/tools')
ASL = os.environ.get('ASL') or shutil.which('asl') or TOOLS + '/asl/bin/asl'
SDAS = os.environ.get('SDASSTM8') or shutil.which('sdasstm8') or TOOLS + '/sdcc-root/usr/bin/sdasstm8'
BASEADDR = 0x8000
PER = 8192


def convert(t, tool, base):
    m = re.match(r'(\w+)\s*(.*)$', t)
    mn, ops = m.group(1).lower(), m.group(2)
    ops = ops.replace(' ', '')
    if mn.startswith('jr') or mn in ('callr', 'btjt', 'btjf'):
        head, tgt = ops.rsplit(',', 1) if ',' in ops else ('', ops)
        ops = (head + ',' if head else '') + hex((int(tgt, 16) + base) & 0xffffff)
    if tool == 'asl':
        if mn in ('ldf', 'jpf', 'callf'):
            ops = re.sub(r'\[(0x[0-9a-fA-F]+)\]', r'[\1.e]', ops)
        else:
            ops = re.sub(r'\[(0x[0-9a-fA-F]+)\]', r'[\1.w]', ops)
        ops = re.sub(r'0x([0-9a-fA-F]+)', r'$\1', ops)
    return mn, ops


def assemble(todo, tool, slot, tmp):
    """-> {index in todo: bytes} for the lines the tool accepted"""
    CH = 2000
    out = {}
    for c in range(0, len(todo), CH):
        part = todo[c:c + CH]
        lines = ['\tcpu stm8' if tool == 'asl' else '\t.area CODE (ABS)']
        for i, nn, t in part:
            org = BASEADDR + (i % PER) * slot
            mn, ops = convert(t, tool, BASEADDR)
            lines.append(f'\torg\t${org:x}' if tool == 'asl' else f'\t.org\t0x{org:x}')
            lines.append(f'\t{mn}\t{ops}')
        src = os.path.join(tmp, 'p.asm' if tool == 'asl' else 'p.s')
        open(src, 'w').write('\n'.join(lines) + '\n')
        got = {}
        if tool == 'asl':
            subprocess.run([ASL, '-L', '-q', '-cpu', 'stm8', src], capture_output=True, text=True, cwd=tmp)
            for l in open(os.path.join(tmp, 'p.lst'), errors='replace'):
                m = re.match(r'\s*(\d+)/\s*[0-9A-F]+ : ((?:[0-9A-F]{2} )+)', l)
                if m:
                    got.setdefault(int(m.group(1)), bytearray()).extend(bytes.fromhex(m.group(2).replace(' ', '')))
        else:
            subprocess.run([SDAS, '-l', '-o', src], capture_output=True, text=True, cwd=tmp)
            for l in open(os.path.join(tmp, 'p.lst'), errors='replace'):
                m = re.match(r'\s{6}[0-9A-F]{6} ((?:[0-9A-F]{2} )+)\s*(?:\[\s*\d+\])?\s+(\d+)\s', l)
                if m:
                    got.setdefault(int(m.group(2)), bytearray()).extend(bytes.fromhex(m.group(1).replace(' ', '')))
        for k in range(len(part)):
            if 3 + 2 * k in got:
                out[c + k] = bytes(got[3 + 2 * k])
    return out


def judge(g, want, t):
    if g is None:
        return 'rejected'
    if g == want:
        return 'identical'
    if len(g) < len(want) and re.search(r'0x0*[0-9a-f]{1,2}\b', t):
        return 'short-form'
    return 'different'


def main():
    gh = [l.rstrip('\n').split(' ', 2) for l in open(sys.argv[1]) if not l.startswith('    ')]
    data = open(sys.argv[2], 'rb').read()
    slot = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    todo = [(int(i), int(n), t) for i, n, t in gh if t != 'BAD']
    tmp = tempfile.mkdtemp(prefix='asmrt.', dir=os.environ.get('TMPDIR', '/tmp'))
    res = {tool: assemble(todo, tool, slot, tmp) for tool in ('asl', 'sdas')}
    okslots = []
    cnt = Counter()
    cls = Counter()
    exm = {}
    for k, (i, n, t) in enumerate(todo):
        want = bytes(data[i * slot:i * slot + n])
        ra = judge(res['asl'].get(k), want, t)
        rs = judge(res['sdas'].get(k), want, t)
        if 'identical' in (ra, rs):
            okslots.append(i)
            key = 'identical in both' if ra == rs else ('identical in sdasstm8 only' if rs == 'identical' else 'identical in asl only')
        elif 'short-form' in (ra, rs):
            key = 'short-form (assembler picked the shorter encoding)'
        else:
            key = 'NEITHER assembler reproduces the bytes'
        cnt[key] += 1
        if key != 'identical in both':
            shape = key + ' | ' + re.sub(r'0x[0-9a-f]+', 'N', t) + ' (%d bytes)' % n
            cls[shape] += 1
            if shape not in exm:
                ga, gs = res['asl'].get(k), res['sdas'].get(k)
                exm[shape] = f'slot {i}: {t} | asl {ga.hex() if ga else "-"} sdas {gs.hex() if gs else "-"} module {want.hex()}'
    shutil.rmtree(tmp)
    if len(sys.argv) > 4:
        open(sys.argv[4], 'w').write('\n'.join(map(str, okslots)) + '\n')
    for k, v in cls.most_common(80):
        print(f'   {v:6d}  {k}   e.g. {exm[k]}')
    for k, v in sorted(cnt.items()):
        print(f'   {k:60s} {v}')
    sys.exit(1 if cnt['NEITHER assembler reproduces the bytes'] else 0)


if __name__ == '__main__':
    main()
