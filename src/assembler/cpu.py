"""CPU and memory simulation for the AMB ISA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .isa import (
    ADDR_MASK,
    GEN_OPCODES,
    IMM_OPCODES,
    JUMP_OPCODES,
    MEM_OPCODES,
    REG_CMPA,
    REG_CMPB,
    REG_IC,
    REG_IMR,
    REG_JMPOFF,
    REG_MEMOFF,
    REG_NAMES,
    RR_OPCODES,
    WORD_BITS,
    WORD_MASK,
    sign_extend,
)


class Memory:
    def __init__(self) -> None:
        self._data: dict[int, int] = {}
        self._dirty: set[int] = set()

    def clear(self) -> None:
        self._data.clear()
        self._dirty.clear()

    def clear_dirty(self) -> None:
        self._dirty.clear()

    def consume_dirty(self) -> set[int]:
        dirty = set(self._dirty)
        self._dirty.clear()
        return dirty

    def read_byte(self, addr: int) -> int:
        addr &= ADDR_MASK
        return self._data.get(addr, 0)

    def write_byte(self, addr: int, value: int) -> None:
        addr &= ADDR_MASK
        value &= 0xFF
        prev = self._data.get(addr, 0)
        if prev != value:
            self._dirty.add(addr)
        if value == 0:
            self._data.pop(addr, None)
        else:
            self._data[addr] = value

    def read_word(self, addr: int) -> int:
        addr &= ADDR_MASK
        hi = self.read_byte(addr)
        lo = self.read_byte((addr + 1) & ADDR_MASK)
        return ((hi & 0xFF) << 8) | (lo & 0xFF)

    def write_word(self, addr: int, word: int) -> None:
        addr &= ADDR_MASK
        hi = (word >> 8) & 0xFF
        lo = word & 0xFF
        self.write_byte(addr, hi)
        self.write_byte((addr + 1) & ADDR_MASK, lo)

    def read_word28(self, addr: int) -> int:
        addr &= ADDR_MASK
        b0 = self.read_byte(addr)
        b1 = self.read_byte((addr + 1) & ADDR_MASK)
        b2 = self.read_byte((addr + 2) & ADDR_MASK)
        b3 = self.read_byte((addr + 3) & ADDR_MASK)
        return ((b3 << 24) | (b2 << 16) | (b1 << 8) | b0) & WORD_MASK

    def write_word28(self, addr: int, value: int) -> None:
        addr &= ADDR_MASK
        value &= WORD_MASK
        b0 = value & 0xFF
        b1 = (value >> 8) & 0xFF
        b2 = (value >> 16) & 0xFF
        b3 = (value >> 24) & 0xFF
        self.write_byte(addr, b0)
        self.write_byte((addr + 1) & ADDR_MASK, b1)
        self.write_byte((addr + 2) & ADDR_MASK, b2)
        self.write_byte((addr + 3) & ADDR_MASK, b3)


@dataclass
class ExecResult:
    ic: int
    halted: bool
    message: Optional[str] = None
    changed_registers: set[int] = field(default_factory=set)
    changed_memory: set[int] = field(default_factory=set)


class CPU:
    def __init__(self) -> None:
        self.registers = [0] * len(REG_NAMES)
        self.imem = Memory()
        self.dmem = Memory()
        self.memory = self.dmem
        self.halted = False

    def reset(self) -> None:
        self.registers = [0] * len(REG_NAMES)
        self.halted = False
        self.imem.clear()
        self.dmem.clear()

    def load_program(self, words: list[int], start_addr: int = 0) -> None:
        addr = start_addr & ADDR_MASK
        for word in words:
            self.imem.write_word(addr, word)
            addr = (addr + 2) & ADDR_MASK
        self.imem.clear_dirty()
        self.dmem.clear_dirty()
        self.registers[REG_IC] = start_addr & ADDR_MASK

    def step(self) -> ExecResult:
        if self.halted:
            return ExecResult(ic=self.registers[REG_IC], halted=True, message="CPU halted")

        pre_regs = list(self.registers)
        self.dmem.clear_dirty()

        ic = self.registers[REG_IC] & ADDR_MASK
        word = self.imem.read_word(ic)
        instr = word & 0x7FFF
        op7 = (instr >> 8) & 0x7F
        rb = (instr >> 4) & 0xF
        ra = instr & 0xF
        imm8 = instr & 0xFF

        next_ic = (ic + 2) & ADDR_MASK

        if op7 == GEN_OPCODES["HLT"]:
            self.halted = True
            self.registers[REG_IC] = ic
            return self._build_result(pre_regs, ic, True, "HLT")

        if op7 == GEN_OPCODES["NOP"]:
            self.registers[REG_IC] = next_ic
            return self._build_result(pre_regs, next_ic, False)

        if op7 in IMM_OPCODES.values():
            imr = self.registers[REG_IMR] & WORD_MASK
            if op7 == IMM_OPCODES["LIL"]:
                imr = (imr & ~0xFF) | imm8
            elif op7 == IMM_OPCODES["LIH"]:
                imr = (imr & ~(0xFF << 8)) | (imm8 << 8)
            elif op7 == IMM_OPCODES["LILL"]:
                imr = (imr & ~(0xFF << 16)) | (imm8 << 16)
            elif op7 == IMM_OPCODES["LIHH"]:
                imr = (imr & ~(0xF << 24)) | ((imm8 & 0xF) << 24)
            self.registers[REG_IMR] = imr & WORD_MASK
            self.registers[REG_IC] = next_ic
            return self._build_result(pre_regs, next_ic, False)

        if op7 in JUMP_OPCODES.values():
            offset = sign_extend(imm8, 8)
            jmpoff = self.registers[REG_JMPOFF] & ADDR_MASK

            def do_jump(use_long: bool) -> None:
                nonlocal next_ic
                stride = offset + (jmpoff if use_long else 0)
                addend = stride << 1
                next_ic = (ic + addend) & ADDR_MASK

            if op7 == JUMP_OPCODES["JMP"]:
                do_jump(False)
            elif op7 == JUMP_OPCODES["JMPL"]:
                do_jump(True)
            elif op7 == JUMP_OPCODES["JPEQ"]:
                if (self.registers[REG_CMPA] & WORD_MASK) == (
                    self.registers[REG_CMPB] & WORD_MASK
                ):
                    do_jump(True)
            elif op7 == JUMP_OPCODES["JPBLW"]:
                # RTL signedness is still open; model the documented unsigned compare.
                if (self.registers[REG_CMPA] & WORD_MASK) < (
                    self.registers[REG_CMPB] & WORD_MASK
                ):
                    do_jump(True)
            else:
                return self._build_result(pre_regs, ic, False, "Unknown jump opcode")

            self.registers[REG_IC] = next_ic
            return self._build_result(pre_regs, next_ic, False)

        a_val = self.registers[ra] & WORD_MASK
        b_val = self.registers[rb] & WORD_MASK

        if op7 == MEM_OPCODES["LOAD"]:
            addr = (b_val + self.registers[REG_MEMOFF]) & ADDR_MASK
            self.registers[ra] = self.dmem.read_word28(addr)
            self.registers[ra] &= WORD_MASK
            self.registers[REG_IC] = next_ic
            return self._build_result(pre_regs, next_ic, False)

        if op7 == MEM_OPCODES["STOR"]:
            addr = (b_val + self.registers[REG_MEMOFF]) & ADDR_MASK
            self.dmem.write_word28(addr, a_val)
            self.registers[REG_IC] = next_ic
            return self._build_result(pre_regs, next_ic, False)

        if op7 == RR_OPCODES["NOT"]:
            self.registers[ra] = (~a_val) & WORD_MASK
        elif op7 == RR_OPCODES["OR"]:
            self.registers[ra] = (a_val | b_val) & WORD_MASK
        elif op7 == RR_OPCODES["AND"]:
            self.registers[ra] = (a_val & b_val) & WORD_MASK
        elif op7 == RR_OPCODES["XOR"]:
            self.registers[ra] = (a_val ^ b_val) & WORD_MASK
        elif op7 == RR_OPCODES["SHL"]:
            shift = b_val
            if shift >= WORD_BITS:
                self.registers[ra] = 0
            else:
                self.registers[ra] = (a_val << shift) & WORD_MASK
        elif op7 == RR_OPCODES["SHR"]:
            shift = b_val
            if shift >= WORD_BITS:
                self.registers[ra] = 0
            else:
                self.registers[ra] = (a_val >> shift) & WORD_MASK
        elif op7 == RR_OPCODES["SAR"]:
            shift = b_val
            signed = sign_extend(a_val, 28)
            if shift >= WORD_BITS:
                self.registers[ra] = WORD_MASK if signed < 0 else 0
            else:
                self.registers[ra] = (signed >> shift) & WORD_MASK
        elif op7 == RR_OPCODES["ADD"]:
            self.registers[ra] = (a_val + b_val) & WORD_MASK
        elif op7 == RR_OPCODES["SUB"]:
            self.registers[ra] = (a_val - b_val) & WORD_MASK
        elif op7 == RR_OPCODES["MOV"]:
            self.registers[ra] = b_val & WORD_MASK
        else:
            return self._build_result(pre_regs, ic, False, "Unknown register opcode")

        self.registers[ra] &= WORD_MASK
        self.registers[REG_IC] = next_ic
        return self._build_result(pre_regs, next_ic, False)

    def _build_result(
        self,
        pre_regs: list[int],
        ic: int,
        halted: bool,
        message: Optional[str] = None,
    ) -> ExecResult:
        changed_registers = {
            idx
            for idx, (before, after) in enumerate(zip(pre_regs, self.registers))
            if before != after
        }
        changed_memory = self.dmem.consume_dirty()
        return ExecResult(
            ic=ic,
            halted=halted,
            message=message,
            changed_registers=changed_registers,
            changed_memory=changed_memory,
        )
