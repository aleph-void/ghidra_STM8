#!/usr/bin/env python3
"""Random single-instruction state tests: uCsim's STM8 simulator (black box) against the module's p-code.

  sem_gen.py gen <ghidra.txt> <ucsim.txt> <corpus.bin> <out-dir> [tests-per-form] [seed]   -> tests.txt (SemCheck input)

* the instruction forms are the ones both disassemblers agree on (compare.py's "agree" class); every operand of a form
  is replaced by random values that keep every effective address inside RAM 0x0000-0x0fff (pointers are initialised),
  the form is assembled with AS (cpu STM8) at 0x1000
* uCsim executes the instruction from random A, X, Y, SP, CC and a random 4 KB RAM image; its final registers, PC and
  RAM are the expectation for SemCheck.java (one emulator step of the module's p-code at 0x1000)
Forms whose uCsim decode is known to be wrong (see GHIDRA-RARE.md) are not run against uCsim.
"""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import canon  # noqa: E402

TOOLS = os.path.expanduser('~/.cache/ghidra-rare-scratch/tools')
ASL = os.environ.get('ASL') or shutil.which('asl') or TOOLS + '/asl/bin/asl'
UCSIM = os.environ.get('UCSIM_STM8') or TOOLS + '/sdcc-root/usr/bin/ucsim_stm8'
CODE = 0x1000
PCMASK = int(os.environ.get('PCMASK', '0xffffff'), 16)       # the 16-bit (medium) language keeps no PC extension byte
WIN = 0x1000
SKIP = {'halt', 'wfi', 'wfe', 'break', 'trap', 'putchar', 'jril', 'jrih'}      # hardware inputs and states: hand-computed cases


def shape_of(t):
    return re.sub(r'0x[0-9a-f]+', lambda m: 'N%d' % len(m.group(0)[2:]), re.sub(r'<[^>]*>', '', t)).replace(' ', '')


def forms(gh_path, uc_path):
    out = {}
    for lg, lu in zip(open(gh_path), open(uc_path)):
        i, gl, gt = lg.rstrip('\n').split(' ', 2)
        _, ul, ut = lu.rstrip('\n').split(' ', 2)
        g, u = canon(gt, 0, int(i)), canon(ut, 0x8000, int(i))
        if g is None or g != u or int(gl) != int(ul):
            continue
        mn = ut.split()[0]
        if mn in SKIP:
            continue
        out.setdefault(shape_of(ut), (re.sub(r'<[^>]*>', '', ut).strip(), int(gl)))
    return out


def rnd_ptr(rnd, w, kind):
    if kind == 'zp':
        return rnd.randrange(0, 0xf0)
    return rnd.randrange(0x100, 0xf00)


def instantiate(text, rnd):
    """-> (asl text, [(addr, bytes) pointer initialisations]) or None"""
    mn = text.split()[0]
    ops = text[len(mn):].strip()
    fixes = []
    idx = 'x' in ops.lower().replace('xl', '').replace('xh', '') or 'y' in ops.lower().replace('yl', '').replace('yh', '')

    def num(m):
        tok = m.group(0)
        w = len(tok) - 2
        s, e = m.start(), m.end()
        before = ops[:s]
        after = ops[e:]
        if before.endswith('#'):                       # immediate
            return '$%0*x' % (w, rnd.randrange(0, 1 << (4 * w)))
        in_br = before.count('[') > before.count(']')
        in_par = before.count('(') > before.count(')')
        if mn.startswith('jr') or mn == 'callr' or (mn in ('btjt', 'btjf') and not after.startswith(',#') and before.endswith(',')):
            return '$%x' % (CODE + 2 + rnd.randrange(0, 0x20))
        if in_br:
            far = after.startswith('.e')
            p = rnd_ptr(rnd, w, 'zp' if w == 2 else 'abs')
            lim = 0x400 if re.match(r'\)?,', after[after.find(']') + 1:]) or '],' in after else 0x900
            val = rnd.randrange(0x100, lim)
            fixes.append((p, bytes([0, val >> 8, val & 255]) if far else bytes([val >> 8, val & 255])))
            return '$%0*x' % (w, p)
        if in_par and (after.startswith(',x') or after.startswith(',y') or after.startswith(',X') or after.startswith(',Y')):
            if w == 2:
                return '$%02x' % rnd.randrange(0, 0x80)
            if w == 4:
                return '$%04x' % rnd.randrange(0x100, 0x400)
            return '$%06x' % rnd.randrange(0x100, 0x400)
        if in_par and (after.startswith(',SP') or after.startswith(',sp')):
            return '$%02x' % rnd.randrange(0, 0x40)
        if mn in ('jp', 'call', 'jpf', 'callf', 'int'):
            return '$%0*x' % (w, 0x2000 + rnd.randrange(0, 0x800))
        if w == 2:
            return '$%02x' % rnd.randrange(0, 0xf0)
        if w == 4:
            return '$%04x' % rnd.randrange(0x100, 0x900)
        return '$%06x' % rnd.randrange(0x100, 0x900)
    new = re.sub(r'0x[0-9a-f]+', num, ops)
    return mn + ' ' + new, fixes


