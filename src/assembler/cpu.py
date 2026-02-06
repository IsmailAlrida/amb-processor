"""CPU and memory simulation for the AMB ISA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .isa import (
    ADDR_MASK,
    GEN_OPCODES,
    IMM_OPCODES,
    JUMP_OPCODES,
    REG_IC,
    REG_JMPOFF,
    REG_MEMOFF,
    REG_NAMES,
    REG_SHC,
    RR_OPCODES,
    WORD_MASK,
    sign_extend,
)


class Memory:
    def __init__(self) -> None:
        self._data: dict[int, int] = {}

    def clear(self) -> None:
        self._data.clear()

    def read_byte(self, addr: int) -> int:
        addr &= ADDR_MASK
        return self._data.get(addr, 0)

    def write_byte(self, addr: int, value: int) -> None:
        addr &= ADDR_MASK
        value &= 0xFF
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


class CPU:
    def __init__(self) -> None:
        self.registers = [0] * len(REG_NAMES)
        self.memory = Memory()
        self.halted = False

    def reset(self) -> None:
        self.registers = [0] * len(REG_NAMES)
        self.halted = False
        self.memory.clear()

    def load_program(self, words: list[int], start_addr: int = 0) -> None:
        addr = start_addr & ADDR_MASK
        for word in words:
            self.memory.write_word(addr, word)
            addr = (addr + 2) & ADDR_MASK
        self.registers[REG_IC] = start_addr & ADDR_MASK

    def step(self) -> ExecResult:
        if self.halted:
            return ExecResult(ic=self.registers[REG_IC], halted=True, message="CPU halted")

        ic = self.registers[REG_IC] & ADDR_MASK
        word = self.memory.read_word(ic)
        instr = word & 0x7FFF
        op3 = (instr >> 12) & 0x7

        next_ic = (ic + 2) & ADDR_MASK

        if op3 >= 0b100:
            op3_val = op3
            ra = (instr >> 8) & 0xF
            imm8 = instr & 0xFF
            if op3_val == IMM_OPCODES["LI"]:
                self.registers[ra] = (self.registers[ra] & ~0xFF) | imm8
            elif op3_val == IMM_OPCODES["LIHI"]:
                self.registers[ra] = (self.registers[ra] & ~(0xFF << 8)) | (imm8 << 8)
            elif op3_val == IMM_OPCODES["LOAD"]:
                addr = (imm8 + self.registers[REG_MEMOFF]) & ADDR_MASK
                self.registers[ra] = self.memory.read_word28(addr)
            elif op3_val == IMM_OPCODES["STOR"]:
                addr = (imm8 + self.registers[REG_MEMOFF]) & ADDR_MASK
                self.memory.write_word28(addr, self.registers[ra])
            else:
                return ExecResult(ic=ic, halted=False, message="Unknown immediate opcode")

            self.registers[ra] &= WORD_MASK
            self.registers[REG_IC] = next_ic
            return ExecResult(ic=next_ic, halted=False)

        if op3 in (0b010, 0b011):
            op4 = (instr >> 11) & 0xF
            imm11 = instr & 0x7FF
            offset = sign_extend(imm11, 11)
            base = (offset * 2) & ADDR_MASK
            jmpoff = self.registers[REG_JMPOFF] & ADDR_MASK

            def do_jump(use_long: bool) -> None:
                nonlocal next_ic
                addend = base + (jmpoff if use_long else 0)
                next_ic = (ic + addend) & ADDR_MASK

            if op4 == JUMP_OPCODES["JMP"]:
                do_jump(False)
            elif op4 == JUMP_OPCODES["JMPL"]:
                do_jump(True)
            elif op4 == JUMP_OPCODES["JPEQ"]:
                # Assumption for demo: compare R0 and R1.
                if self.registers[0] == self.registers[1]:
                    do_jump(True)
            elif op4 == JUMP_OPCODES["JPBLW"]:
                # Assumption for demo: compare R0 < R1 (unsigned).
                if (self.registers[0] & WORD_MASK) < (self.registers[1] & WORD_MASK):
                    do_jump(True)
            else:
                return ExecResult(ic=ic, halted=False, message="Unknown jump opcode")

            self.registers[REG_IC] = next_ic
            return ExecResult(ic=next_ic, halted=False)

        op7 = (instr >> 8) & 0x7F
        ra = (instr >> 4) & 0xF
        rb = instr & 0xF

        if op7 == GEN_OPCODES["HLT"]:
            self.halted = True
            self.registers[REG_IC] = ic
            return ExecResult(ic=ic, halted=True, message="HLT")

        if op7 == GEN_OPCODES["NOP"]:
            self.registers[REG_IC] = next_ic
            return ExecResult(ic=next_ic, halted=False)

        a_val = self.registers[ra] & WORD_MASK
        b_val = self.registers[rb] & WORD_MASK

        if op7 == RR_OPCODES["NOT"]:
            self.registers[ra] = (~a_val) & WORD_MASK
        elif op7 == RR_OPCODES["OR"]:
            self.registers[ra] = (a_val | b_val) & WORD_MASK
        elif op7 == RR_OPCODES["AND"]:
            self.registers[ra] = (a_val & b_val) & WORD_MASK
        elif op7 == RR_OPCODES["XOR"]:
            self.registers[ra] = (a_val ^ b_val) & WORD_MASK
        elif op7 == RR_OPCODES["SHL"]:
            shift = b_val & 0x1F
            self.registers[REG_SHC] = shift
            self.registers[ra] = (a_val << shift) & WORD_MASK
        elif op7 == RR_OPCODES["SHR"]:
            shift = b_val & 0x1F
            self.registers[REG_SHC] = shift
            self.registers[ra] = (a_val >> shift) & WORD_MASK
        elif op7 == RR_OPCODES["SAR"]:
            shift = b_val & 0x1F
            self.registers[REG_SHC] = shift
            signed = sign_extend(a_val, 28)
            self.registers[ra] = (signed >> shift) & WORD_MASK
        elif op7 == RR_OPCODES["ADD"]:
            self.registers[ra] = (a_val + b_val) & WORD_MASK
        elif op7 == RR_OPCODES["SUB"]:
            self.registers[ra] = (a_val - b_val) & WORD_MASK
        elif op7 == RR_OPCODES["MOV"]:
            self.registers[ra] = b_val & WORD_MASK
        else:
            return ExecResult(ic=ic, halted=False, message="Unknown register opcode")

        self.registers[ra] &= WORD_MASK
        self.registers[REG_IC] = next_ic
        return ExecResult(ic=next_ic, halted=False)
