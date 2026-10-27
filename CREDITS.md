# Credits and provenance: STM8 module

## Upstream

| | |
|---|---|
| Source | https://github.com/esaulenka/ghidra_STM8, HEAD `45b7097` ("Merge pull request #13 from abliss/patch-1", 2025-07-28) |
| Ghidra-Rare fork | branch `ghidra-rare` of the aleph-void fork; the history below the Ghidra-Rare commits is the original repository's |
| License | Apache-2.0 (`LICENSE`) |
| Original authors | from `git log` of the original history (40 commits): Alexey Esaulenko (GitHub @esaulenka; 32 commits, plus 1 as "alexeye"): the module, the analyzer, the manual index; Adam Bliss (@abliss): `SUB SP,#` display fix (PR #13); "kio" (@Megatokio): `CC_H` calculation and the `INC` / `INCW` fix (PR #2) |
| Based on | the STM8 CPU programming manual PM0044 (opcode tables), Ghidra's module template |

## Other implementations

`gh search repos "ghidra stm8"` and `"stm8 sleigh"` found no other Ghidra STM8 module (only the upstream repository itself).
No code was borrowed from elsewhere.

## Ghidra-Rare changes

1. `JP` / `CALL` through (X), (Y), (n,X), [ptr], ([ptr],X) ... jump to the effective address, not to the operand's contents
   (upstream issues #9 and #10; the p-code jumped to garbage and `CALL (Y)` could not be emulated).
2. `SBC` computes A - operand - C correctly (borrow, overflow and result were wrong).
3. `JRNH` / `JRH` test H (upstream tested V).
4. `JRIL` / `JRIH` (90 2E / 90 2F) added (a pcodeop models the interrupt pin).
5. `JRF` ("branch never", used by SDCC as a one-byte skip) has empty p-code: no flow to the displayed target (this made
   the decompiler crash on SDCC's library code).
6. `NOP`, `RIM`, `SIM` no longer call pcodeops; `DIV` / `DIVW` by zero set C (and Z) instead of dividing by zero in p-code.
7. `SUBW` H flag: the borrow out of bit 7 (the upstream expression had an operator-precedence error).
8. `ADDW X,#` / `SUBW X,#` print the `#`; the undefined opcodes 72 A0 / 72 AB were removed; `ADD SP,#` (upstream issue #16);
   unreachable constructors removed (`Jcond "A"`, `Jcond "F"`, two dead operand rows).
9. LDF / JPF / CALLF / INT print the full 24-bit operand also in the 16-bit language (the token is displayed, not the truncated address).
10. cspec: argument/result registers `Y:X` for 32-bit values, `Y` killed by calls, `__farcall` stack arguments at SP+4,
   new `__flagreturn` prototype (upstream issue #12); `STM8.dwarf` register map and `STM8.opinion` (ELF, EM_STM8 = 186);
   the DWARF mapping is referenced from the language definitions.
11. Build files (`build.gradle`, `extension.properties`), README updates, `GHIDRA-RARE.md`, `CREDITS.md`, `test/`.

## Sources and reference tools

Used as black boxes, facts or test inputs; nothing copied into the module:

- uCsim 0.8.15's STM8 simulator (`ucsim_stm8`, GPL-2.0, from the Ubuntu package `sdcc-ucsim`): disassembler and CPU state,
  run as a black box only (its source was not read).
- AS macro assembler 1.42 (GPL-2.0) `cpu STM8`, and `sdasstm8` (SDCC 4.5.0, GPL-2.0): independent assemblers.
- SDCC 4.5.0 (GPL-2.0, library exception): compiler and the library sources used as real code; rksdna/stm8s (MIT) and
  jukkas/stm8-sdcc-examples (Unlicense), fetched by pinned commit and SHA-256 by `test/real-binaries.sh`, never committed.
- The STM8 CPU programming manual PM0044 could not be downloaded here; opcode tables and semantics were checked against the
  two assemblers, uCsim, and the programs above.