def assemble(items, tmp, tag):
    """items: list of asl lines -> list of bytes"""
    src = os.path.join(tmp, tag + '.asm')
    lines = ['\tcpu stm8']
    for k, t in enumerate(items):
        lines.append(f'\torg\t${CODE:x}')
        lines.append('\t' + t)
    open(src, 'w').write('\n'.join(lines) + '\n')
    subprocess.run([ASL, '-L', '-q', '-cpu', 'stm8', src], capture_output=True, text=True, cwd=tmp)
    got = {}
    for l in open(os.path.join(tmp, tag + '.lst'), errors='replace'):
        m = re.match(r'\s*(\d+)/\s*[0-9A-F]+ : ((?:[0-9A-F]{2} )+)', l)
        if m:
            got.setdefault(int(m.group(1)), bytearray()).extend(bytes.fromhex(m.group(2).replace(' ', '')))
    return [bytes(got[3 + 2 * k]) if 3 + 2 * k in got else None for k in range(len(items))]


def ihex(data, base):
    out = []
    for i in range(0, len(data), 16):
        c = data[i:i + 16]
        a = base + i
        b = bytes([len(c), a >> 8 & 255, a & 255, 0]) + c
        out.append(':' + (b + bytes([(-sum(b)) & 255])).hex().upper())
    out.append(':00000001FF')
    return '\n'.join(out) + '\n'


def run_ucsim(test, tmp, tag):
    mem = bytearray(test['mem'])
    for a, b in test['fix']:
        mem[a:a + len(b)] = b
    mem[CODE - 0:CODE] = b''
    hx = os.path.join(tmp, tag + '.hex')
    open(hx, 'w').write(ihex(bytes(mem), 0) .replace(':00000001FF\n', '') + ihex(test['code'], CODE))
    # the console (stdin) runs the commands in order; -e would print the dump before the step has executed
    cmds = (f"set memory regs8 0 {test['A']:#x} {test['CC']:#x}\nset memory regs16 0 {test['X']:#x} {test['Y']:#x} {test['SP']:#x}\n"
            f"pc {CODE:#x}\nstep\ninfo registers\ndump rom 0 {WIN - 1:#x}\nquit\n")
    try:
        r = subprocess.run([UCSIM, '-c', '-', hx], input=cmds, capture_output=True, text=True, errors='replace', timeout=60)
    except subprocess.TimeoutExpired:
        return None
    out = r.stdout
    m = re.search(r'Stop at 0x([0-9a-f]+)', out)
    f = re.findall(r'Flags= 0x([0-9a-f]+)\s+\d+.*?A= 0x([0-9a-f]+)', out)
    xy = re.findall(r'X= 0x([0-9a-f]+)\s+\d+ .*?Y= 0x([0-9a-f]+)', out)
    sp = re.findall(r'SP= 0x([0-9a-f]+)', out)
    if not (m and f and xy and sp):
        return None
    memo = bytearray(WIN)
    seen = 0
    for mm in re.finditer(r'0x([0-9a-f]{5})\s+((?:[0-9a-f]{2} ){8})', out[out.rfind('Stop at'):]):
        if mm:
            a = int(mm.group(1), 16)
            bs = bytes.fromhex(mm.group(2).replace(' ', ''))
            if a < WIN:
                memo[a:a + len(bs)] = bs[:WIN - a]
                seen += len(bs)
    if seen < WIN:
        return None
    return dict(PC=int(m.group(1), 16), CC=int(f[-1][0], 16), A=int(f[-1][1], 16), X=int(xy[-1][0], 16),
                Y=int(xy[-1][1], 16), SP=int(sp[-1], 16), mem=bytes(memo))


