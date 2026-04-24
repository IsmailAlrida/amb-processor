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
    input clk
);

    // Global Zero Register
    assign reg[DATA_WORD_WIDTH-1:0] ZR = 28'h0000000;
    // Used to link between components
    reg [DATA_WORD_WIDTH-1:0] IC; 
    wire [DATA_WORD_WIDTH-1:0] IC_OUT, IC_increment, JumpAddr, JumpOffset;
    wire [DATA_WORD_WIDTH-1:0] MEMOFF, JMPOFF, CMPA, CMPB, DmemFetch, OperandA, OperandB, ALURes, zerof, altb; 

    // Control flag single-bit wires
    wire RegWrite, MemOp, LongJump, isJump, BranchType, isImmLoad, WriteEn, ReadEn, WillBranch;
    
    // Control Multi-bit flags
    wire [3:0] ALUCtrl;
    wire [1:0] ImmSel; // This ons is for reg file
    wire [1:0] CMPType;
    wire [1:0] RegDest; // This is 2 bit cuz we can write either from mem, from ALU, or from Imm

    // Just for niceness
    assign CMPType = {BranchType, isJump};

    // Instruction Memory Bus
    wire [INSTRUCTION_WIDTH-1:0] instr;

    // To Control Unit
    assign wire [6:0] opcode = instr[14:8];

    // For the IMR Branch, we pad with zeroes.
    assign wire [DATA_WORD_WIDTH-1:0] ImmExtd       = {{(DATA_WORD_WIDTH-8){1'b0}},     instr[7:0]};
    assign wire [DATA_WORD_WIDTH-1:0] ImmExtdSigned = {{(DATA_WORD_WIDTH-8){instr[7]}}, instr[7:0]};

    
    // -- CPU GLUE -- 

    // Instruction Counter Path

    assign JumpOffset = LongJump ? JMPOFF : ZR;
    // TODO: Check if we want signed jumping or unsigned immediate jumping
    assign JumpAddr = (ImmExtdSigned + JumpOffset) << 1;


    always @(*) begin
        casez (CMPType)
            2'b00: WillBranch = 1'b0;
            2'b01: WillBranch = 1'b1;
            2'b10: WillBranch = zerof; // this is the ALU zero flag
            2'b11: WillBranch = altb; // This is the A less than B flag
        endcase
    end

    assign IC = WillBranch ? JumpAddr : IC_increment;


    // To Reg File
    assign wire [3:0] ReadReg1 = isJump ? CMPA : instr[7:4];
    assign wire [3:0] ReadReg2 = isJump ? CMPB : instr[3:0];
    assign wire [3:0] WriteReg = isImmLoad ? IMR : instr[3:0];
    wire [DATA_WORD_WIDTH-1:0] RegDataWrite;
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
        .instr(instr)
    );

    // Register File 
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
        .ImmSel(ImmSel)
    );

    // Data Memory
    dmem #(
        .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
    ) dmem_inst (
        .Address(ALURes),
        .DataIn(ReadReg2),
        .DataOut(DmemFetch),
        .ReadEn(ReadEn),
        .WriteEn(WriteEn)
    );



    
endmodule