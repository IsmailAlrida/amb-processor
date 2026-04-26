"""ISA definitions for the AMB (Alrida Muddathir & Basel) Processor."""

INSTR_BITS = 15
INSTR_STORAGE_BITS = 16
INSTR_BYTES = 2
WORD_BITS = 28
WORD_BYTES = 4
ADDR_BITS = 28
REG_BITS = 4
IMM8_BITS = 8

ADDR_MASK = (1 << ADDR_BITS) - 1
WORD_MASK = (1 << WORD_BITS) - 1

REG_NAMES = [
    "R0",
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
    "IC",
    "SP",
    "LC",
    "IMR",
    "JMPOFF",
    "MEMOFF",
    "CMPA",
    "CMPB",
]

REG_ALIASES = {
    "IC": 8,
    "SP": 9,
    "LC": 10,
    "IMR": 11,
    "JMPOFF": 12,
    "MEMOFF": 13,
    "CMPA": 14,
    "CMPB": 15,
}

REG_IC = 8
REG_SP = 9
REG_LC = 10
REG_IMR = 11
REG_JMPOFF = 12
REG_MEMOFF = 13
REG_CMPA = 14
REG_CMPB = 15

RR_OPCODES = {
    "NOT": 0b0010000,
    "OR": 0b0010001,
    "AND": 0b0010010,
    "XOR": 0b0010011,
    "SHL": 0b0010100,
    "SHR": 0b0010101,
    "SAR": 0b0010110,
    "ADD": 0b0010111,
    "SUB": 0b0011000,
    "MOV": 0b0011001,
}

GEN_OPCODES = {
    "HLT": 0b0000000,
    "NOP": 0b0000001,
}

IMM_OPCODES = {
    "LIL": 0b0011010,
    "LIH": 0b0011011,
    "LILL": 0b0011100,
    "LIHH": 0b0011101,
}

MEM_OPCODES = {
    "LOAD": 0b0011110,
    "STOR": 0b0011111,
}

JUMP_OPCODES = {
    "JMP": 0b1000000,
    "JMPL": 0b1000001,
    "JPEQ": 0b1000010,
    "JPBLW": 0b1000011,
}


def encode_rr(opcode7: int, ra: int, rb: int) -> int:
    return ((opcode7 & 0x7F) << 8) | ((rb & 0xF) << 4) | (ra & 0xF)


def encode_imm8(opcode7: int, imm8: int) -> int:
    return ((opcode7 & 0x7F) << 8) | (imm8 & 0xFF)


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)