def main():
    gh, uc, corpus, outdir = sys.argv[2:6]
    per = int(sys.argv[6]) if len(sys.argv) > 6 else 6
    rnd = random.Random(int(sys.argv[7]) if len(sys.argv) > 7 else 1)
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='sem.', dir=os.environ.get('TMPDIR', '/tmp'))
    fm = forms(gh, uc)
    cases = []
    for shape, (text, ln) in sorted(fm.items()):
        for _ in range(per):
            r = instantiate(text, rnd)
            if r is None:
                continue
            cases.append(dict(form=shape, asm=r[0], fix=r[1], len=ln))
    codes = assemble([c['asm'] for c in cases], tmp, 'asm')
    tests = []
    for c, code in zip(cases, codes):
        if code is None or len(code) != c['len']:
            continue
        c['code'] = code
        c['mem'] = bytes(rnd.randrange(256) for _ in range(WIN))
        c['A'] = rnd.randrange(256)
        c['X'] = rnd.randrange(0x100, 0x500)
        c['Y'] = rnd.randrange(0x100, 0x500)
        c['SP'] = rnd.randrange(0xa00, 0xe00)
        if c['asm'].split()[0] == 'iret' or c['asm'].replace(' ', '').lower() == 'popcc':
            m = bytearray(c['mem'])           # CC bit 6 is reserved: do not load it from the stack
            m[c['SP'] + 1] &= 0xbf
            c['mem'] = bytes(m)
        c['CC'] = rnd.choice([0x00, 0x28, 0xff & ~0x40]) if rnd.random() < 0.3 else (rnd.randrange(256) & ~0x40)
        tests.append(c)
    print(len(cases), 'cases,', len(tests), 'assembled')

    def one(k):
        c = tests[k]
        return run_ucsim(c, tmp, 't%d' % k)
    with ThreadPoolExecutor(int(os.environ.get('JOBS', '8'))) as ex:
        results = list(ex.map(one, range(len(tests))))
    n = 0
    with open(os.path.join(outdir, 'tests.txt'), 'w') as f:
        for k, (c, r) in enumerate(zip(tests, results)):
            if r is None:
                continue
            mem = bytearray(c['mem'])
            for a, b in c['fix']:
                mem[a:a + len(b)] = b
            init = f"A={c['A']:x},CC={c['CC']:x},X={c['X']:x},Y={c['Y']:x},SP={c['SP']:x},m{WIN}:0={bytes(mem).hex()},m{len(c['code'])}:{CODE:x}={c['code'].hex()}"
            exp = f"A={r['A']:x},CC={r['CC'] & 0xbf:x},X={r['X']:x},Y={r['Y']:x},SP={r['SP']:x},PC={r['PC'] & PCMASK:x},m{WIN}:0={r['mem'].hex()}"
            f.write(f"{c['asm'].replace(' ', '_').replace(chr(9), '_')}#{k} {init} {exp}\n")
            n += 1
    print(n, 'tests written')
    shutil.rmtree(tmp)


if __name__ == '__main__':
    if sys.argv[1] == 'gen':
        main()
