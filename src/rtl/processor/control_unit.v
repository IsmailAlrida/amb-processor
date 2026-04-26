module controller #(
    parameter OPCODE_WIDTH = 7,
    parameter CONTROL_OP_WIDTH = 4
) (
    input clk,
    input reset,
    input [OPCODE_WIDTH-1:0] opcode,
    output reg MemOp,
    output reg RegWrite,
    output reg BranchEqual,
    output reg BranchLt,
    //! Set when opcode[6] == 1, but is it better just to make a large case statement?
    output reg isJump,
    //! Set when opcode[0] == 1 or when opcode == 1000001, 1000010, 1000011. First theory since jumps are only in the 1xxxxx address space
    output reg LongJump,
    //! Set when opcode is between 0011010 and 0011101 inclusive
    output reg isImmLoad,
    //! Set when opcode is 0011111, reset else
    output reg WriteEn,
    // Set when opcode is 0011110
    output reg ReadEn,
    output reg [1:0] RegDest,
    output reg [1:0] ImmSel,
    output reg [CONTROL_OP_WIDTH-1:0] ALUCtrl,
    output reg halt
);

    localparam set = 1'b1;
    localparam unset = 1'b0;

    localparam HALT   = 7'b0000000;
    localparam NOP    = 7'b0000001;
    localparam  NOT   = 7'b0010000;
    localparam  OR    = 7'b0010001;
    localparam  AND   = 7'b0010010;
    localparam  XOR   = 7'b0010011;
    localparam  SHL   = 7'b0010100;
    localparam  SHR   = 7'b0010101;
    localparam  SAR   = 7'b0010110;
    localparam  ADD   = 7'b0010111;
    localparam  SUB   = 7'b0011000;
    localparam  MOV   = 7'b0011001;
    localparam  LIL   = 7'b0011010;
    localparam  LIH   = 7'b0011011;
    localparam  LILL  = 7'b0011100;
    localparam  LIHH  = 7'b0011101;
    localparam  LOAD  = 7'b0011110;
    localparam  STOR  = 7'b0011111;
    localparam  JMP   = 7'b1000000;
    localparam  JMPL  = 7'b1000001;
    localparam  JPEQ  = 7'b1000010;
    localparam  JPBLW = 7'b1000011;

    // TODO: Consider a global shared param list between this and ALU. Hardcode is fine for now.
    localparam  ALU_NOT = 4'b0000;
    localparam  ALU_OR  = 4'b0001;
    localparam  ALU_AND = 4'b0010;
    localparam  ALU_XOR = 4'b0011;
    localparam  ALU_SHL = 4'b0100;
    localparam  ALU_SHR = 4'b0101;
    localparam  ALU_SAR = 4'b0110;
    localparam  ALU_ADD = 4'b0111;
    localparam  ALU_SUB = 4'b1000;
    localparam  ALU_MOV = 4'b1001;


    wire RTYPE;
    assign RTYPE = (opcode >= NOT) && (opcode <= MOV);

    //! MemOp
    always @(*) begin
        if (opcode == STOR || opcode == LOAD) begin
            MemOp = set;
        end else begin
            MemOp = unset;
        end
    end

    //! RegWrite
    always @(*) begin
        // Set only when not J-types (!opcode[6]) or when not STOR instruction
        if (!opcode[6] && opcode != STOR && opcode != HALT && opcode != NOP) begin
            RegWrite = set;
        end else begin
            RegWrite = unset;
        end
    end

    //! BranchEqual
    always @(*) begin
        if (opcode == JPEQ) begin
            BranchEqual = set;
        end else begin
            BranchEqual = unset;
        end
    end

    //! BranchLt
    always @(*) begin
        if (opcode == JPBLW) begin
            BranchLt = set;
        end else begin
            BranchLt = unset;
        end
    end

    //! isJump 
    //! set on opcode[6] being 1 because all jump intructions have opcode[6] = 1.
    always @(*) begin
        if (opcode[6]) begin
            isJump = set;
        end else begin
            isJump = unset;
        end
    end
    //! LongJump only when branchers or JMPL
    always @(*) begin
        if (opcode == JMPL || opcode == JPEQ || opcode == JPBLW) begin
            LongJump = set;
        end else begin
            LongJump = unset;
        end
    end

    //! isImmLoad
    always @(*) begin
        if (opcode == LIL || opcode == LIH || opcode == LILL || opcode == LIHH) begin
            isImmLoad = set;
        end else begin
            isImmLoad = unset;
        end
    end

    //! WriteEn 
    always @(*) begin
        if (opcode == STOR) begin
            WriteEn = set;
        end else begin
            WriteEn = unset;
        end
    end

    //! ReadEn
    always @(*) begin
        if (opcode == LOAD) begin
            ReadEn = set;
        end else begin
            ReadEn = unset;
        end
    end

    //! RegDest
    always @(*) begin
        // MemRead
        if (opcode == LOAD) begin
            RegDest = 2'b00; 
        
        // Use ALU Result
        end else if (RTYPE || opcode == NOP) begin
            RegDest = 2'b01;
        
        // Write zero-extended immediate
        // TODO: For sake of timing closures, consider NOT using isImmLoad here, and just make another same check
        end else if (opcode == LIL || opcode == LIH || opcode == LILL || opcode == LIHH) begin
            RegDest = 2'b10;

        // Write Zero
        end else begin
            RegDest = 2'b11;
        end
    end

    //! ImmSel 
    //TODO: I have a feeling the lack of an else statement can cause a hazard here or something.
    always @(*) begin
        ImmSel = 2'b00;
        if (opcode == LIL) begin
            ImmSel = 2'b00;
        end else if (opcode == LIH) begin
            ImmSel = 2'b01;
        end else if (opcode == LILL) begin
            ImmSel = 2'b10;
        end else if (opcode == LIHH) begin
            ImmSel = 2'b11;
        end else begin
            // I dont know what to put here.... for now.
        end
    end

    //! ALUCtrl 
    always @(*) begin
        // TODO: I still need to implement better 
        case (opcode)
            NOT: ALUCtrl = ALU_NOT;
            OR:  ALUCtrl = ALU_OR;
            AND: ALUCtrl = ALU_AND;
            XOR: ALUCtrl = ALU_XOR;
            SHL: ALUCtrl = ALU_SHL;
            SHR: ALUCtrl = ALU_SHR;
            SAR: ALUCtrl = ALU_SAR;
            ADD: ALUCtrl = ALU_ADD;
            SUB: ALUCtrl = ALU_SUB;
            MOV: ALUCtrl = ALU_MOV;
            LOAD: ALUCtrl = ALU_ADD;
            STOR: ALUCtrl = ALU_ADD;
            JPEQ: ALUCtrl = ALU_SUB;
            JPBLW: ALUCtrl = ALU_SUB;
            default: ALUCtrl = ALU_SUB;
        endcase
    end


    
    //! Halt flag handling
    always @(*) begin : halting
        if (opcode == HALT) begin
            halt = set;
        end else begin
            halt = unset;
        end
    end

endmodule
