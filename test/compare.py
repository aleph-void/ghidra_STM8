#!/usr/bin/env python3
"""Compare the module's decode (DumpSlots output) with uCsim's STM8 disassembler (ucsim_stream.py output).

  compare.py <ghidra.txt> <ucsim.txt> [--show N]

Both texts are reduced to a canonical form (lower case, no blanks, numbers as integers, branch targets masked to
16 bits, uCsim's register-name annotations "<pa_odr>" and size suffixes ".w" / ".e" removed).  Classes: agree, both
invalid, length differs, text differs, and one-sided decodes.  Explained classes are listed in EXPLAINED; exit
status 1 if anything else is non-empty.
"""
import re
import sys
from collections import Counter, defaultdict

NUMMASK = 0xffffff          # --mask16: the 16-bit (medium) language cannot show the upper byte of far addresses
ALIAS = {'jrult': 'jrc', 'jruge': 'jrnc', 'jrt': 'jra', 'sla': 'sll', 'slaw': 'sllw'}


def canon(t, base=0, slot=0):      # slot=None: keep branch targets absolute (real code, same addresses)
    t = t.strip()
    if t in ('BAD', 'UNKNOWN'):
        return None
    t = re.sub(r'<[^>]*>', '', t).lower()
    t = re.sub(r'\.[we]\b', '', t)
    t = re.sub(r'\s+', ' ', t)
    m = re.match(r'(\S+)\s*(.*)$', t)
    mn, rest = ALIAS.get(m.group(1), m.group(1)), m.group(2).replace(' ', '')
    rest = re.sub(r'0x([0-9a-f]+)', lambda x: str(int(x.group(1), 16) & NUMMASK), rest)
    if mn in ('jpf', 'callf', 'int') or (mn in ('addw', 'subw') and re.match(r'[xy],#', rest)):
        rest = rest.replace('#', '')        # uCsim prints # on address operands; # on ADDW / SUBW is checked by the assembler round trip
    if mn == 'add' and rest.startswith('sp,'):
        mn = 'addw'
    if slot is not None and (mn.startswith('jr') or mn in ('callr', 'btjt', 'btjf')):        # relative targets: distance from the slot
        a = (slot * 8) % 65536 + base
        rest = re.sub(r'(\d+)$', lambda x: 'rel%d' % ((int(x.group(1)) - a) & 0xffff), rest)
    return mn + ' ' + rest


def main():
    global NUMMASK
    if '--mask16' in sys.argv:
        NUMMASK = 0xffff
    gh = [l.rstrip('\n').split(' ', 2) for l in open(sys.argv[1])]
    uc = [l.rstrip('\n').split(' ', 2) for l in open(sys.argv[2])]
    okset = set(map(int, open(sys.argv[sys.argv.index('--asm-ok') + 1]).read().split())) if '--asm-ok' in sys.argv else set()
    corpus = open(sys.argv[sys.argv.index('--corpus') + 1], 'rb').read() if '--corpus' in sys.argv else b''
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 5
    assert len(gh) == len(uc), (len(gh), len(uc))
    cnt = Counter()
    ex = defaultdict(list)
    for (i, gl, gt), (j, ul, ut) in zip(gh, uc):
        g, u = canon(gt, 0, int(i)), canon(ut, 0x8000, int(i))
        if g is None and u is None:
            k = 'both invalid'
        elif g is None and corpus and corpus[int(i) * 8] == 0x71:
            k = 'uCsim simulator escape 71 xx (halt / putchar pseudo-instructions, no STM8 opcode)'
        elif g is None:
            k = 'uCsim decodes, module rejects'
        elif u is None:
            k = 'module decodes, uCsim rejects'
        elif int(gl) != int(ul):
            k = 'length differs'
        else:
            k = 'agree' if g == u else 'text differs'
        if k not in ('agree', 'both invalid') and int(i) in okset:
            k = 'uCsim differs, an assembler reproduces the module\'s bytes: ' + (re.sub(r'\d+', 'N', g or 'invalid') + ' vs ' + re.sub(r'\d+', 'N', u or 'invalid'))[:70]
        elif k == 'text differs':
            k = 'text differs: ' + re.sub(r'\d+', 'N', g) + '  vs  ' + re.sub(r'\d+', 'N', u)
        cnt[k] += 1
        if len(ex[k]) < show:
            ex[k].append(f'slot {i}: module {gt!r}  uCsim {ut!r}')
    # a leftover whose shape is already confirmed by an assembler in other slots is a case the assemblers cannot produce
    # (a long operand form with a value below 256: they pick the short form)
    conf = {k.split(': ', 1)[1].replace('  vs  ', ' vs ') for k in cnt if k.startswith('uCsim differs, ')}
    for k in list(cnt):
        if k.startswith('text differs: ') and k[len('text differs: '):].replace('  vs  ', ' vs ') in conf:
            cnt['uCsim differs, same shape as slots an assembler reproduces: ' + k[len('text differs: '):].replace('  vs  ', ' vs ')] += cnt.pop(k)
    tot = sum(cnt.values())
    explained = ('agree', 'both invalid') + tuple(EXPLAINED)
    cnt2 = Counter()
    for k, v in cnt.items():
        cnt2[k] += v
    asm_ok = sum(v for k, v in cnt.items() if k.startswith('uCsim differs, '))
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        print(f'   {k:70s} {v:8d}  ({100 * v / tot:.3f}%)')
        if k not in ('agree', 'both invalid'):
            for e in ex[k]:
                print('      ', e)
    bad = sum(v for k, v in cnt.items() if k not in explained and not k.startswith('uCsim differs, '))
    print(f'   (differences confirmed as uCsim errors by an assembler: {asm_ok})')
    print(f'   total {tot}, unexplained differences {bad}')
    sys.exit(1 if bad else 0)


EXPLAINED = {'uCsim simulator escape 71 xx (halt / putchar pseudo-instructions, no STM8 opcode)'}

if __name__ == '__main__':
    main()
