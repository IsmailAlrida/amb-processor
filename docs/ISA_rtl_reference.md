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

## Suggestions 

what if we make the opcode field directly just 7 bits cash, and play around with the rest

```text
General / reg-reg:
  [14:8] opcode
  [7:4]  Ra
  [3:0]  Rb

Jump:
  [14:8] opcode
  [7:0]  imm8

Immediate:
  [14:8] opcode
  [7:0]   imm8
```

This way jumps just become referenced to what is in JMPOFF + an 8-bit offset.

Immediates? We make a special purpose register called IMR for carryinh immediates.

28-bits is like

| 4-bits | 8-bits | 8-bits | 8-bits |

So we can load an immediate in 4 cycles

```verilog

reg [27:0] IMR;
reg [7:0] incoming_immediate;
reg [1:0] slot;


 
always @(*) 
begin
  case(slot)
    2'b00: IMR[7:0] = incoming_immediate;
    2'b01: IMR[15:8] = incoming_immediate;
    2'b10: IMR[23:16] = incoming_immediate;
    2'b11: IMR[27:24] = incoming_immediate[3:0];
  endcase
end

```

And we can just make four immediate load instructions now that we have 2^7 possible instructions. Pretty cool, right?

so it would look something like this:

``` assembly
; Go off on a limb: LIL/LIH -> [15:0] and LILL/LIHH -> [27:16]
LIL  32
LIH  45
LILL 66
LIHH 255 ;this will get truncated, but argument for it is IF we go 32 bit mode we really dont lose much

MOV r1, imr ;now we just move the imr value to r1
```

Thus, after these instructions, we would have:

| 4-bits | 8-bits | 8-bits | 8-bits |
| --- | --- | --- | --- |
| 1111 | 01000010 | 00101101 | 00100000 |


As for the memory load/store instructions?
Why use a direct 8 bit immediate when you can just do the same thing but read from a register reference.

behaviorwise we can always have 

| [14:8] opcode | Mnemonic | Behavior |
| --- | --- | --- |
| dunno | `LIL imm8` | Set `IMR[7:0] = imm8` |
| dunno | `LIH imm8` | Set `IMR[15:8] = imm8` |
| dunno | `LILL imm8` | Set `IMR[23:16] = imm8` |
| dunno | `LIHH imm8` | Set `IMR[27:24] = imm8` |
| dunno | `LOAD Ra, Rb` | `Ra = MEM[Rb + MEMOFF]` as a 28-bit word |
| dunno | `STOR Ra, Rb` | `MEM[Rb + MEMOFF] = Ra` as a 28-bit word |


Annnnnd what if we rebrand MEMOFF as a "segmenter" since that was what we originally had in mind.

### Suggested Register Quick Reference

Suggested 16-slot register map under the ideas above:

| Sel | Name | Role | Notes |
| --- | --- | --- | --- |
| `0000` | `R0` | General purpose | Unchanged general-purpose register |
| `0001` | `R1` | General purpose | Unchanged general-purpose register |
| `0010` | `R2` | General purpose | Unchanged general-purpose register |
| `0011` | `R3` | General purpose | Unchanged general-purpose register |
| `0100` | `R4` | General purpose | Unchanged general-purpose register |
| `0101` | `R5` | General purpose | Unchanged general-purpose register |
| `0110` | `R6` | General purpose | Unchanged general-purpose register |
| `0111` | `R7` | General purpose | Unchanged general-purpose register |
| `1000` | `R8` | General purpose | Yeah we wont IC in the reg file. it's gonna be independent component |
| `1001` | `SP` | Stack pointer | Preserved in the suggested model |
| `1010` | `LC` | Loop counter | Preserved in the suggested model |
| `1011` | `IMR` | Immediate assembly register | Replaces the former `SHC` slot in this suggested model |
| `1100` | `JMPOFF` | Jump base offset | Base offset used by the 8-bit jump forms |
| `1101` | `MEMOFF` | Memory base / segment register | Kept as `MEMOFF`, but treated conceptually as a segment/base register |
| `1110` | `CMPA` | Compare operand A | Used by conditional jump compares |
| `1111` | `CMPB` | Compare operand B | Used by conditional jump compares |

soooo

