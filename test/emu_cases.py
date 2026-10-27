"""Hand-computed p-code test cases for the STM8 module (assembled by emu_tests.py, run by EmuCheck.java).

T(name, asm, init, expect): asm is a short sequence (AS syntax, cpu STM8); init and expect are comma separated items:
registers (A X Y SP CC), 'm1:<addr>=<hex>' / 'm2:' / 'm3:' (memory, big-endian); '@END@' is the address after the
sequence, '@label@' a label's address.

Every expectation is worked out by hand from the STM8 instruction set (PM0044) and its CC layout
(V=80 I1=20 H=10 I0=08 N=04 Z=02 C=01, bit 6 reserved): ADD / ADC / SUB / SBC / CP set V and C (carry or borrow),
ADD / ADC also H (carry out of bit 3); INC / DEC set V, N, Z; LD / logic / TNZ set N and Z; NEG sets C unless the
operand is 0 and V when it is 0x80; SLL / SRL / SRA / RLC / RRC put the bit shifted out in C; CPL sets C; MUL clears
H and C; SIM sets I1 and I0, RIM sets I1 and clears I0; BSET / BRES / BCPL / MOV / PUSH / POP (not POP CC) / JP / CALL
change no flag; the stack grows down and CALL pushes PCL first.  Tests whose name starts with XFAIL_ carry a
deliberately wrong expectation and must be reported as failures.
"""

CASES = []


def T(name, asm, init='', expect=''):
    CASES.append((name, asm, init, expect))


