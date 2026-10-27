#!/usr/bin/env bash
# Real STM8 code: freely licensed programs built with SDCC, imported (auto-detected) into Ghidra, analysed,
# decompiled, and compared with uCsim and with SDCC's own assembler listings.
#   test/real-binaries.sh <workdir>
# Fetched by pinned URL and SHA-256 (nothing is committed):
#   SDCC 4.5.0 (Ubuntu packages sdcc, sdcc-libraries, sdcc-ucsim: compiler, assembler, library sources, STM8 simulator)
#   rksdna/stm8s            (MIT)        cooperative multitasking OS for the STM8S
#   jukkas/stm8-sdcc-examples (Unlicense) blink / adc / uart / spi / ds18b20 / timer-interrupt
# and the library sources of SDCC itself (GPL-2.0 with the library exception), built into one image per memory model.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "${1:?workdir}")
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
mkdir -p "$W/dl" "$W/sdcc" "$W/src" "$W/out" "$W/ghidra"
export TMPDIR=$W PROJ_DIR=${PROJ_DIR:-$W/ghidra}

fetch() { # url sha256 file
	local f="$W/dl/$3"
	[[ -f $f ]] || curl -sL -o "$f" "$1"
	echo "$2  $f" | sha256sum -c --quiet - || { echo "SHA-256 mismatch for $3" >&2; exit 1; }
}
UB=http://archive.ubuntu.com/ubuntu/pool/universe/s/sdcc
fetch "$UB/sdcc_4.5.0+dfsg-4_amd64.deb" fe001b87ed398e8e0707b18b8aa3fbdf65387234f859a76b48a637a6d5a0e5f9 sdcc.deb
fetch "$UB/sdcc-libraries_4.5.0+dfsg-4_all.deb" 1073ff621dc929d4d2741199f8fa608e808c1fed2e2de0bf6baa227fe67619c5 sdcc-libraries.deb
fetch "$UB/sdcc-ucsim_4.5.0+dfsg-4_amd64.deb" 1cbee1de1d201e73d58f92bddf4d1b0ae9666f5ac37c420031f45eb0e6981a39 sdcc-ucsim.deb
fetch https://github.com/rksdna/stm8s/archive/1c253ddce1df2ac0d020ac38868a032216bf987b.tar.gz 0049f8d0c5080460a2a24eb430c0b5d45d91d1cd0b29d90d05a230a008a6edab stm8s.tar.gz
fetch https://github.com/jukkas/stm8-sdcc-examples/archive/2911fcf70333207709311eefefae8d6a1cebcc33.tar.gz 6150fad7ad71e2ae129823414c6ac1a84db6f18601da1033ca3d475c3779dff2 examples.tar.gz
[[ -x $W/sdcc/usr/bin/sdcc ]] || for d in sdcc sdcc-libraries sdcc-ucsim; do dpkg -x "$W/dl/$d.deb" "$W/sdcc"; done
[[ -d $W/src/stm8s ]] || { mkdir -p "$W/src/stm8s" "$W/src/examples"; tar -xzf "$W/dl/stm8s.tar.gz" -C "$W/src/stm8s" --strip-components=1
	tar -xzf "$W/dl/examples.tar.gz" -C "$W/src/examples" --strip-components=1; }
export PATH=$W/sdcc/usr/bin:$PATH
export UCSIM_STM8=$W/sdcc/usr/bin/ucsim_stm8
LIB=$W/sdcc/usr/share/sdcc/lib/src

build() { # name dir sources... : medium and large model, ELF with DWARF and ELF without debug symbols (+ ihx for uCsim)
	local n=$1 d=$2; shift 2
	for m in medium large; do
		local opt=(); [[ $m == large ]] && opt=(--model-large)
		mkdir -p "$W/out/$n-$m"
		# (the link of the OS sample warns about two undefined symbols of its own sources and sdcc exits non-zero)
		(cd "$W/out/$n-$m"
		sdcc -mstm8 "${opt[@]}" --out-fmt-elf -DSTM8S103 -I"$W/src/examples" "$@" -o "$n-$m.elf" >/dev/null 2>&1 || true
		sdcc -mstm8 "${opt[@]}" --debug --out-fmt-elf -DSTM8S103 -I"$W/src/examples" "$@" -o "$n-$m-dbg.elf" >/dev/null 2>&1 || true
		sdcc -mstm8 "${opt[@]}" -DSTM8S103 -I"$W/src/examples" "$@" -o "$n-$m.ihx" >/dev/null 2>&1 || true)
	done
}
if [[ ! -f $W/out/.built ]]; then
	for p in blink adc uart spi-out-max7219 ds18b20 timer-interrupt; do build "$p" . "$W/src/examples/$p/$p.c"; done
	build stm8s-os . "$W"/src/stm8s/*.c
	# SDCC's whole library (C and assembler sources) linked into one image per model
	for m in medium large; do
		opt=(); [[ $m == large ]] && opt=(--model-large)
		D=$W/out/sdcc-lib-$m; mkdir -p "$D"; cd "$D"
		for f in "$LIB"/*.c; do sdcc -mstm8 "${opt[@]}" -c "$f" -I"$LIB" -o "$(basename "$f" .c).rel" >/dev/null 2>&1 || true; done
		for f in "$LIB"/stm8/*.s; do cp "$f" .; sdasstm8 -plosgff "$(basename "$f")" >/dev/null 2>&1 || true; done
		rm -f __memcpy.rel
		printf 'void main(void){}\nchar putchar(char c){return c;}\n' > main.c
		sdcc -mstm8 "${opt[@]}" -c main.c >/dev/null 2>&1
		sdcc -mstm8 "${opt[@]}" --out-fmt-elf --code-size 60000 ./*.rel -o "sdcc-lib-$m.elf" >/dev/null 2>&1 || true
		sdcc -mstm8 "${opt[@]}" --code-size 60000 ./*.rel -o "sdcc-lib-$m.ihx" >/dev/null 2>&1 || true
		cd "$W"
	done
	touch "$W/out/.built"
fi

fail=0
for elf in "$W"/out/*/*.elf; do
	n=$(basename "$elf" .elf); d=$(dirname "$elf")
	ihx=$d/${n%-dbg}.ihx
	[[ -f $ihx ]] || continue
	R=$W/res/$n; mkdir -p "$R"; rm -f "$R"/*
	echo "== $n"
	mode=(auto -); [[ $n == *-large* ]] && mode=(elf STM8:BE:24:default)      # (the ELF opinion chooses the 16-bit language)
	"$HERE/ghidra-script.sh" "${mode[@]}" "$elf" RealCheck.java "$R/summary.txt" "$R/listing.txt" 300 || { fail=1; continue; }
	grep -E "^(language|instructions|functions|bookmark|decompiled)" "$R/summary.txt" | sed 's/^/   /'
	grep -E "^(Error|decompile failure)" "$R/summary.txt" | head -5 | sed 's/^/   /'
	rst=(); for f in "$d"/*.rst; do [[ -f $f ]] && rst+=("$f"); done
	python3 "$HERE/real_compare.py" "$R/listing.txt" "$ihx" ${rst[@]:+--rst "${rst[@]}"} || fail=1
done
exit $fail
