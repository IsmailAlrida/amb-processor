
# Entity: dmem 
- **File**: d_memory.v

## Diagram
![Diagram](dmem.svg "Diagram")
## Description

Byte-addressed data memory model with asynchronous reads and synchronous writes.

## Generics

| Generic name    | Type | Value | Description                                           |
| --------------- | ---- | ----- | ----------------------------------------------------- |
| DATA_ADDR_SPACE |      | 28    | Width of the data byte address bus.                   |
| DATA_WORD_WIDTH |      | 28    | Width of each architectural data word.                |
| DEPTH           |      | 4096  | Number of addressable bytes in the data memory image. |

## Ports

| Port name | Direction | Type                  | Description                                                                |
| --------- | --------- | --------------------- | -------------------------------------------------------------------------- |
| clk       | input     |                       | Rising-edge clock for memory writes.                                       |
| reset     | input     |                       | Reset carried for contract symmetry; memory contents are not cleared here. |
| halt      | input     |                       | Halt input that blocks writes when asserted.                               |
| Address   | input     | [DATA_ADDR_SPACE-1:0] | Byte address used for the current read or write.                           |
| DataIn    | input     | [DATA_WORD_WIDTH-1:0] | Data word written to memory on stores.                                     |
| DataOut   | output    | [DATA_WORD_WIDTH-1:0] | Data word read from memory on loads.                                       |
| ReadEn    | input     |                       | Enables the asynchronous read output.                                      |
| WriteEn   | input     |                       | Enables a synchronous memory write.                                        |

## Signals

| Name                | Type         | Description                                       |
| ------------------- | ------------ | ------------------------------------------------- |
| dmemory [0:DEPTH-1] | reg [7:0]    | Byte-addressed data storage loaded from data hex. |
| data_hex            | reg [1023:0] | Runtime path to the data hex image.               |

## Processes
- asynchronous_data_read: ( @(*) )
  - **Type:** always
  - **Description**
  Asynchronously reads a 28-bit little-endian word when ReadEn is asserted. 
- synchronous_data_write: ( @(posedge clk) )
  - **Type:** always
  - **Description**
  Synchronously writes a 28-bit little-endian word when WriteEn is asserted. 
