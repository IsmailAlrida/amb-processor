
# Entity: cpu 
- **File**: cpu.v

## Diagram
![Diagram](cpu.svg "Diagram")
## Description

Single-cycle AMB CPU core that connects instruction fetch, decode, register file, ALU, and external data memory buses.

## Generics

| Generic name              | Type | Value | Description                                                            |
| ------------------------- | ---- | ----- | ---------------------------------------------------------------------- |
| DATA_ADDR_SPACE           |      | 28    | Width of byte addresses used on the external data memory interface.    |
| DATA_WORD_WIDTH           |      | 28    | Width of architectural data words.                                     |
| INSTRUCTION_WIDTH         |      | 16    | Stored instruction width. Bit 15 is unused by the 15-bit ISA encoding. |
| INSTRUCTION_ADDRESS_SPACE |      | 28    | Width of byte addresses used by the instruction counter.               |
| REG_ADDR_WIDTH            |      | 4     | Number of selector bits used to address one architectural register.    |
| NUM_OF_REGS               |      | 16    | Number of architectural register slots.                                |

## Ports

| Port name       | Direction | Type                            | Description                                                         |
| --------------- | --------- | ------------------------------- | ------------------------------------------------------------------- |
| clk             | input     |                                 | Rising-edge CPU clock.                                              |
| reset           | input     |                                 | Active-high reset for the instruction counter and register file.    |
| halt            | output    |                                 | Asserted when the decoded instruction is HLT.                       |
| IC              | output    | [INSTRUCTION_ADDRESS_SPACE-1:0] | Current byte address presented to instruction memory.               |
| instr           | input     | [INSTRUCTION_WIDTH-1:0]         | Instruction word returned by instruction memory for the current IC. |
| DataAddress     | output    | [DATA_ADDR_SPACE-1:0]           | Byte address presented to external data memory.                     |
| DataMemoryWrite | output    | [DATA_WORD_WIDTH-1:0]           | Data word presented to external data memory on stores.              |
| DataMemoryRead  | input     | [DATA_WORD_WIDTH-1:0]           | Data word returned by external data memory on loads.                |
| DmemReadEn      | output    |                                 | Data memory read enable asserted for LOAD.                          |
| DmemWriteEn     | output    |                                 | Data memory write enable asserted for STOR.                         |

## Signals

