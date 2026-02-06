"""Assembler and parser for the AMB ISA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .isa import (
    GEN_OPCODES,
    IMM_OPCODES,
    JUMP_OPCODES,
    RR_OPCODES,
    REG_ALIASES,
    REG_NAMES,
    encode_imm,
    encode_jump,
    encode_rr,
)


class AsmError(Exception):
    def __init__(self, message: str, line_no: Optional[int] = None):
        self.message = message
        self.line_no = line_no
        if line_no is not None:
            super().__init__(f"Line {line_no}: {message}")
        else:
            super().__init__(message)


@dataclass
class Instruction:
    address: int
    line_no: int
    text: str
    mnemonic: str
    operands: List[str]
    encoded: Optional[int] = None


@dataclass
class Program:
    instructions: List[Instruction]
    labels: Dict[str, int]

    @property
    def addr_to_line(self) -> Dict[int, int]:
        return {inst.address: inst.line_no for inst in self.instructions}

    @property
    def words(self) -> List[int]:
        return [inst.encoded or 0 for inst in self.instructions]


COMMENT_MARKERS = ["//", ";", "#"]


def strip_comment(line: str) -> str:
    earliest = None
    for marker in COMMENT_MARKERS:
        idx = line.find(marker)
        if idx != -1:
            if earliest is None or idx < earliest:
                earliest = idx
    if earliest is None:
        return line
    return line[:earliest]


def parse_number(token: str) -> int:
    token = token.replace("_", "").strip()
    if not token:
        raise ValueError("empty number")
    sign = 1
    if token[0] in "+-":
        if token[0] == "-":
            sign = -1
        token = token[1:]
    base = 10
    if token.startswith("0x") or token.startswith("0X"):
        base = 16
        token = token[2:]
    elif token.startswith("0b") or token.startswith("0B"):
        base = 2
        token = token[2:]
    return sign * int(token, base)


def parse_register(token: str, line_no: int) -> int:
    token_u = token.strip().upper()
    if token_u in REG_ALIASES:
        return REG_ALIASES[token_u]
    if token_u.startswith("R") and token_u[1:].isdigit():
        idx = int(token_u[1:])
        if 0 <= idx < len(REG_NAMES):
            return idx
    raise AsmError(f"Unknown register '{token}'", line_no)


def parse_operands(text: str) -> List[str]:
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_lines(source: str) -> Program:
    labels: Dict[str, int] = {}
    instructions: List[Instruction] = []
    pc = 0

    lines = source.splitlines()
    for idx, raw in enumerate(lines, start=1):
        line = strip_comment(raw).strip()
        if not line:
            continue

        while True:
            colon = line.find(":")
            if colon == -1:
                break
            label = line[:colon].strip()
            if not label:
                break
            if not label.replace("_", "A").isalnum() or label[0].isdigit():
                raise AsmError(f"Invalid label '{label}'", idx)
            label_u = label.upper()
            if label_u in labels:
                raise AsmError(f"Duplicate label '{label}'", idx)
            labels[label_u] = pc
            line = line[colon + 1 :].strip()
            if not line:
                break

        if not line:
            continue

        parts = line.split(None, 1)
        mnemonic = parts[0].upper()
        ops_text = parts[1] if len(parts) > 1 else ""
        operands = parse_operands(ops_text)
        instructions.append(
            Instruction(
                address=pc,
                line_no=idx,
                text=raw.rstrip("\n"),
                mnemonic=mnemonic,
                operands=operands,
            )
        )
        pc += 2

    return Program(instructions=instructions, labels=labels)


def _resolve_immediate(token: str, labels: Dict[str, int], line_no: int) -> Tuple[Optional[int], bool]:
    token_u = token.upper()
    if token_u in labels:
        return labels[token_u], True
    try:
        return parse_number(token), False
    except ValueError as exc:
        raise AsmError(f"Invalid immediate '{token}'", line_no) from exc


def assemble(source: str) -> Program:
    program = parse_lines(source)

    for inst in program.instructions:
        mnem = inst.mnemonic
        ops = inst.operands
        line_no = inst.line_no

        if mnem in RR_OPCODES:
            if len(ops) == 1:
                ra = parse_register(ops[0], line_no)
                rb = ra
            elif len(ops) == 2:
                ra = parse_register(ops[0], line_no)
                rb = parse_register(ops[1], line_no)
            else:
                raise AsmError(f"{mnem} expects 1 or 2 registers", line_no)
            inst.encoded = encode_rr(RR_OPCODES[mnem], ra, rb)
            continue

        if mnem in GEN_OPCODES:
            if ops:
                raise AsmError(f"{mnem} expects no operands", line_no)
            inst.encoded = encode_rr(GEN_OPCODES[mnem], 0, 0)
            continue

        if mnem in IMM_OPCODES:
            if len(ops) != 2:
                raise AsmError(f"{mnem} expects register and immediate", line_no)
            ra = parse_register(ops[0], line_no)
            imm_val, is_label = _resolve_immediate(ops[1], program.labels, line_no)
            if is_label:
                raise AsmError(f"{mnem} does not accept labels", line_no)
            if imm_val is None:
                raise AsmError("Missing immediate", line_no)
            if not (-128 <= imm_val <= 255):
                raise AsmError(f"Immediate out of range for {mnem}: {imm_val}", line_no)
            inst.encoded = encode_imm(IMM_OPCODES[mnem], ra, imm_val & 0xFF)
            continue

        if mnem in JUMP_OPCODES:
            if len(ops) != 1:
                raise AsmError(f"{mnem} expects an immediate or label", line_no)
            imm_val, is_label = _resolve_immediate(ops[0], program.labels, line_no)
            if imm_val is None:
                raise AsmError("Missing immediate", line_no)
            if is_label:
                delta = imm_val - inst.address
                if delta % 2 != 0:
                    raise AsmError(f"Label '{ops[0]}' is not 2-byte aligned", line_no)
                imm_val = delta // 2
            if not (-1024 <= imm_val <= 1023):
                raise AsmError(f"Jump offset out of range: {imm_val}", line_no)
            inst.encoded = encode_jump(JUMP_OPCODES[mnem], imm_val & 0x7FF)
            continue

        raise AsmError(f"Unknown instruction '{mnem}'", line_no)

    return program
