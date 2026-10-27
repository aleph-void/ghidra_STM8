#!/usr/bin/env bash
# STM8 module test suite: everything that needs no downloaded inputs.
#
#   GHIDRA_INSTALL_DIR=<Ghidra 12.1.x/12.2 with this module linked into Ghidra/Processors/STM8> test/run-tests.sh [workdir] [--real]
#
# 1. both specs compile (.sla well under 16 MB)
# 2. decode differential against uCsim's STM8 disassembler (sstm8, a black box) on every prefix x opcode x operand byte
#    and 100,000 random slots, in both languages, and AS (cpu STM8) + sdasstm8 re-assembling the module's disassembly
#    to the original bytes
# 3. every SLEIGH constructor is reached by that corpus
# 4. p-code: 97 hand-computed emulator cases (EmuCheck.java) including deliberately wrong expectations that must be
#    reported, in both languages
#    4b: random single instructions: uCsim's final state (A X Y SP CC PC and 4 KB of RAM) from random states is the
#    expectation for the module's p-code (sem_gen.py + SemCheck.java), in both languages
# SEMANTICS_ONLY=1 skips the decode steps 2 and 3 (they need the exhaustive corpus decoded; the gh24/uc files of an
# earlier run in the same workdir are reused by 4b and 4c)
# --real adds step 5: SDCC-built programs (test/real-binaries.sh)
#
# Environment: GHIDRA_INSTALL_DIR, JAVA_HOME (optional), PROJ_DIR (where headless projects are created: the path must
# not contain a component that starts with a dot), JOBS (parallel Ghidra runs, default 4), QUICK=1 (30,000 random
# slots and only the first 2 prefixes of the exhaustive corpus' operand space), UCSIM_STM8, ASL / P2BIN, SDASSTM8.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
REAL=0
ARGS=()
for a in "$@"; do if [[ $a == --real ]]; then REAL=1; else ARGS+=("$a"); fi; done
W=$(readlink -m "${ARGS[0]:-${TMPDIR:-/tmp}/stm8-tests}")
mkdir -p "$W"
export TMPDIR=$W PROJ_DIR=${PROJ_DIR:-$W} JOBS=${JOBS:-4}
TOOLS=$HOME/.cache/ghidra-rare-scratch/tools
export UCSIM_STM8=${UCSIM_STM8:-$(command -v ucsim_stm8 || echo "$TOOLS/sdcc-root/usr/bin/ucsim_stm8")}
export ASL=${ASL:-$(command -v asl || echo "$TOOLS/asl/bin/asl")} P2BIN=${P2BIN:-$(command -v p2bin || echo "$TOOLS/asl/bin/p2bin")}
export SDASSTM8=${SDASSTM8:-$(command -v sdasstm8 || echo "$TOOLS/sdcc-root/usr/bin/sdasstm8")}
fail=0
P="$GHIDRA_INSTALL_DIR/Ghidra/Processors/STM8"
if [[ ! -e $P ]]; then ln -s "$MOD" "$P"; elif [[ $(readlink -f "$P") != "$MOD" ]]; then echo "warning: $P exists and is not this module" >&2; fi

echo "== 1. SLEIGH compiles"
for m in medium large; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/STM8_$m.slaspec" 2>&1 | grep -E "^ERROR" && exit 1 || true
	sz=$(stat -c %s "$MOD/data/languages/STM8_$m.sla")
	echo "   STM8_$m.sla: $sz bytes"
	((sz < 16 * 1024 * 1024))
done