# ---- loads and ALU -----------------------------------------------------------------------------------------
T('ld_imm_negative', 'ld a,#$80', 'A=00,CC=00', 'A=80,CC=04')
T('ld_zero_keeps_carry', 'ld a,#$00', 'A=55,CC=01', 'A=00,CC=03')
T('add_half_carry', 'add a,#$0f', 'A=01,CC=00', 'A=10,CC=10')
T('add_overflow_carry', 'add a,#$80', 'A=80,CC=00', 'A=00,CC=83')
T('sub_borrow', 'sub a,#$01', 'A=00,CC=00', 'A=ff,CC=05')
T('sub_overflow', 'sub a,#$01', 'A=80,CC=00', 'A=7f,CC=80')
T('sbc_borrow_in', 'sbc a,#$05', 'A=05,CC=01', 'A=ff,CC=05')
T('sbc_no_borrow_in', 'sbc a,#$05', 'A=05,CC=00', 'A=00,CC=02')
T('sbc_a_equals_b_minus_carry', 'sbc a,#$ff', 'A=fe,CC=01', 'A=fe,CC=05')
T('adc_carry_in_and_out', 'adc a,#$ff', 'A=ff,CC=01', 'A=ff,CC=15')
T('cp_less', 'cp a,#$02', 'A=01,CC=00', 'A=01,CC=05')
T('inc_overflow', 'inc a', 'A=7f,CC=01', 'A=80,CC=85')
T('dec_mem_to_zero', 'dec $50', 'CC=00,m1:50=01', 'CC=02,m1:50=00')
T('neg_overflow', 'neg a', 'A=80,CC=00', 'A=80,CC=85')
T('neg_zero_clears_carry', 'neg a', 'A=00,CC=01', 'A=00,CC=02')
T('cpl', 'cpl a', 'A=0f,CC=00', 'A=f0,CC=05')
T('swap', 'swap a', 'A=1e,CC=00', 'A=e1,CC=04')
T('sll', 'sll a', 'A=c1,CC=00', 'A=82,CC=05')
T('srl', 'srl a', 'A=03,CC=00', 'A=01,CC=01')
T('sra_keeps_sign', 'sra a', 'A=81,CC=00', 'A=c0,CC=05')
T('rlc_through_carry', 'rlc a', 'A=80,CC=01', 'A=01,CC=01')
T('rrc_through_carry', 'rrc a', 'A=01,CC=01', 'A=80,CC=05')
T('and_or_xor', 'and a,#$3c\n or a,#$81\n xor a,#$ff', 'A=f0,CC=00', 'A=4e,CC=00')
T('bcp_keeps_a', 'bcp a,#$80', 'A=80,CC=00', 'A=80,CC=04')
T('mul', 'mul x,a', 'X=00ff,A=02,CC=11', 'X=01fe,A=02,CC=00')
T('div', 'div x,a', 'X=0064,A=07,CC=01', 'X=000e,A=02,CC=00')
T('divw', '@raw 65', 'X=03e8,Y=0007,CC=13', 'X=008e,Y=0006,CC=00')
T('div_by_zero_sets_carry', 'div x,a', 'X=1234,A=00,CC=00', 'X=1234,A=00,CC=03')
T('divw_by_zero_sets_carry', '@raw 65', 'X=1234,Y=0000,CC=00', 'X=1234,Y=0000,CC=03')
T('rrwa', 'rrwa x', 'X=1234,A=56,CC=00', 'X=5612,A=34,CC=00')
T('rlwa', 'rlwa x', 'X=1234,A=56,CC=00', 'X=3456,A=12,CC=00')
T('exg_a_xl_and_exgw', 'exg a,xl\n exgw x,y', 'A=11,X=2233,Y=4455', 'A=33,X=4455,Y=2211')
T('ld_xh_xl_a', 'ld xh,a\n ld a,yl', 'A=ab,X=0000,Y=00cd', 'A=cd,X=ab00')
# ---- 16-bit ----------------------------------------------------------------------------------------------
T('subw_x_imm', 'subw x,#$0001', 'X=1234,CC=00', 'X=1233,CC=00')
T('addw_x_wrap', 'addw x,#$0001', 'X=ffff,CC=00', 'X=0000,CC=13')
T('addw_y_mem', 'addw y,$0200', 'Y=1000,CC=00,m2:0200=0234', 'Y=1234,CC=00')
T('cpw_equal', 'cpw x,#$1234', 'X=1234,CC=00', 'X=1234,CC=02')
T('negw', 'negw x', 'X=0001,CC=00', 'X=ffff,CC=05')
T('clrw_keeps_carry', 'clrw x', 'X=1234,CC=01', 'X=0000,CC=03')
T('incw_decw', 'incw y\n decw x', 'X=0001,Y=00ff,CC=00', 'X=0000,Y=0100,CC=02')
T('sllw_srlw', 'sllw x\n srlw y', 'X=8001,Y=0003,CC=00', 'X=0002,Y=0001,CC=01')
T('swapw', 'swapw x', 'X=12ab,CC=00', 'X=ab12,CC=04')
T('ldw_x_imm_negative', 'ldw x,#$beef', 'CC=00', 'X=beef,CC=04')
T('ldw_sp_x', 'ldw x,#$0900\n ldw sp,x', 'SP=0800,CC=00', 'SP=0900,X=0900,CC=00')
T('ldw_x_sp_and_sub_sp', 'ldw x,sp\n sub sp,#4\n addw sp,#1', 'SP=0800', 'X=0800,SP=07fd')
T('ldw_indirect', 'ldw x,[$50.w]', 'CC=00,m2:0050=0a00,m2:0a00=beef', 'X=beef,CC=04')
# ---- addressing -------------------------------------------------------------------------------------------
T('ld_sp_relative', 'ld a,($05,sp)', 'SP=0800,m1:0805=77', 'A=77,CC=00')
T('ld_x_indexed_long', 'ld a,($0100,x)', 'X=0400,m1:0500=9c', 'A=9c,CC=04')
T('ld_indirect_indexed', 'ld a,([$60.w],x)', 'X=0003,m2:0060=0300,m1:0303=5a', 'A=5a')
T('ld_store_x', 'ld ($02,x),a', 'A=12,X=0300', 'm1:0302=12')
T('ldf_direct_and_indexed', 'ldf a,$000123\n ldf ($000100,x),a', 'X=0002,m1:0123=99', 'A=99,CC=04,m1:0102=99')
T('ldf_through_pointer', 'ldf a,[$70.e]', 'm3:0070=000a10,m1:0a10=3c', 'A=3c')
T('mov_imm_and_mem', 'mov $60,#$5a\n mov $70,$60\n mov $0300,$0070', '', 'm1:60=5a,m1:70=5a,m1:0300=5a')
T('exg_a_mem', 'exg a,$0200', 'A=01,m1:0200=02', 'A=02,m1:0200=01')
T('bset_bres_bcpl', 'bset $0200,#7\n bres $0200,#0\n bcpl $0200,#3', 'm1:0200=01', 'm1:0200=88')
T('bccm_copies_carry', 'bccm $50,#2', 'CC=01,m1:50=00', 'm1:50=04')
T('push_pop', 'push a\n pushw x\n clrw x\n ld a,#0\n popw x\n pop a', 'A=ab,X=1234,SP=0800', 'A=ab,X=1234,SP=0800')
T('push_layout', 'push a\n pushw x', 'A=ab,X=1234,SP=0800', 'SP=07fd,m1:0800=ab,m2:07fe=1234')
# ---- control flow ---------------------------------------------------------------------------------------
T('call_ret', 'call l1\nretp: jra done\nl1: ld a,#$42\n ret\ndone: nop', 'SP=0800', 'A=42,SP=0800,m2:07ff=@retp@')
T('callr_ret', 'callr l1\n jra done\nl1: ld a,#$43\n ret\ndone: nop', 'SP=0800', 'A=43,SP=0800')
T('callf_retf', 'callf l1\n jra done\nl1: ld a,#$44\n retf\ndone: nop', 'SP=0800', 'A=44,SP=0800')
T('jrne_taken_not_taken', 'cp a,#1\n jrne skip\n ld a,#9\nskip: jreq done\n ld a,#7\ndone: nop', 'A=02', 'A=07')
T('jrc_and_jrnc', 'jrc l1\n ld a,#1\nl1: jrnc l2\n ld a,#2\nl2: nop', 'A=00,CC=01', 'A=02')
T('jrsgt_signed', 'cp a,#$ff\n jrsgt yes\n ld a,#1\n jra done\nyes: ld a,#2\ndone: nop', 'A=01', 'A=02')
T('jrh_half_carry', 'jrh yes\n ld a,#1\n jra done\nyes: ld a,#2\ndone: nop', 'A=00,CC=10', 'A=02')
T('jrnh_half_carry_clear', 'jrnh yes\n ld a,#1\n jra done\nyes: ld a,#2\ndone: nop', 'A=00,CC=80', 'A=02')
T('btjt_taken_sets_carry', 'btjt $50,#3,done\n ld a,#1\ndone: nop', 'A=00,CC=00,m1:50=08', 'A=00,CC=01')
T('btjf_not_taken_clears_carry', 'btjf $50,#3,done\n ld a,#1\ndone: nop', 'A=00,CC=01,m1:50=08', 'A=01,CC=01')
T('jp_indirect_x', 'ldw x,#l2\n jp (x)\n ld a,#1\nl2: nop', 'A=00', 'A=00')
T('jp_long_pointer', 'jp [$50.w]\n ld a,#1\nl2: nop', 'A=00,m2:0050=@l2@', 'A=00')
T('call_indexed_offset', 'ldw x,#l1-$10\n call ($10,x)\n jra done\nl1: ld a,#9\n ret\ndone: nop', 'SP=0800', 'A=09')
T('jpf_direct', 'jpf l2\n ld a,#1\nl2: nop', 'A=00', 'A=00')
T('iret_pops_context', 'iret', 'SP=07f6,m1:07f7=bf,m1:07f8=11,m2:07f9=2233,m2:07fb=4455,m3:07fd=@END@', 'CC=bf,A=11,X=2233,Y=4455,SP=07ff')
T('sim_rim', 'sim\n rim', 'CC=00', 'CC=20')
T('sim_only', 'sim', 'CC=00', 'CC=28')
T('halt_sets_interrupt_mask', 'halt', 'CC=00', 'CC=20,TRAP=__Halt')
T('trap_instruction', 'trap', '', 'TRAP=__TrapInterrupt')
T('jril_is_hardware_input', 'jril l1\nl1: nop', '', 'TRAP=__InterruptLineLevel')
T('int_jumps', 'dc.b $82,0,l1>>8,l1&255\n ld a,#1\nl1: nop', 'A=00', 'A=00')
T('nop_is_a_nop', 'nop', 'A=12,CC=15', 'A=12,CC=15')
# ---- forms uCsim decodes wrongly (see GHIDRA-RARE.md): checked by hand only -------------------------------------
T('addw_y_sp_relative', 'addw y,($02,sp)', 'Y=0100,SP=0800,CC=00,m2:0802=0102', 'Y=0202,CC=00')
T('subw_y_mem', 'subw y,$0200', 'Y=1234,CC=00,m2:0200=0001', 'Y=1233,CC=00')
T('subw_x_sp_relative', 'subw x,($04,sp)', 'X=0005,SP=0800,CC=00,m2:0804=0006', 'X=ffff,CC=15')
T('cpw_x_long_pointer', 'cpw x,[$0050.w]', 'X=0a0a,CC=00,m2:0050=0a00,m2:0a00=0a0a', 'X=0a0a,CC=02')
T('cpw_y_short_pointer', 'cpw y,[$50.w]', 'Y=0a0b,CC=00,m2:0050=0a00,m2:0a00=0a0a', 'Y=0a0b,CC=00')
T('ldw_store_y_through_pointer', 'ldw [$50.w],y', 'Y=beef,CC=00,m2:0050=0a00', 'm2:0a00=beef,CC=04')
T('ldw_y_indirect_indexed', 'ldw y,([$50.w],y)', 'Y=0002,CC=00,m2:0050=0a00,m2:0a02=1234', 'Y=1234,CC=00')
T('ldw_store_x_indirect_indexed_y', 'ldw ([$50.w],y),x', 'X=8001,Y=0004,CC=00,m2:0050=0a00', 'm2:0a04=8001,CC=04')
T('ldf_store_through_far_pointer', 'ldf [$70.e],a', 'A=5a,CC=00,m3:0070=000a10', 'm1:0a10=5a,CC=00')
T('ldf_indexed_through_far_pointer', 'ldf a,([$70.e],x)', 'X=0003,CC=00,m3:0070=000a10,m1:0a13=c3', 'A=c3,CC=04')
T('ldf_store_far_direct', 'ldf $000300,a', 'A=11,CC=00', 'm1:0300=11')
T('ldf_store_far_indexed', 'ldf ($000300,x),a', 'A=00,X=0005,CC=01', 'm1:0305=00,CC=03')
T('jpf_through_far_pointer', 'jpf [$70.e]\n ld a,#1\nl2: nop', 'A=00,m3:0070=@l2@', 'A=00')
T('callf_through_far_pointer', 'callf [$70.e]\nretf1: jra done\nl1: ld a,#$55\n retf\ndone: nop', 'SP=0800,m3:0070=@l1@', 'A=55,SP=0800,m3:07fe=@retf1@')
T('jrf_never_branches', 'jrf l1\n nop\nl1: ld a,#7', 'A=00', 'A=07')
# ---- must fail --------------------------------------------------------------------------------------------
T('XFAIL_wrong_add_result', 'add a,#$01', 'A=01', 'A=03')
T('XFAIL_wrong_flag', 'cp a,#$01', 'A=01,CC=00', 'CC=00')