| opcode7 | Mnemonic | Behavior |
| --- | --- | --- |
| `0000000` | `HLT` | Halt CPU operation |
| `0000001` | `NOP` | No action |
| `0010000` | `NOT Ra` | `Ra = ~Ra` |
| `0010001` | `OR Ra, Rb` | `Ra = Ra OR Rb` |
| `0010010` | `AND Ra, Rb` | `Ra = Ra AND Rb` |
| `0010011` | `XOR Ra, Rb` | `Ra = Ra XOR Rb` |
| `0010100` | `SHL Ra, Rb` | `Ra = Ra << Rb` |
| `0010101` | `SHR Ra, Rb` | `Ra = Ra >> Rb` |
| `0010110` | `SAR Ra, Rb` | `Ra = arithmetic_right_shift(Ra, Rb)` |
| `0010111` | `ADD Ra, Rb` | `Ra = Ra + Rb` |
| `0011000` | `SUB Ra, Rb` | `Ra = Ra - Rb` |
| `0011001` | `MOV Ra, Rb` | `Ra = Rb` |
| `0011010` | `LIL imm8` | Set `IMR[7:0] = imm8` |
| `0011011` | `LIH imm8` | Set `IMR[15:8] = imm8` |
| `0011100` | `LILL imm8` | Set `IMR[23:16] = imm8` |
| `0011101` | `LIHH imm8` | Set `IMR[27:24] = imm[3:0]` |
| `0011110` | `LOAD Ra, Rb` | `Ra = MEM[Rb + MEMOFF]` as a 28-bit word |
| `0011111` | `STOR Ra, Rb` | `MEM[Rb + MEMOFF] = Ra` as a 28-bit word |
| `1000000` | `JMP imm8` | `IC = IC + (imm8 << 1)` |
| `1000001` | `JMPL imm8` | `IC = IC + ( (imm8 + JMPOFF) << 1) ` |
| `1000010` | `JPEQ imm8` | If `CMPA == CMPB`, do `JMPL` |
| `1000011` | `JPBLW imm8` | If `CMPA < CMPB`, do `JMPL` |
| `1000100` | `JMPR Ra` | `IC = IC + (Ra << 1)` | 

maybe let's not do JMPR. It's more headache than necessary for this version especially.

I dont see why we need SHC, especially because it complicates stuff on the hardware side when we can just make it a register-register op.

Reg-reg instructions

| 14:8 | 7:4 | 3:0 |
| --- | --- | --- |
| Opcode | Rb | Ra |

Immediate Load + Jumps

| 14:8 | 7:0 |
| --- | --- |
| Opcode | imm8 |

rb is source, ra is destination

## RTL Implementation Helper Notes

These notes capture the current RTL-facing contract for wiring `cpu.v` and the module shells.

### Field Roles

| Field | Role | RTL meaning |
| --- | --- | --- |
| `instr[14:8]` | `opcode7` | Controller decode input |
| `instr[7:4]` | `Rb` | Source register |
| `instr[3:0]` | `Ra` | Destination register |
| `instr[7:0]` | `imm8` | Immediate payload for immediate loads and jumps |

### Datapath Contract

| Path | Contract |
| --- | --- |
| ALU register ops | `OperandA = Ra`, `OperandB = Rb`, result writes back to `Ra` |
| `MOV Ra, Rb` | ALU should output `OperandB` |
| `LOAD Ra, Rb` | Address is `Rb + MEMOFF`; memory read value writes to `Ra` |
| `STOR Ra, Rb` | Address is `Rb + MEMOFF`; memory write data is `Ra` |
| Immediate loads | `imm8` is zero-extended onto writeback data and written into `IMR` |
| Normal PC update | `IC = IC + 2` |
| Jump PC update | `IC = IC + JumpOffset` |

### Control Signal Contracts

| Signal | Values / meaning |
| --- | --- |
| `RegDest` | `00`: memory read, `01`: ALU result, `10`: immediate, `11`: zero |
| `ImmSel` | `00`: `LIL`, `01`: `LIH`, `10`: `LILL`, `11`: `LIHH` |
| `isImmLoad` | Selects `IMR` as the register-file write address |
| `MemOp` | Selects memory-address ALU operands: `Rb + MEMOFF` |
| `isJump` | Enables jump/branch register reads from `CMPA` and `CMPB` |
| `BranchEqual` | Conditional branch uses ALU `zero` flag |
| `BranchLt` | Conditional branch uses ALU `altb` flag |
| `LongJump` | Adds `JMPOFF` into the jump stride calculation |
| `halt` | Freezes `IC` update when asserted |

### Immediate Register Lane Map

| `ImmSel` | Mnemonic | IMR lane written |
| --- | --- | --- |
| `00` | `LIL imm8` | `IMR[7:0]` |
| `01` | `LIH imm8` | `IMR[15:8]` |
| `10` | `LILL imm8` | `IMR[23:16]` |
| `11` | `LIHH imm8` | `IMR[27:24] = imm8[3:0]` |

### External Memory Interface

`cpu.v` treats instruction and data memory as external modules:

| CPU port | Direction | Connects to |
| --- | --- | --- |
| `IC` | output | Instruction memory address input |
| `instr` | input | Instruction memory instruction output |
| `DataAddress` | output | Data memory address input |
| `DataMemoryWrite` | output | Data memory write-data input |
| `DataMemoryRead` | input | Data memory read-data output |
| `DmemReadEn` | output | Data memory read enable |
| `DmemWriteEn` | output | Data memory write enable |
