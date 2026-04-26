/*
    Meet the top-level of the processor. This is where we will glue all the bits and pieces together.
    Ultimately, we will just implement a simple single-cycle fetch-decode-execute here for this version.
*/
//! Single-cycle AMB CPU core that connects instruction fetch, decode, register file, ALU, and external data memory buses.
module cpu #(
    //! Width of byte addresses used on the external data memory interface.
    parameter DATA_ADDR_SPACE = 28,

    //! Width of architectural data words.
    parameter DATA_WORD_WIDTH = 28,

    //! Stored instruction width. Bit 15 is unused by the 15-bit ISA encoding.
    parameter INSTRUCTION_WIDTH = 16,

    //! Width of byte addresses used by the instruction counter.
    parameter INSTRUCTION_ADDRESS_SPACE = 28,

    //! Number of selector bits used to address one architectural register.
    parameter REG_ADDR_WIDTH = 4,

    //! Number of architectural register slots.
    parameter NUM_OF_REGS = 16
) (
    //! Rising-edge CPU clock.
    input clk,
    //! Active-high reset for the instruction counter and register file.
    input reset,
    //! Asserted when the decoded instruction is HLT.
    output halt,
    //! Current byte address presented to instruction memory.
    output reg [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    //! Instruction word returned by instruction memory for the current IC.
    input [INSTRUCTION_WIDTH-1:0] instr,
    //! Byte address presented to external data memory.
    output [DATA_ADDR_SPACE-1:0] DataAddress,
    //! Data word presented to external data memory on stores.
    output [DATA_WORD_WIDTH-1:0] DataMemoryWrite,
    //! Data word returned by external data memory on loads.
    input [DATA_WORD_WIDTH-1:0] DataMemoryRead,
    //! Data memory read enable asserted for LOAD.
    output DmemReadEn,
    //! Data memory write enable asserted for STOR.
    output DmemWriteEn
);

    //! Register selector for the immediate assembly register.
    localparam [3:0] IMR_ADDR = 4'b1011;
    //! Register selector for the first compare operand.
    localparam [3:0] CMPA_ADDR = 4'b1110;
    //! Register selector for the second compare operand.
    localparam [3:0] CMPB_ADDR = 4'b1111;

    //! Constant zero word used by mux defaults and reset paths.
    wire [DATA_WORD_WIDTH-1:0] ZR;
    assign ZR = 28'h0000000;

    //! Selects branch/jump IC update when high, otherwise selects sequential IC+2.
    reg WillBranch;
    //! Writeback data selected from data memory, ALU result, immediate byte, or zero.
    reg [DATA_WORD_WIDTH-1:0] RegDataWrite;

    //! Amount added to IC this cycle.
    wire [DATA_WORD_WIDTH-1:0] IC_increment;
    //! Next IC value before the IC register captures it.
    wire [DATA_WORD_WIDTH-1:0] NextIC;
    //! Signed jump stride after immediate/JMPOFF selection and instruction-word scaling.
    wire [DATA_WORD_WIDTH-1:0] JumpOffset;
    //! Optional long-jump base offset selected from JMPOFF.
    wire [DATA_WORD_WIDTH-1:0] LJumpStride;
    //! Current MEMOFF register value used as the memory base offset.
    wire [DATA_WORD_WIDTH-1:0] MEMOFF;
    //! Current JMPOFF register value used by long jump forms.
    wire [DATA_WORD_WIDTH-1:0] JMPOFF;
    //! ALU operand A selected from Ra data or MEMOFF during memory operations.
    wire [DATA_WORD_WIDTH-1:0] OperandA;
    //! ALU operand B sourced from Rb data.
    wire [DATA_WORD_WIDTH-1:0] OperandB;
    //! Combinational ALU result used for writeback, data address, and branch compare result.
    wire [DATA_WORD_WIDTH-1:0] ALURes;
    //! Zero-extended instruction imm8 field.
    wire [DATA_WORD_WIDTH-1:0] ImmExtd;
    //! Sign-extended instruction imm8 field.
    wire [DATA_WORD_WIDTH-1:0] ImmExtdSigned;
    //! Register file read data for Rb/source selector.
    wire [DATA_WORD_WIDTH-1:0] ReadDataRb;
    //! Register file read data for Ra/destination selector.
    wire [DATA_WORD_WIDTH-1:0] ReadDataRa;

    // Register select and decode wires
    //! Decoded seven-bit opcode field from instr[14:8].
    wire [6:0] opcode;
    //! Register file Rb/source read selector.
    wire [3:0] ReadRegRb;
    //! Register file Ra/destination read selector.
    wire [3:0] ReadRegRa;
    //! Register file write selector.
    wire [3:0] WriteReg;

    // Control wires
    //! Enables register file writes for register-producing instructions.
    wire RegWrite;
    //! Selects memory address operand mode for LOAD/STOR.
    wire MemOp;
    //! Enables JMPOFF participation in jump offset calculation.
    wire LongJump;
    //! Identifies J-type opcodes.
    wire isJump;
    //! Enables equality branch decision for JPEQ.
    wire BranchEqual;
    //! Enables less-than branch decision for JPBLW.
    wire BranchLt;
    //! Identifies LIL/LIH/LILL/LIHH immediate assembly instructions.
    wire isImmLoad;

    // ALU Flags
    //! ALU equality flag used by JPEQ.
    wire zerof;
    //! ALU less-than flag used by JPBLW.
    wire altb;

    // Control Multi-bit flags
    //! ALU operation selector generated by the controller.
    wire [3:0] ALUCtrl;
    //! Immediate lane selector for IMR writes in the register file.
    wire [1:0] ImmSel; // This ons is for reg file
    //! Packed branch decision type: {isJump, BranchEqual, BranchLt}.
    wire [2:0] CMPType;
    //! Register writeback source selector.
    wire [1:0] RegDest; // This is 2 bit cuz we can write either from mem, from ALU, or from Imm

    // Just for niceness. BranchType 1 = CMP action A==B, 0 = CMP Action A<B
    //! Combines jump and conditional branch control bits into one branch decision selector.
    assign CMPType = {isJump, BranchEqual, BranchLt};
    //! Extracts the opcode field from the current instruction.
    assign opcode        = instr[14:8];
    //! Extends imm8 as an unsigned value for IMR lane writes.
    assign ImmExtd       = {{(DATA_WORD_WIDTH-8){1'b0}},     instr[7:0]};
    //! Extends imm8 as a signed value for PC-relative jump offsets.
    assign ImmExtdSigned = {{(DATA_WORD_WIDTH-8){instr[7]}}, instr[7:0]};

    // Instruction Counter Path

    // Muxed by LongJump to be JMPOFF or zero, it is the offset added to immediates in jump instructions
    //! Selects JMPOFF only for long jump forms; direct JMP uses zero base.
    assign LJumpStride = LongJump ? JMPOFF : ZR;
    // TODO: Signed or unsigned jumps

    // Used to calculate IC Increment in jump instruction. JumpOffset = (ImmExtdSigned + LJumpStride) * 2.
    //! Calculates byte offset for jump instructions from signed imm8 plus optional JMPOFF.
    assign JumpOffset = (ImmExtdSigned + LJumpStride) << 1;

    // MSB of CMPType is 
    //! Selects whether the current instruction branches unconditionally, conditionally, or not at all.
    always @(*) begin : branch_logic
        casez (CMPType)
            3'b100: WillBranch = 1'b1;
            3'b110: WillBranch = zerof;
            3'b101: WillBranch = altb;
            default: WillBranch = ZR[0];
        endcase
    end

    //! Selects sequential IC increment or branch/jump offset.
    assign IC_increment = WillBranch ? JumpOffset : 28'd2;
    //! Adds the selected increment to the current IC.
    assign NextIC = IC + IC_increment;

    // This is the instruction counter loop
    //! Updates the instruction counter on each active clock edge unless halted.
    always @(posedge clk or posedge reset) begin : instruction_counter_update
        if (reset) begin
            IC <= ZR;
        end else if (!halt) begin
            IC <= NextIC;
        end
    end

    // To Reg File
    //! Selects CMPB for branch compare instructions, otherwise instr[7:4].
    assign ReadRegRb = isJump ? CMPB_ADDR : instr[7:4];
    //! Selects CMPA for branch compare instructions, otherwise instr[3:0].
    assign ReadRegRa = isJump ? CMPA_ADDR : instr[3:0];
    //! Directs immediate loads into IMR, otherwise writes the Ra selector.
    assign WriteReg = isImmLoad ? IMR_ADDR : instr[3:0];

    // ALU Operand Muxing
    //! Selects MEMOFF as operand A for memory address calculation, otherwise Ra data.
    assign OperandA = MemOp ? MEMOFF : ReadDataRa; 
    //! Provides Rb data as operand B for ALU and memory address calculation.
    assign OperandB = ReadDataRb; 

    //! Drives the external data memory byte address from the ALU result.
    assign DataAddress = ALURes;
    //! Drives store data from Ra read data.
    assign DataMemoryWrite = ReadDataRa;
  

    // This is to specify where the data for the register write comes from
    //! Selects the data source written back into the register file.
    always @(*) begin : register_writeback_data_select
        case (RegDest)
            2'b00: RegDataWrite = DataMemoryRead;
            2'b01: RegDataWrite = ALURes;
            2'b10: RegDataWrite = ImmExtd;
            2'b11: RegDataWrite = ZR;
        endcase
    end



    // Register File
    //! Architectural register file instance with IMR lane write support.
    // TODO: Register file-related glue is done. Move on
    reg_file #(
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
        .ADDR_WIDTH(REG_ADDR_WIDTH),
        .NUM_OF_REGS(NUM_OF_REGS)
    ) reg_file_inst (
        .clk(clk),
        .reset(reset),
        .halt(halt),
        .ReadAddrRb(ReadRegRb),
        .ReadAddrRa(ReadRegRa),
        .WriteAddr(WriteReg),
        .WriteData(RegDataWrite),
        .RegWrite(RegWrite),
        .ReadDataRb(ReadDataRb),
        .ReadDataRa(ReadDataRa),
        .MEMOFF_OUT(MEMOFF),
        .JMPOFF_OUT(JMPOFF),
        .ImmSel(ImmSel)
    );

    // ALU
    //! Combinational ALU instance used for arithmetic, moves, compares, and memory address generation.
    alu #(
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH)
    ) alu_inst (
        .clk(clk),
        .reset(reset),
        .halt(halt),
        .OperandA(OperandA),
        .OperandB(OperandB),
        .ALUCtrl(ALUCtrl),
        .result(ALURes),
        .zero(zerof),
        .altb(altb) // Flag for A less than B
    );

    // Control Unit
    //! Instruction decoder and control signal generator.
    controller #(
    ) controller_inst (
        .clk(clk),
        .reset(reset),
        .opcode(opcode),
        .MemOp(MemOp),
        .RegWrite(RegWrite),
        .BranchEqual(BranchEqual),
        .BranchLt(BranchLt),
        .isJump(isJump),
        .LongJump(LongJump),
        .isImmLoad(isImmLoad),
        .WriteEn(DmemWriteEn),
        .ReadEn(DmemReadEn),
        .RegDest(RegDest),
        .ImmSel(ImmSel),
        .ALUCtrl(ALUCtrl),
        .halt(halt)
    );
endmodule
