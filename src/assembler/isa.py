"""ISA definitions for the AMB (Alrida Muddathir & Basel) Processor."""

INSTR_BITS = 15
INSTR_STORAGE_BITS = 16
INSTR_BYTES = 2
WORD_BITS = 28
WORD_BYTES = 4
ADDR_BITS = 28
REG_BITS = 4
IMM8_BITS = 8
IMM11_BITS = 11

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
    "SHC",
    "JMPOFF",
    "MEMOFF",
    "R14",
    "R15",
]

REG_ALIASES = {
    "IC": 8,
    "SP": 9,
    "LC": 10,
    "SHC": 11,
    "JMPOFF": 12,
    "MEMOFF": 13,
}

REG_IC = 8
REG_SP = 9
REG_LC = 10
REG_SHC = 11
REG_JMPOFF = 12
REG_MEMOFF = 13

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

JUMP_OPCODES = {
    "JMP": 0b0100,
    "JMPL": 0b0101,
    "JPEQ": 0b0110,
    "JPBLW": 0b0111,
}

IMM_OPCODES = {
    "LI": 0b100,
    "LIHI": 0b101,
    "LOAD": 0b110,
    "STOR": 0b111,
}


def encode_rr(opcode7: int, ra: int, rb: int) -> int:
    return ((opcode7 & 0x7F) << 8) | ((ra & 0xF) << 4) | (rb & 0xF)


def encode_jump(opcode4: int, imm11: int) -> int:
    return ((opcode4 & 0xF) << 11) | (imm11 & 0x7FF)


def encode_imm(opcode3: int, ra: int, imm8: int) -> int:
    return ((opcode3 & 0x7) << 12) | ((ra & 0xF) << 8) | (imm8 & 0xFF)


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)
