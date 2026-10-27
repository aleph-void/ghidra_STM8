# ghidra_STM8

Ghidra STM8 processor module

> **Ghidra-Rare fork.** This copy is verified against uCsim, two assemblers and SDCC-built programs; see
> [GHIDRA-RARE.md](GHIDRA-RARE.md) (results, test suite, changes) and [CREDITS.md](CREDITS.md). Prebuilt extension zips for
> Ghidra 12.1.3, 12.1.4 and 12.2 are on this repository's Releases page. Install: *File > Install Extensions* in the
> Ghidra project window, pick the zip, restart. The statement in the older text below that the analyzer jar must be built
> separately is obsolete: the zip contains it.

## Installation

### Easy way

just copy files to
`$(GHIDRA_HOME)\Ghidra\Extensions\`

### Long way

In this case you also build an analyzer plugin that automatically assigns the proper calling convention. This is very useful for big binaries.

* run `# GHIDRA_INSTALL_DIR=$(full path to ghidra installation) gradle`
* open Ghidra
* in the project selection window click File -> Install Extension
* select `lib/ghidra_STM8.jar` that was built by gradle


## Notes

STM8 uses two kinds of pointers: standard 16-bit, that can deal with RAM, I/O area and the bottom of Flash and 'far' 24-bit pointers that can address all memory.

In Ghidra far pointers can be declared as `byte *24`, `my_struct *24`, etc.

Functions that called by `CALLF` should be declared as `__farcall`. Standard ones, that called by `CALL`, should be declared as `__stdcall` (default behavior).


If the flash image is larger than 32 kbytes, use `STM8:BE:24` language, otherwise either option can be used (but `STM8:BE:16` gives clearer output).


## Known limitations (state in this fork)

| Limitation (upstream README / issues) | State |
|---|---|
| `CALL (X)` / `JP (X)` and the other indirect forms jump to garbage (issues #9, #10) | fixed |
| `CALLF [ptr]` needs a dereference (issue #3) | checked: correct, covered by a hand-computed emulator case |
| `ADD SP,#` shown as ADDW (issue #16) | fixed (`ADD SP,#`); `RRWA X` / `RLWA X` keep ST's spelling, SDCC's assembler accepts it |
| Analyzer jar does not load in Ghidra 11.3.2 (issue #15) | built for 12.1.3, 12.1.4 and 12.2 |
| A function returns its result in the flags (issue #12) | new `__flagreturn` calling convention |
| "Overlapping input varnodes" (issue #11) | not reproducible: 233 SDCC library functions and 672 random functions decompile without it; the reporter's firmware was not available |
| Function ID databases (issue #6) | remaining: not part of a processor module |
| The 16-bit (medium) language truncates far (24-bit) operands | inherent to its 16-bit address space; use `STM8:BE:24` |
| JRF-as-skip code (SDCC's one-byte skip trick) jumps into the middle of an instruction | remaining: Ghidra cannot hold overlapping instructions |
| SDCC `--debug` ELF files: the GCC exception-handler analyzer reports an error | remaining: SDCC writes 4-byte addresses in `.debug_frame`, Ghidra expects the pointer size |