RAND=100000; [[ -n ${QUICK:-} ]] && RAND=30000
python3 "$HERE/gen_corpus.py" "$W/all.bin" $RAND 7
if [[ -z ${SEMANTICS_ONLY:-} ]]; then
echo "== 2. decode differential"
python3 "$HERE/ucsim_stream.py" "$W/all.bin" "$W/uc.txt" 8
"$HERE/decode-corpus.sh" STM8:BE:24:default "$W/all.bin" "$W/gh24.txt" 8
"$HERE/decode-corpus.sh" STM8:BE:16:default "$W/all.bin" "$W/gh16.txt" 8
echo "   AS and sdasstm8 re-assemble the large language's disassembly to the original bytes"
python3 "$HERE/asm_roundtrip.py" "$W/gh24.txt" "$W/all.bin" 8 "$W/ok24.txt" | tee "$W/roundtrip.txt" | tail -8 || fail=1
echo "   against uCsim, large language (24-bit addresses)"
python3 "$HERE/compare.py" "$W/gh24.txt" "$W/uc.txt" --asm-ok "$W/ok24.txt" --corpus "$W/all.bin" --show 2 | tee "$W/compare24.txt" | grep -v "^       " | cut -c1-170 || fail=1
echo "   against uCsim, medium language (addresses shown modulo 64 KB)"
python3 "$HERE/compare.py" "$W/gh16.txt" "$W/uc.txt" --asm-ok "$W/ok24.txt" --corpus "$W/all.bin" --mask16 --show 2 | tee "$W/compare16.txt" | grep -v "^       " | cut -c1-170 || fail=1

echo "== 3. every constructor is reached"
"$HERE/decode-corpus.sh" STM8:BE:24:default "$W/all.bin" "$W/reach.txt" 8 Reach.java
python3 "$HERE/reach_check.py" "$MOD/data/languages/STM8.sinc" "$W/reach.txt" || fail=1

fi
echo "== 4. p-code: hand-computed emulator tests"
mkdir -p "$W/emu"
python3 "$HERE/emu_tests.py" "$W/emu"
for v in 16 24; do
	"$HERE/ghidra-script.sh" raw STM8:BE:$v:default "$W/emu/emu.bin" EmuCheck.java "$W/emu/tests.txt" "$W/emu/out$v.txt"
	echo "   STM8:BE:$v: $(tail -1 "$W/emu/out$v.txt")"
	grep -q " 0 failed" "$W/emu/out$v.txt" || { grep ^FAIL "$W/emu/out$v.txt" | head -20; fail=1; }
	grep -q "[1-9][0-9]* broken expectations detected" "$W/emu/out$v.txt" || { echo "   the deliberately wrong expectations were not detected"; fail=1; }
done
echo "== 4b. random single instructions against uCsim's state"
head -c 8192 /dev/zero > "$W/blank.bin"
for v in 16 24; do
	mkdir -p "$W/sem$v"
	PCMASK=$([[ $v == 16 ]] && echo 0xffff || echo 0xffffff) python3 "$HERE/sem_gen.py" gen "$W/gh24.txt" "$W/uc.txt" "$W/all.bin" "$W/sem$v" 8 3 | tail -1
	"$HERE/ghidra-script.sh" raw STM8:BE:$v:default "$W/blank.bin" SemCheck.java "$W/sem$v/tests.txt" "$W/sem$v/out.txt"
	echo "   STM8:BE:$v: $(tail -1 "$W/sem$v/out.txt")"
	grep -q " 0 failed" "$W/sem$v/out.txt" || { grep ^FAIL "$W/sem$v/out.txt" | head -20; fail=1; }
done
echo "== 4c. decompiler fuzz: random straight-line functions"
for seed in 1 2 3; do
	mkdir -p "$W/fuzz$seed"
	python3 "$HERE/fuzz_decomp.py" "$W/gh24.txt" "$W/uc.txt" "$W/fuzz$seed" 480 $seed >/dev/null
	BASE_ADDR=0x8000 "$HERE/ghidra-script.sh" raw STM8:BE:16:default "$W/fuzz$seed/fuzz.bin" DecompAll.java "$W/fuzz$seed/entries.txt" "$W/fuzz$seed/out.txt"
	echo "   seed $seed: $(tail -1 "$W/fuzz$seed/out.txt")"
	grep -q " 0 failed, 0 with low-level errors" "$W/fuzz$seed/out.txt" || { grep -E "^(FAILED|LOWLEVEL)" "$W/fuzz$seed/out.txt" | head; fail=1; }
done
if ((REAL)); then
	echo "== 5. real code"
	"$HERE/real-binaries.sh" "$W/real" || fail=1
fi
if ((fail)); then echo "FAILED"; exit 1; fi
echo "all tests passed"
