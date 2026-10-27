#!/usr/bin/env python3
"""Assemble the STM8 p-code test sequences of emu_cases.py and write emu.bin + tests.txt.

  emu_tests.py <workdir>

Each case is a short instruction sequence with initial registers / memory and the registers, flags and
memory it must leave, worked out by hand from the manual (never from the module's output).  The sequences
are assembled with the AS macro assembler (cpu STM8) at BASE + n*STRIDE.  A line starting with '@raw ' is emitted as bytes.
EmuCheck.java runs them in Ghidra's emulator.

Environment: ASL / P2BIN override the tools (default: asl and p2bin on PATH).
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emu_cases  # noqa: E402

BASE = 0x2000
STRIDE = 0x40
ASL = os.environ.get('ASL') or shutil.which('asl') or os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/asl/bin/asl')
P2BIN = os.environ.get('P2BIN') or shutil.which('p2bin') or os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/asl/bin/p2bin')


def main():
    work = os.path.abspath(sys.argv[1])
    os.makedirs(work, exist_ok=True)
    cases = emu_cases.CASES
    lines = ['\tcpu\tstm8']
    renames = []
    for n, (name, asm, init, expect) in enumerate(cases):
        lines.append(f'\torg\t${BASE + n * STRIDE:x}')
        lines.append(f't{n:04d}:')
        body = [l.strip() for l in asm.strip('\n').split('\n') if l.strip()]
        labels = [m.group(1) for l in body for m in [re.match(r'(\w+):', l)] if m]
        ren = {lab: f'{lab}_{n}' for lab in labels}
        renames.append(ren)

        def fix(text, ren=ren):
            return re.sub(r'\b\w+\b', lambda m: ren.get(m.group(0), m.group(0)), text)
        for l in body:
            if l.startswith('@raw '):
                lines.append('\tdc.b\t' + ','.join('$' + b for b in l[5:].split()))
            else:
                lines.append('\t' + fix(l) if not re.match(r'\w+:', l) else fix(l))
        lines.append(f't{n:04d}_end:')
        lines.append('\tnop')
    src = os.path.join(work, 'emu.asm')
    open(src, 'w').write('\n'.join(lines) + '\n')
    r = subprocess.run([ASL, '-cpu', 'stm8', '-L', '-o', os.path.join(work, 'emu.p'), src], capture_output=True, text=True, cwd=work)
    out = r.stdout + r.stderr
    if ' 0 errors' not in out and '0 errors' not in out:
        print(out[-3000:])
        sys.exit(1)
    end = BASE + len(cases) * STRIDE
    subprocess.run([P2BIN, os.path.join(work, 'emu.p'), os.path.join(work, 'emu.bin'), '-r', '0x0-0x7fff'],
                   check=True, capture_output=True)
    lst = open(os.path.join(work, 'emu.lst')).read()
    sym = {}
    for m in re.finditer(r'(\b\w+)\s*:\s*([0-9A-F]+)\s+C', lst):
        sym[m.group(1).lower()] = int(m.group(2), 16)

    def subst(text, n, s, e):
        text = text.replace('@END@', f'{e:x}')
        text = re.sub(r'@(\w+)>>8@', lambda m: f'{sym[(renames[n].get(m.group(1), m.group(1))).lower()] >> 8:x}', text)
        return re.sub(r'@(\w+)@', lambda m: f'{sym[(renames[n].get(m.group(1), m.group(1))).lower()]:x}', text)

    with open(os.path.join(work, 'tests.txt'), 'w') as f:
        for n, (name, asm, init, expect) in enumerate(cases):
            s, e = sym[f't{n:04d}'], sym[f't{n:04d}_end']
            f.write(f'{name} {s:x} {e:x} {subst(init, n, s, e) or "-"} {subst(expect, n, s, e) or "-"}\n')
    print(f'{len(cases)} cases assembled')


if __name__ == '__main__':
    main()