| Name          | Type                       | Description                                                                           |
| ------------- | -------------------------- | ------------------------------------------------------------------------------------- |
| ZR            | wire [DATA_WORD_WIDTH-1:0] | Constant zero word used by mux defaults and reset paths.                              |
| WillBranch    | reg                        | Selects branch/jump IC update when high, otherwise selects sequential IC+2.           |
| RegDataWrite  | reg [DATA_WORD_WIDTH-1:0]  | Writeback data selected from data memory, ALU result, immediate byte, or zero.        |
| IC_increment  | wire [DATA_WORD_WIDTH-1:0] | Amount added to IC this cycle.                                                        |
| NextIC        | wire [DATA_WORD_WIDTH-1:0] | Next IC value before the IC register captures it.                                     |
| JumpOffset    | wire [DATA_WORD_WIDTH-1:0] | Signed jump stride after immediate/JMPOFF selection and instruction-word scaling.     |
| LJumpStride   | wire [DATA_WORD_WIDTH-1:0] | Optional long-jump base offset selected from JMPOFF.                                  |
| MEMOFF        | wire [DATA_WORD_WIDTH-1:0] | Current MEMOFF register value used as the memory base offset.                         |
| JMPOFF        | wire [DATA_WORD_WIDTH-1:0] | Current JMPOFF register value used by long jump forms.                                |
| OperandA      | wire [DATA_WORD_WIDTH-1:0] | ALU operand A selected from Ra data or MEMOFF during memory operations.               |
| OperandB      | wire [DATA_WORD_WIDTH-1:0] | ALU operand B sourced from Rb data.                                                   |
| ALURes        | wire [DATA_WORD_WIDTH-1:0] | Combinational ALU result used for writeback, data address, and branch compare result. |
| ImmExtd       | wire [DATA_WORD_WIDTH-1:0] | Zero-extended instruction imm8 field.                                                 |
| ImmExtdSigned | wire [DATA_WORD_WIDTH-1:0] | Sign-extended instruction imm8 field.                                                 |
| ReadDataRb    | wire [DATA_WORD_WIDTH-1:0] | Register file read data for Rb/source selector.                                       |
| ReadDataRa    | wire [DATA_WORD_WIDTH-1:0] | Register file read data for Ra/destination selector.                                  |
| opcode        | wire [6:0]                 | Decoded seven-bit opcode field from instr[14:8].                                      |
| ReadRegRb     | wire [3:0]                 | Register file Rb/source read selector.                                                |
| ReadRegRa     | wire [3:0]                 | Register file Ra/destination read selector.                                           |
| WriteReg      | wire [3:0]                 | Register file write selector.                                                         |
| RegWrite      | wire                       | Enables register file writes for register-producing instructions.                     |
| MemOp         | wire                       | Selects memory address operand mode for LOAD/STOR.                                    |
| LongJump      | wire                       | Enables JMPOFF participation in jump offset calculation.                              |
| isJump        | wire                       | Identifies J-type opcodes.                                                            |
| BranchEqual   | wire                       | Enables equality branch decision for JPEQ.                                            |
| BranchLt      | wire                       | Enables less-than branch decision for JPBLW.                                          |
| isImmLoad     | wire                       | Identifies LIL/LIH/LILL/LIHH immediate assembly instructions.                         |
| zerof         | wire                       | ALU equality flag used by JPEQ.                                                       |
| altb          | wire                       | ALU less-than flag used by JPBLW.                                                     |
| ALUCtrl       | wire [3:0]                 | ALU operation selector generated by the controller.                                   |
| ImmSel        | wire [1:0]                 | Immediate lane selector for IMR writes in the register file.                          |
| CMPType       | wire [2:0]                 | Packed branch decision type: {isJump, BranchEqual, BranchLt}.                         |
| RegDest       | wire [1:0]                 | Register writeback source selector.                                                   |

## Constants

| Name      | Type | Value   | Description                                            |
| --------- | ---- | ------- | ------------------------------------------------------ |
| IMR_ADDR  |      | 4'b1011 | Register selector for the immediate assembly register. |
| CMPA_ADDR |      | 4'b1110 | Register selector for the first compare operand.       |
| CMPB_ADDR |      | 4'b1111 | Register selector for the second compare operand.      |

## Processes
- branch_logic: ( @(*) )
  - **Type:** always
  - **Description**
  Combines jump and conditional branch control bits into one branch decision selector.  Extracts the opcode field from the current instruction.  Extends imm8 as an unsigned value for IMR lane writes.  Extends imm8 as a signed value for PC-relative jump offsets.  Selects JMPOFF only for long jump forms; direct JMP uses zero base.  Calculates byte offset for jump instructions from signed imm8 plus optional JMPOFF.  Selects whether the current instruction branches unconditionally, conditionally, or not at all. 
- instruction_counter_update: ( @(posedge clk or posedge reset) )
  - **Type:** always
  - **Description**
  Selects sequential IC increment or branch/jump offset.  Adds the selected increment to the current IC.  Updates the instruction counter on each active clock edge unless halted. 
- register_writeback_data_select: ( @(*) )
  - **Type:** always
  - **Description**
  Selects CMPB for branch compare instructions, otherwise instr[7:4].  Selects CMPA for branch compare instructions, otherwise instr[3:0].  Directs immediate loads into IMR, otherwise writes the Ra selector.  Selects MEMOFF as operand A for memory address calculation, otherwise Ra data.  Provides Rb data as operand B for ALU and memory address calculation.  Drives the external data memory byte address from the ALU result.  Drives store data from Ra read data.  Selects the data source written back into the register file. 

## Instantiations

- reg_file_inst: reg_file
  -  Architectural register file instance with IMR lane write support.- alu_inst: alu
  -  Combinational ALU instance used for arithmetic, moves, compares, and memory address generation.- controller_inst: controller
  -  Instruction decoder and control signal generator.