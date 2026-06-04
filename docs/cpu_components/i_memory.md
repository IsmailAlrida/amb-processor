
# Entity: imem 
- **File**: i_memory.v

## Diagram
![Diagram](imem.svg "Diagram")
## Description

Byte-addressed instruction memory model with asynchronous instruction fetch.

## Generics

| Generic name              | Type | Value | Description                                      |
| ------------------------- | ---- | ----- | ------------------------------------------------ |
| INSTRUCTION_WIDTH         |      | 16    | Width of each returned instruction word.         |
| INSTRUCTION_ADDRESS_SPACE |      | 28    | Width of the instruction byte address bus.       |
| DEPTH                     |      | 4096  | Number of addressable bytes in the memory image. |

## Ports

| Port name | Direction | Type                            | Description                                                                |
| --------- | --------- | ------------------------------- | -------------------------------------------------------------------------- |
| clk       | input     |                                 | Clock carried for contract symmetry with the CPU core.                     |
| reset     | input     |                                 | Reset carried for contract symmetry; memory contents are not cleared here. |
| halt      | input     |                                 | Halt carried for contract symmetry with the CPU core.                      |
| IC        | input     | [INSTRUCTION_ADDRESS_SPACE-1:0] | Byte address of the instruction to fetch.                                  |
| instr     | output    | [INSTRUCTION_WIDTH-1:0]         | Instruction word assembled from two adjacent bytes.                        |

## Signals

| Name                | Type         | Description                                                 |
| ------------------- | ------------ | ----------------------------------------------------------- |
| imemory [0:DEPTH-1] | reg [7:0]    | Byte-addressed instruction storage loaded from program hex. |
| program_hex         | reg [1023:0] | Runtime path to the program hex image.                      |

## Processes
- asynchronous_instruction_fetch: ( @(*) )
  - **Type:** always
  - **Description**
  Asynchronously returns the 16-bit instruction at the current byte address. 
