/*
    Meet the top-level of the processor. This is where we will glue all the bits and pieces together.
    Ultimately, we will just implement a simple single-cycle fetch-decode-execute here for this version.
*/
module cpu #(
    parameter
    DATA_ADDR_SPACE = 28,
    DATA_WORD_WIDTH = 28,
    INSTRUCTION_WIDTH = 16,
    INSTRUCTION_ADDRESS_SPACE = 28,
    REG_ADDR_WIDTH = 5,
    NUM_OF_REGS = 16,
) (
    input clk,
    input reset
);

    // Register Addresses 
    localparam [3:0] IMR_ADDR = 4'b1011;
    localparam [3:0] CMPA_ADDR = 4'b1110;
    localparam [3:0] CMPB_ADDR = 4'b1111;

    // Global Zero Register
    reg [DATA_WORD_WIDTH-1:0] ZR;
    assign ZR = 28'h0000000;


    // Wires moving between two components
    reg [DATA_WORD_WIDTH-1:0] IC; 
    wire [DATA_WORD_WIDTH-1:0] IC_OUT, IC_increment, NextIC, JumpOffset, LJumpStride;
    wire [DATA_WORD_WIDTH-1:0] MEMOFF, JMPOFF, DmemFetch, OperandA, OperandB, ALURes; 

    // Control flag single-bit wires
    wire RegWrite, MemOp, LongJump, isJump, BranchType, isImmLoad, WriteEn, ReadEn, WillBranch, halt, zerof, altb;
    
    // Control Multi-bit flags
    wire [3:0] ALUCtrl;
    wire [1:0] ImmSel; // This ons is for reg file
    wire [1:0] CMPType;
    wire [1:0] RegDest; // This is 2 bit cuz we can write either from mem, from ALU, or from Imm

    // Just for niceness. BranchType 1 = CMP action A==B, 0 = CMP Action A<B
    assign CMPType = {BranchType, isJump};

    // Instruction Memory Bus
    wire [INSTRUCTION_WIDTH-1:0] instr;

    // To Control Unit
    wire [6:0] opcode;

    // For the IMR Branch, we pad with zeroes.
    wire [DATA_WORD_WIDTH-1:0] ImmExtd;
    wire [DATA_WORD_WIDTH-1:0] ImmExtdSigned;
    wire [3:0] ReadReg1;
    wire [3:0] ReadReg2;
    wire [3:0] WriteReg;

    assign opcode        = instr[14:8];
    assign ImmExtd       = {{(DATA_WORD_WIDTH-8){1'b0}},     instr[7:0]};
    assign ImmExtdSigned = {{(DATA_WORD_WIDTH-8){instr[7]}}, instr[7:0]};

    
    // -- CPU GLUE -- 

    // Instruction Counter Path

    assign LJumpStride = LongJump ? JMPOFF : ZR;
    // TODO: Signed or unsigned jumps?
    assign JumpOffset = (ImmExtdSigned + LJumpStride) << 1;


    always @(*) begin
        casez (CMPType)
            2'b00: WillBranch = altb;
            2'b01: WillBranch = 1'b1;
            2'b10: WillBranch = ZR[0];
            2'b11: WillBranch = zerof; 
        endcase
    end

    assign IC_increment = WillBranch ? JumpOffset : 28'd2;
    assign NextIC = IC + IC_increment;

    // This is the instruction counter loop
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            IC <= ZR;
        end else if (!halt) begin
            IC <= NextIC;
        end
    end


    // To Reg File
    assign ReadReg1 = isJump ? CMPA_ADDR : instr[7:4];
    assign ReadReg2 = isJump ? CMPB_ADDR : instr[3:0];
    assign WriteReg = isImmLoad ? IMR_ADDR : instr[3:0];
    reg [DATA_WORD_WIDTH-1:0] RegDataWrite;
    // This is to specify where the data for the register write comes from
    always @(*) begin
        casez (RegDest)
            2'b00: RegDataWrite = DmemFetch;
            2'b01: RegDataWrite = ALURes;
            2'b10: RegDataWrite = ImmExtd;
            2'b11: RegDataWrite = {28{1'b0}};
        endcase
    end

    // From Reg File
    wire [DATA_WORD_WIDTH-1:0] ReadData1, ReadData2;

    // ALU Operand Muxing
    assign OperandA = ReadData1;
    assign OperandB = MemOp ? MEMOFF : ReadData2;

     


    imem #(
        .INSTRUCTION_WIDTH(INSTRUCTION_WIDTH),
        .INSTRUCTION_ADDRESS_SPACE(INSTRUCTION_ADDRESS_SPACE)
    ) imem_inst (
        .IC(IC),
        .instr(instr),
        .clk(clk),
        .reset(reset),
        .halt(halt)
    );

    // Register File 
    // TODO: Register file-related glue is done. Move on
    reg_file #(
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
        .ADDR_WIDTH(REG_ADDR_WIDTH),
        .NUM_OF_REGS(NUM_OF_REGS)
    ) reg_file_inst (
        .ReadAddr1(ReadReg1),
        .ReadAddr2(ReadReg2),
        .WriteAddr(WriteReg),
        .WriteData(RegDataWrite),
        .RegWrite(RegWrite),
        .ReadData1(ReadData1),
        .ReadData2(ReadData2),
        .MEMOFF(MEMOFF),
        .JMPOFF(JMPOFF),
        .ImmSel(ImmSel),
        .clk(clk),
        .reset(reset),
        .halt(halt)
    ); 

    // ALU 
    alu #(
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH)
    ) alu_inst (
        .OperandA(OperandA),
        .OperandB(OperandB),
        .result(ALURes),
        .zero(zerof),
        .altb(altb), // Flag for A less than B
        .ALUCtrl(ALUCtrl),
        .clk(clk),
        .reset(reset),
        .halt(halt)
    );

    // Control Unit
    controller #(

    )  controller_inst (
        .opcode(opcode),
        .MemOp(MemOp),
        .RegWrite(RegWrite),
        .BranchType(BranchType),
        .isJump(isJump),
        .LongJump(LongJump),
        .isImmLoad(isImmLoad),
        .WriteEn(WriteEn),
        .ReadEn(ReadEn),
        .RegDest(RegDest),
        .ImmSel(ImmSel),
        .ALUCtrl(ALUCtrl),
        .halt(halt),
        .clk(clk),
        .reset(reset)
    );

    // Data Memory
    dmem #(
        .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
    ) dmem_inst (
        .Address(ALURes),
        .DataIn(ReadData2),
        .DataOut(DmemFetch),
        .ReadEn(ReadEn),
        .WriteEn(WriteEn),
        .clk(clk),
        .reset(reset),
        .halt(halt)
    );



    
endmodule
