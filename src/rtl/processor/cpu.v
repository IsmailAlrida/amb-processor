/*
    Meet the top-level of the processor. This is where we will glue all the bits and pieces together.
    Ultimately, we will just implement a simple single-cycle fetch-decode-execute here for this version.
*/
module cpu #(
    //! Width of the data memory address bus
    parameter DATA_ADDR_SPACE = 28,

    //! Width of the data word (bits)
    parameter DATA_WORD_WIDTH = 28,

    //! Total bits per instruction (Standard: 16-bit)
    parameter INSTRUCTION_WIDTH = 16,

    //! Width of the instruction memory address bus
    parameter INSTRUCTION_ADDRESS_SPACE = 28,

    //! Number of bits that address the register file
    parameter REG_ADDR_WIDTH = 4,

    //! Total number of physical registers available
    parameter NUM_OF_REGS = 16
) (
    //! CPU clock
    input clk,
    //! External Reset
    input reset,
    //! Internally-generated halt on "HLT" instructions
    output halt,
    //! Instruction counter
    output reg [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    //! Instruction data from instruction memory
    input [INSTRUCTION_WIDTH-1:0] instr,
    //! Address of memory to read from
    output [DATA_ADDR_SPACE-1:0] DataAddress,
    //! Data to be written into the data memory
    output [DATA_WORD_WIDTH-1:0] DataMemoryWrite,
    //! Data incoming from data memory
    input [DATA_WORD_WIDTH-1:0] DataMemoryRead,
    //! Memory read enable
    output DmemReadEn,
    //! Memory write enable
    output DmemWriteEn
);

    //! Address value of the IMmediate Register (IMR)
    localparam [3:0] IMR_ADDR = 4'b1011;
    //! Address value of the CMPA register
    localparam [3:0] CMPA_ADDR = 4'b1110;
    //! Address value of the CMPB register
    localparam [3:0] CMPB_ADDR = 4'b1111;

    //! Global Zero Register
    wire [DATA_WORD_WIDTH-1:0] ZR;
    assign ZR = 28'h0000000;

    //! Branch or increment flag. If 0, will increment IC by 2. If 1, will use JumpOffset for increment.
    reg WillBranch;
    //! Multiplexed data bus to choose who writes to the regiter file: Data memory, ALU Result, 
    reg [DATA_WORD_WIDTH-1:0] RegDataWrite;

    //! Datapath wires
    wire [DATA_WORD_WIDTH-1:0] IC_increment, NextIC, JumpOffset, LJumpStride;
    wire [DATA_WORD_WIDTH-1:0] MEMOFF, JMPOFF, OperandA, OperandB, ALURes;
    wire [DATA_WORD_WIDTH-1:0] ImmExtd, ImmExtdSigned;
    wire [DATA_WORD_WIDTH-1:0] ReadDataRb, ReadDataRa;

    // Register select and decode wires
    wire [6:0] opcode;
    wire [3:0] ReadRegRb, ReadRegRa, WriteReg;

    // Control wires
    wire RegWrite, MemOp, LongJump, isJump, BranchEqual, BranchLt, isImmLoad;

    // ALU Flags
    wire zerof, altb;

    // Control Multi-bit flags
    wire [3:0] ALUCtrl;
    wire [1:0] ImmSel; // This ons is for reg file
    wire [2:0] CMPType;
    wire [1:0] RegDest; // This is 2 bit cuz we can write either from mem, from ALU, or from Imm

    // Just for niceness. BranchType 1 = CMP action A==B, 0 = CMP Action A<B
    assign CMPType = {isJump, BranchEqual, BranchLt};
    assign opcode        = instr[14:8];
    assign ImmExtd       = {{(DATA_WORD_WIDTH-8){1'b0}},     instr[7:0]};
    assign ImmExtdSigned = {{(DATA_WORD_WIDTH-8){instr[7]}}, instr[7:0]};

    // Instruction Counter Path

    // Muxed by LongJump to be JMPOFF or zero, it is the offset added to immediates in jump instructions
    assign LJumpStride = LongJump ? JMPOFF : ZR;
    // TODO: Signed or unsigned jumps

    // Used to calculate IC Increment in jump instruction. JumpOffset = (ImmExtdSigned + LJumpStride) * 2.
    assign JumpOffset = (ImmExtdSigned + LJumpStride) << 1;

    // MSB of CMPType is 
    //! hi
    always @(*) begin : branch_logic
        casez (CMPType)
            3'b100: WillBranch = 1'b1;
            3'b110: WillBranch = zerof;
            3'b101: WillBranch = altb;
            default: WillBranch = ZR[0];
        endcase
    end

    assign IC_increment = WillBranch ? JumpOffset : 28'd2;
    assign NextIC = IC + IC_increment;

    // This is the instruction counter loop
    always @(posedge clk or posedge reset) begin : instruction_counter_update
        if (reset) begin
            IC <= ZR;
        end else if (!halt) begin
            IC <= NextIC;
        end
    end

    // To Reg File
    assign ReadRegRb = isJump ? CMPB_ADDR : instr[7:4];
    assign ReadRegRa = isJump ? CMPA_ADDR : instr[3:0];
    assign WriteReg = isImmLoad ? IMR_ADDR : instr[3:0];

    // ALU Operand Muxing
    assign OperandA = MemOp ? MEMOFF : ReadDataRa; 
    assign OperandB = ReadDataRb; 

    assign DataAddress = ALURes;
    assign DataMemoryWrite = ReadDataRa;
  

    // This is to specify where the data for the register write comes from
    always @(*) begin
        case (RegDest)
            2'b00: RegDataWrite = DataMemoryRead;
            2'b01: RegDataWrite = ALURes;
            2'b10: RegDataWrite = ImmExtd;
            2'b11: RegDataWrite = ZR;
        endcase
    end



    // Register File
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
