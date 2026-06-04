
# Entity: controller 
- **File**: control_unit.v

## Diagram
![Diagram](controller.svg "Diagram")
## Description

Combinational decoder that maps ISA v1 opcodes into CPU datapath control signals.

## Generics

| Generic name     | Type | Value | Description                          |
| ---------------- | ---- | ----- | ------------------------------------ |
| OPCODE_WIDTH     |      | 7     | Width of the ISA opcode field.       |
| CONTROL_OP_WIDTH |      | 4     | Width of the ALU operation selector. |

## Ports

| Port name   | Direction | Type                   | Description                                                         |
| ----------- | --------- | ---------------------- | ------------------------------------------------------------------- |
| clk         | input     |                        | Clock carried for module contract symmetry with the CPU datapath.   |
| reset       | input     |                        | Reset carried for module contract symmetry with the CPU datapath.   |
| opcode      | input     | [OPCODE_WIDTH-1:0]     | Current instruction opcode from instr[14:8].                        |
| MemOp       | output    |                        | Selects memory address generation mode in the CPU ALU operand path. |
| RegWrite    | output    |                        | Enables writes into the register file.                              |
| BranchEqual | output    |                        | Marks JPEQ as the active branch comparison.                         |
| BranchLt    | output    |                        | Marks JPBLW as the active branch comparison.                        |
| isJump      | output    |                        | Asserted for opcodes in the jump opcode space.                      |
| LongJump    | output    |                        | Asserted for jump forms that add JMPOFF to the signed imm8 offset.  |
| isImmLoad   | output    |                        | Asserted for LIL, LIH, LILL, and LIHH.                              |
| WriteEn     | output    |                        | Data memory write enable asserted for STOR.                         |
| ReadEn      | output    |                        | Data memory read enable asserted for LOAD.                          |
| RegDest     | output    | [1:0]                  | Register writeback source selector.                                 |
| ImmSel      | output    | [1:0]                  | IMR lane selector used by immediate load instructions.              |
| ALUCtrl     | output    | [CONTROL_OP_WIDTH-1:0] | ALU operation selector.                                             |
| halt        | output    |                        | Halt flag asserted for HLT.                                         |

## Signals

| Name  | Type | Description                                                              |
| ----- | ---- | ------------------------------------------------------------------------ |
| RTYPE | wire | True when the current opcode is one of the register-register operations. |

## Constants

| Name    | Type | Value      | Description                                    |
| ------- | ---- | ---------- | ---------------------------------------------- |
| set     |      | 1'b1       | Canonical asserted control value.              |
| unset   |      | 1'b0       | Canonical deasserted control value.            |
| HALT    |      | 7'b0000000 | HLT opcode.                                    |
| NOP     |      | 7'b0000001 | NOP opcode.                                    |
| NOT     |      | 7'b0010000 | NOT opcode.                                    |
| OR      |      | 7'b0010001 | OR opcode.                                     |
| AND     |      | 7'b0010010 | AND opcode.                                    |
| XOR     |      | 7'b0010011 | XOR opcode.                                    |
| SHL     |      | 7'b0010100 | SHL opcode.                                    |
| SHR     |      | 7'b0010101 | SHR opcode.                                    |
| SAR     |      | 7'b0010110 | SAR opcode.                                    |
| ADD     |      | 7'b0010111 | ADD opcode.                                    |
| SUB     |      | 7'b0011000 | SUB opcode.                                    |
| MOV     |      | 7'b0011001 | MOV opcode.                                    |
| LIL     |      | 7'b0011010 | LIL opcode for IMR[7:0].                       |
| LIH     |      | 7'b0011011 | LIH opcode for IMR[15:8].                      |
| LILL    |      | 7'b0011100 | LILL opcode for IMR[23:16].                    |
| LIHH    |      | 7'b0011101 | LIHH opcode for IMR[27:24].                    |
| LOAD    |      | 7'b0011110 | LOAD opcode.                                   |
| STOR    |      | 7'b0011111 | STOR opcode.                                   |
| JMP     |      | 7'b1000000 | Direct PC-relative jump opcode.                |
| JMPL    |      | 7'b1000001 | Long PC-relative jump opcode using JMPOFF.     |
| JPEQ    |      | 7'b1000010 | Conditional equal jump opcode using CMPA/CMPB. |
| JPBLW   |      | 7'b1000011 | Conditional below jump opcode using CMPA/CMPB. |
| ALU_NOT |      | 4'b0000    | ALU selector for NOT.                          |
| ALU_OR  |      | 4'b0001    | ALU selector for OR.                           |
| ALU_AND |      | 4'b0010    | ALU selector for AND.                          |
| ALU_XOR |      | 4'b0011    | ALU selector for XOR.                          |
| ALU_SHL |      | 4'b0100    | ALU selector for SHL.                          |
| ALU_SHR |      | 4'b0101    | ALU selector for SHR.                          |
| ALU_SAR |      | 4'b0110    | ALU selector for SAR.                          |
| ALU_ADD |      | 4'b0111    | ALU selector for ADD.                          |
| ALU_SUB |      | 4'b1000    | ALU selector for SUB.                          |
| ALU_MOV |      | 4'b1001    | ALU selector for MOV.                          |

## Processes
- memory_operation_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Range decode for register-register ALU and MOV opcodes.  Decodes LOAD/STOR as memory operations. 
- register_write_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Enables register writes for instructions that produce architectural register data. 
- branch_equal_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Decodes JPEQ equality-branch intent. 
- branch_less_than_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Decodes JPBLW less-than-branch intent. 
- jump_class_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Decodes the jump opcode space. 
- long_jump_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Enables JMPOFF for JMPL and conditional branch opcodes. 
- immediate_load_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Decodes immediate assembly instructions that write IMR lanes. 
- data_memory_write_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Generates the data memory write strobe. 
- data_memory_read_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Generates the data memory read strobe. 
- register_writeback_source_select: ( @(*) )
  - **Type:** always
  - **Description**
  Selects register writeback source: memory, ALU, immediate byte, or zero. 
- immediate_lane_select: ( @(*) )
  - **Type:** always
  - **Description**
  Selects which byte lane of IMR receives the current imm8 value. 
- alu_control_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Maps the current opcode to the ALU operation selector. 
- halt_decode: ( @(*) )
  - **Type:** always
  - **Description**
  Decodes HLT into the core halt signal. 
