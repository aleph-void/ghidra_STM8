# STM8 in Ghidra-Rare: verification notes

Source: https://github.com/esaulenka/ghidra_STM8 (Apache-2.0), see [CREDITS.md](CREDITS.md) for provenance and every change.
Languages: `STM8:BE:16:default` (medium memory model, 16-bit addresses) and `STM8:BE:24:default` (large, 24-bit addresses);
the upstream language IDs are unchanged. Builds for Ghidra 12.1.3, 12.1.4 and 12.2 (`tools/build-module.sh --standard --name STM8`).

## How to test

```
GHIDRA_INSTALL_DIR=<Ghidra> PROJ_DIR=<dir whose path has no component starting with '.'> test/run-tests.sh <workdir> [--real]
```
Needs `ucsim_stm8` (Ubuntu `sdcc-ucsim`), AS (`asl`, `p2bin`) and `sdasstm8` (Ubuntu `sdcc`); `--real` fetches SDCC 4.5.0 and two
freely licensed sample projects by pinned URL and SHA-256 (nothing is committed). The reference tools are used as black boxes.

## Results

| Area | Result |
|---|---|
| Decode | 755,360 slots (every prefix none/72/90/91/92 x opcode x first operand byte x 2 operand tails, plus 100,000 random 8-byte slots), both languages, against uCsim's disassembler: 394,729 agree, 346,352 both invalid, 14,274 differences each shown to be a uCsim error by an assembler that reproduces the module's bytes, 5 uCsim simulator escapes (opcode 71 xx), **0 unexplained**. Re-assembly of the module's own disassembly: 375,231 identical in both AS and sdasstm8, 26,773 AS only, 6,552 sdasstm8 only (assembler quirks, below), 447 short-form (a long operand with a value below 256: the assemblers pick the short encoding), **0 where neither reproduces the bytes** |
| Reached | 240/240 constructors reached by the corpus |
| Semantics | 95 hand-computed emulator cases (ALU and flags, shifts, MUL/DIV/DIVW incl. division by zero, 16-bit ops, every addressing mode incl. far pointers, stack, CALL/CALLF/RET/RETF/IRET, branches on all flag kinds, BTJT/BTJF, JP/CALL indirect, INT, SIM/RIM, HALT/TRAP/JRIL as traps), in both languages, plus 2 deliberately wrong expectations that are detected. Also 4,695 random single instructions per language (random A, X, Y, SP, CC and a 4 KB RAM image; 590 instruction forms x 8 operand sets): uCsim's final registers, PC and RAM equal the module's p-code result: 4,695/4,695 in both languages |
| Real code | SDCC 4.5.0-built ELF files: 6 sample programs of jukkas/stm8-sdcc-examples (Unlicense), rksdna/stm8s (MIT), and all of SDCC's own library sources (C and assembler, GPL-2.0 with library exception) linked into one image, each in the medium and the large model, with and without `--debug`. Auto-detected by the ELF opinion (medium language; large forced). About 15,200 library instructions and 2,800 sample instructions: all agree with uCsim at the same addresses (known uCsim errors aside) and all instruction lengths equal SDCC's own assembler listings (14,416 of the library instructions, 0 different). 0 decompile failures (233 library functions, plus 80+ sample functions). 672 random straight-line functions decompile with 0 failures and 0 low-level errors |
| Doesn't work | see below |
| Unverified | see below |

## Confirmed reference-tool errors

- uCsim 0.8.15 prints only the first address byte of `BCPL` / `BCCM` / `SUBW X,longmem` / `SUBW Y,longmem` and
  `LDW Y,[ptr]` forms and gives the wrong length for some (the assemblers and the module agree on 4 bytes); decodes
  `72 F9` (`ADDW Y,(n,SP)`) as `ADDW Y,shortmem`; decodes `CPW X,[longptr.w]` (72 C3) as `CPW Y,...`; does not know
  `LDF (ext,X),A` (A7), `LDF [ptr.e],A` (92 BD) and reads `LDW [ptr],Y`-type forms wrongly; its simulator has
  pseudo-instructions on 71 xx. The semantics of these forms are covered by hand-computed cases.
- AS 1.42: `DIVW X,Y` assembles to `90 65` (opcode 65 is DIVW X,Y: uCsim and sdas agree with the module); `PUSH longmem` assembles
  as `PUSH #imm` (4B instead of 3B); `INT` is unknown.
- sdasstm8 4.5.0: `CPW Y,[longptr]` silently truncates the pointer to its low byte.

## Doesn't work (and why)

- The medium (16-bit) language has a 16-bit address space: the upper byte of LDF/JPF/CALLF/INT operands is lost. Use the large language.
- SDCC's `JRF` skip trick (a one-byte `JRF` consuming the first byte of the next instruction, jumped to from elsewhere) creates
  overlapping instructions, which Ghidra cannot hold: the jumped-to byte is reported as a conflicting instruction.
- `.debug_frame` of SDCC's ELF files makes Ghidra's GCC exception analyzer log an error (4-byte addresses in a 2/3-byte
  address-size program). DWARF locations that use `DW_OP_breg8` (SP-relative frame base) are not recovered.
- HALT, WFI, WFE, BREAK, TRAP, JRIL/JRIH are pcodeops (hardware state: clocks, debugger, interrupt pin).
- Function ID databases for SDCC/Cosmic libraries are not part of a processor module.

## Unverified

- PM0044 could not be downloaded: H after the 16-bit ADDW / SUBW (borrow/carry out of bit 7), the flags after DIV by zero (C set,
  Z set as uCsim does; the manual calls the result undefined), the reserved CC bit 6 and V after the shifts rest on uCsim
  and the module author's tables.
- Other STM8 variants' peripherals/option bytes (not part of a CPU module), Cosmic and IAR compiler output (no free sample),
  the exact reporter's firmware of upstream issue #11.
