# AMB ISA RTL Reference

Condensed reference for decoder and datapath work, derived from [ISA.md](./ISA.md) and [ISArequirements.md](./ISArequirements.md).

## Core Facts

| Item | Value |
| --- | --- |
| Instruction encoding width | 15 bits |
| Instruction storage width | 16 bits |
| Instruction storage size | 2 bytes |
| Unused stored bit | 1 bit |
| Register file size | 16 registers |
| Register width | 28 bits |
| Data word width | 28 bits |
| Address width | 28 bits |
| Memory model | Byte-addressable |
| `IC` / program counter | Byte address |
| Normal next instruction | `IC + 2` |

Instruction storage in memory:

```text
byte address N     : [unused][instr[14:8]]
byte address N + 1 : [instr[7:0]]

IC points to byte address N
next IC = IC + 2
```

## Register Select Map

| Sel | Name | Use |
| --- | --- | --- |
| `0000` | `R0` | General purpose |
| `0001` | `R1` | General purpose |
| `0010` | `R2` | General purpose |
| `0011` | `R3` | General purpose |
| `0100` | `R4` | General purpose |
| `0101` | `R5` | General purpose |
| `0110` | `R6` | General purpose |
| `0111` | `R7` | General purpose |
| `1000` | `IC` | Instruction counter |
| `1001` | `SP` | Stack pointer |
| `1010` | `LC` | Loop counter |
| `1011` | `SHC` | Shift count for `SHL/SHR/SAR` |
| `1100` | `JMPOFF` | Extra offset used by long/conditional jumps |
| `1101` | `MEMOFF` | Extra offset used by `LOAD/STOR` |
| `1110` | `CMPA` | Compare operand A |
| `1111` | `CMPB` | Compare operand B |

## Decode Layout

Treat the instruction as `instr[14:0]`.

Family split:

```text
if instr[14:12] is 100..111 -> immediate format
else if instr[14:13] is 01   -> jump format
else                         -> general / reg-reg format
```

Formats:

```text
General / reg-reg:
  [14:8] opcode7
  [7:4]  Ra
  [3:0]  Rb

Jump:
  [14:11] opcode4
  [10:0]  imm11

Immediate:
  [14:12] opcode3
  [11:8]  Ra
  [7:0]   imm8
```

## General And Register Ops

`Ra` is the destination. `Rb` is the source for binary ops.

| opcode7 | Mnemonic | Behavior |
| --- | --- | --- |
| `0000000` | `HLT` | Halt CPU operation |
| `0000001` | `NOP` | No action |
| `0010000` | `NOT Ra` | `Ra = ~Ra` |
| `0010001` | `OR Ra, Rb` | `Ra = Ra OR Rb` |
| `0010010` | `AND Ra, Rb` | `Ra = Ra AND Rb` |
| `0010011` | `XOR Ra, Rb` | `Ra = Ra XOR Rb` |
| `0010100` | `SHL Ra` | `Ra = Ra << SHC` |
| `0010101` | `SHR Ra` | `Ra = Ra >> SHC` |
| `0010110` | `SAR Ra` | `Ra = arithmetic_right_shift(Ra, SHC)` |
| `0010111` | `ADD Ra, Rb` | `Ra = Ra + Rb` |
| `0011000` | `SUB Ra, Rb` | `Ra = Ra - Rb` |
| `0011001` | `MOV Ra, Rb` | `Ra = Rb` |

Shift rules:

- `SHL`, `SHR`, and `SAR` use only `Ra`.
- Encoded `Rb` is ignored for shift ops.
- Shift amount comes from `SHC`.
- If shift amount is `>= 28`:
  - `SHL` result is `0`
  - `SHR` result is `0`
  - `SAR` result is sign-filled

## Jump Ops

Jump immediates are instruction offsets, so hardware shifts `imm11` left by 1 before adding to `IC`.

| opcode4 | Mnemonic | Behavior |
| --- | --- | --- |
| `0100` | `JMP imm11` | `IC = IC + (imm11 << 1)` |
| `0101` | `JMPL imm11` | `IC = IC + (imm11 << 1) + JMPOFF` |
| `0110` | `JPEQ imm11` | If `CMPA == CMPB`, do `JMPL` |
| `0111` | `JPBLW imm11` | If `CMPA < CMPB`, do `JMPL` |

Notes:

- `JPEQ` and `JPBLW` compare only `CMPA` and `CMPB`.
- To compare arbitrary registers, move values into `CMPA` and `CMPB` first.

## Immediate Ops

| opcode3 | Mnemonic | Behavior |
| --- | --- | --- |
| `100` | `LIL Ra, imm8` | Set `Ra[7:0] = imm8` |
| `101` | `LIH Ra, imm8` | Set `Ra[15:8] = imm8` |
| `110` | `LOAD Ra, imm8` | `Ra = MEM[imm8 + MEMOFF]` as a 28-bit word |
| `111` | `STOR Ra, imm8` | `MEM[imm8 + MEMOFF] = Ra` as a 28-bit word |

Notes:

- `LIL` changes only bits `7:0`.
- `LIH` changes only bits `15:8`.
- `LOAD` and `STOR` use the byte address `imm8 + MEMOFF`.

## RTL Checklist

- Keep register results masked to 28 bits.
- Increment `IC` by 2 after normal instruction execution.
- Use byte addressing for `IC` and memory effective addresses.
- Make `SHL/SHR/SAR` read shift count from `SHC`, not `Rb`.
- Make `JPEQ/JPBLW` compare `CMPA` and `CMPB` only.
- Make `JMPL/JPEQ/JPBLW` add `JMPOFF`; plain `JMP` does not.

## Clarifications To Lock Down In RTL

These are not stated cleanly in the original prose docs, so they are worth deciding explicitly in RTL:

- Whether `imm11` is signed or unsigned for jumps.
- Whether `JPBLW` is signed or unsigned compare.
- Whether `LOAD/STOR` require aligned addresses for 28-bit word transfers.

Current repo software model behavior:

- `imm11` is sign-extended before the jump offset is applied.
- `JPBLW` uses an unsigned comparison.
- Register select values follow the table above.
