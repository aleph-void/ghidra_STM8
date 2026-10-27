#!/usr/bin/env python3
"""Corpus of 8-byte slots for the STM8 decode differential.

  gen_corpus.py <out.bin> [random-slots] [seed]

* every prefix (none, 72, 90, 91, 92) x every opcode x every first operand byte, with two sets of
  following bytes (so 1-, 2-, 3-, 4- and 5-byte forms all see distinct operands)
* random slots
"""
import random
import sys

out = sys.argv[1]
nrand = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
tails = [(0x00, 0x00, 0x00), (0xa5, 0x5a, 0xc3)]
slots = []
for pre in ([], [0x72], [0x90], [0x91], [0x92]):
    for op in range(256):
        for b1 in range(256):
            for t in tails:
                s = bytes(pre + [op, b1]) + bytes(t)
                slots.append((s + bytes(rnd.randrange(256) for _ in range(8)))[:8])
for _ in range(nrand):
    slots.append(bytes(rnd.randrange(256) for _ in range(8)))
open(out, 'wb').write(b''.join(slots))
print(len(slots), 'slots')
