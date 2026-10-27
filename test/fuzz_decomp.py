#!/usr/bin/env python3
"""Generate straight-line random STM8 functions for the decompiler fuzz (DecompAll.java).

  fuzz_decomp.py <gh24.txt> <uc.txt> <out-dir> [functions=480] [seed]

Each function is 12 random non-branching instructions (forms from the decode corpus, random operands) and a RET, assembled
with AS at 0x4000 + n * 0x40.  Writes fuzz.bin (image from 0x4000) and entries.txt ("f<n> <hex address>").
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sem_gen as g  # noqa: E402

gh, uc, outdir = sys.argv[1:4]
nfun = int(sys.argv[4]) if len(sys.argv) > 4 else 480
rnd = random.Random(int(sys.argv[5]) if len(sys.argv) > 5 else 1)
outdir = os.path.abspath(outdir)
os.makedirs(outdir, exist_ok=True)
CONTROL = ('jr', 'jp', 'call', 'ret', 'iret', 'int', 'trap', 'btj', 'popw', 'pushw')
forms = [(s, t) for s, (t, ln) in g.forms(gh, uc).items() if ln <= 4 and not t.split()[0].startswith(CONTROL[:-2]) and 'sp' not in t.lower().split()[0]]
lines = ['\tcpu stm8']
for n in range(nfun):
    lines.append(f'\torg\t${0x4000 + n * 0x40:x}')
    lines.append(f'f{n}:')
    for _ in range(12):
        s, t = rnd.choice(forms)
        r = g.instantiate(t, rnd)
        lines.append('\t' + r[0])
    lines.append('\tret')
open(os.path.join(outdir, 'fuzz.asm'), 'w').write('\n'.join(lines) + '\n')
subprocess.run([g.ASL, '-cpu', 'stm8', '-o', os.path.join(outdir, 'fuzz.p'), os.path.join(outdir, 'fuzz.asm')], capture_output=True, cwd=outdir)
subprocess.run([os.environ.get('P2BIN') or os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/asl/bin/p2bin'), os.path.join(outdir, 'fuzz.p'),
                os.path.join(outdir, 'fuzz.bin'), '-r', f'0x4000-0x{0x4000 + nfun * 0x40 - 1:x}'], capture_output=True, cwd=outdir)
open(os.path.join(outdir, 'entries.txt'), 'w').write(''.join(f'f{n} {0x4000 + n * 0x40:x}\n' for n in range(nfun)))
print(nfun, 'functions,', os.path.getsize(os.path.join(outdir, 'fuzz.bin')), 'bytes')
