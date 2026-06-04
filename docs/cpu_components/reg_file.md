
# Entity: reg_file 
- **File**: reg_file.v

## Diagram
![Diagram](reg_file.svg "Diagram")
## Description

Sixteen-slot architectural register file with asynchronous reads and synchronous writes.

## Generics

| Generic name    | Type | Value | Description                                       |
| --------------- | ---- | ----- | ------------------------------------------------- |
| DATA_WORD_WIDTH |      | 28    | Width of each register word.                      |
| ADDR_WIDTH      |      | 4     | Width of each register selector.                  |
| NUM_OF_REGS     |      | 16    | Number of register slots implemented by the file. |

## Ports

| Port name  | Direction | Type                  | Description                                                 |
| ---------- | --------- | --------------------- | ----------------------------------------------------------- |
| clk        | input     |                       | Rising-edge clock for register writes.                      |
| reset      | input     |                       | Active-high reset that clears all register slots.           |
| halt       | input     |                       | Halt input that blocks further writes when asserted.        |
| ReadAddrRb | input     | [ADDR_WIDTH-1:0]      | Source register selector for Rb.                            |
| ReadAddrRa | input     | [ADDR_WIDTH-1:0]      | Destination register selector for Ra.                       |
| WriteAddr  | input     | [ADDR_WIDTH-1:0]      | Register selector targeted by the writeback port.           |
| WriteData  | input     | [DATA_WORD_WIDTH-1:0] | Data presented to the writeback port.                       |
| RegWrite   | input     |                       | Write enable for the writeback port.                        |
| ReadDataRb | output    | [DATA_WORD_WIDTH-1:0] | Asynchronous read data for Rb.                              |
| ReadDataRa | output    | [DATA_WORD_WIDTH-1:0] | Asynchronous read data for Ra.                              |
| MEMOFF_OUT | output    | [DATA_WORD_WIDTH-1:0] | Current MEMOFF register value exported to the CPU datapath. |
| JMPOFF_OUT | output    | [DATA_WORD_WIDTH-1:0] | Current JMPOFF register value exported to the CPU datapath. |
| ImmSel     | input     | [1:0]                 | IMR byte-lane selector for immediate assembly writes.       |

## Signals

| Name                       | Type                      | Description                                           |
| -------------------------- | ------------------------- | ----------------------------------------------------- |
| i                          | integer                   | Loop index used when reset clears the register array. |
| registry [0:NUM_OF_REGS-1] | reg [DATA_WORD_WIDTH-1:0] | Backing storage for all architectural register slots. |

## Constants

| Name   | Type | Value   | Description                                                |
| ------ | ---- | ------- | ---------------------------------------------------------- |
| R0     |      | 4'b0000 | Register selector for general register R0.                 |
| R1     |      | 4'b0001 | Register selector for general register R1.                 |
| R2     |      | 4'b0010 | Register selector for general register R2.                 |
| R3     |      | 4'b0011 | Register selector for general register R3.                 |
| R4     |      | 4'b0100 | Register selector for general register R4.                 |
| R5     |      | 4'b0101 | Register selector for general register R5.                 |
| R6     |      | 4'b0110 | Register selector for general register R6.                 |
| R7     |      | 4'b0111 | Register selector for general register R7.                 |
| R8     |      | 4'b1000 | Register selector for the instruction counter mirror slot. |
| SP     |      | 4'b1001 | Register selector for the stack pointer slot.              |
| LC     |      | 4'b1010 | Register selector for the loop counter slot.               |
| IMR    |      | 4'b1011 | Register selector for the immediate assembly register.     |
| JMPOFF |      | 4'b1100 | Register selector for the long-jump base offset.           |
| MEMOFF |      | 4'b1101 | Register selector for the memory base offset.              |
| CMPA   |      | 4'b1110 | Register selector for the first compare operand.           |
| CMPB   |      | 4'b1111 | Register selector for the second compare operand.          |

## Processes
- asynchronous_register_read: ( @(*) )
  - **Type:** always
  - **Description**
  Asynchronously reads the selected Ra and Rb register slots. 
- synchronous_register_write: ( @(posedge clk or posedge reset) )
  - **Type:** always
  - **Description**
  Exposes MEMOFF directly for memory address generation.  Exposes JMPOFF directly for long jump address generation.  Synchronously clears registers on reset and writes either a full register or an IMR lane. 
