#!/usr/bin/env python3
"""Compare the module's disassembly of a real program with uCsim's, instruction by instruction, at the same addresses.

  real_compare.py <ghidra-listing.txt> <program.ihx> [--rst <sdas listing>]

The listing is RealCheck.java's ("<hex address> <length> <text>").  uCsim loads the Intel hex file of the same link and
disassembles each address (`dc a a`).  With --rst, the instruction lengths are also checked against SDCC's assembler
listing (sdas .rst files, the author's own assembler output).
"""
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare  # noqa: E402
from compare import canon  # noqa: E402

compare.NUMMASK = 0xffff      # the 16-bit language cannot show the upper byte of far addresses; this check compares low 16 bits
# uCsim errors confirmed by two assemblers in the exhaustive decode test (GHIDRA-RARE.md): wrong operand / opcode text
UCSIM_BUGS = re.compile(r'^(bcpl|bccm) |^addw y,\(\d+,sp\)$|^(subw [xy],\d+|ldw y,\[\d+\]|ldw \[\d+\],y|ldf \[\d+\],a)$')

UCSIM = os.environ.get('UCSIM_STM8') or os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/sdcc-root/usr/bin/ucsim_stm8')
LINE = re.compile(r'0x([0-9a-f]+)\s+\S?\s*((?:[0-9a-f]{2} )+)\s*(.*?)(?:\x1b\[0K)?$')


def main():
    # addresses below 0x8000 are RAM (the ELF sections of variables), not code: Ghidra disassembles them as zeros
    lst = [l.split(' ', 2) for l in open(sys.argv[1]).read().split('\n') if l.strip() and int(l.split(' ')[0], 16) >= 0x8000]
    ihx = sys.argv[2]
    got = {}
    for c in range(0, len(lst), 1000):
        part = lst[c:c + 1000]
        cmds = ';'.join(f'dc {int(a, 16)} {int(a, 16)}' for a, _, _ in part)
        out = subprocess.run([UCSIM, '-e', cmds, ihx], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             errors='replace').stdout
        for l in out.split('\n'):
            m = LINE.match(l.rstrip('\r'))
            if m:
                got[int(m.group(1), 16)] = (len(m.group(2).split()), m.group(3).strip())
    cnt = Counter()
    ex = {}
    for a, n, t in lst:
        ua = got.get(int(a, 16))
        g = canon(t, 0, None)
        if ua is None:
            k = 'uCsim gives nothing'
        else:
            u = canon(ua[1], 0, None) if not ua[1].startswith('UNKNOWN') else None
            if g == u and int(n) == ua[0]:
                k = 'agree'
            elif g and UCSIM_BUGS.match(g):
                k = 'agree (known uCsim error, assembler-confirmed)'
            elif u is None:
                k = 'uCsim: invalid'
            else:
                k = 'differs: ' + re.sub(r'\d+', 'N', g or '?') + '  vs  ' + re.sub(r'\d+', 'N', u)
        cnt[k] += 1
        ex.setdefault(k, f'{a}: module {t!r} uCsim {ua}')
    print(f'   instructions {len(lst)}')
    for k, v in cnt.most_common():
        print(f'   {k:70s} {v}' + ('' if k == 'agree' else '   e.g. ' + ex[k]))
    if '--rst' in sys.argv:
        rst = {}
        for f in sys.argv[sys.argv.index('--rst') + 1:]:
            for l in open(f, errors='replace'):
                m = re.match(r'\s{6}([0-9A-F]{6}) ((?:[0-9A-F]{2} )+)\s*\[\s*\d+\]', l)
                if m:
                    rst[int(m.group(1), 16)] = len(m.group(2).split())
        ok = bad = 0
        for a, n, t in lst:
            if int(a, 16) in rst:
                if rst[int(a, 16)] == int(n):
                    ok += 1
                else:
                    bad += 1
                    print('   length differs from the SDCC listing at', a, t)
        print(f'   SDCC assembler listing: {ok} instructions with the same length, {bad} different')
    sys.exit(1 if any(k.startswith('differs') or k == 'uCsim gives nothing' for k in cnt) else 0)


if __name__ == '__main__':
    main()
