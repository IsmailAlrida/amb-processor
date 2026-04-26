//! Combinational decoder that maps ISA v1 opcodes into CPU datapath control signals.
module controller #(
    //! Width of the ISA opcode field.
    parameter OPCODE_WIDTH = 7,
    //! Width of the ALU operation selector.
    parameter CONTROL_OP_WIDTH = 4
) (
    //! Clock carried for module contract symmetry with the CPU datapath.
    input clk,
    //! Reset carried for module contract symmetry with the CPU datapath.
    input reset,
    //! Current instruction opcode from instr[14:8].
    input [OPCODE_WIDTH-1:0] opcode,
    //! Selects memory address generation mode in the CPU ALU operand path.
    output reg MemOp,
    //! Enables writes into the register file.
    output reg RegWrite,
    //! Marks JPEQ as the active branch comparison.
    output reg BranchEqual,
    //! Marks JPBLW as the active branch comparison.
    output reg BranchLt,
    //! Asserted for opcodes in the jump opcode space.
    output reg isJump,
    //! Asserted for jump forms that add JMPOFF to the signed imm8 offset.
    output reg LongJump,
    //! Asserted for LIL, LIH, LILL, and LIHH.
    output reg isImmLoad,
    //! Data memory write enable asserted for STOR.
    output reg WriteEn,
    // Set when opcode is 0011110
    //! Data memory read enable asserted for LOAD.
    output reg ReadEn,
    //! Register writeback source selector.
    output reg [1:0] RegDest,
    //! IMR lane selector used by immediate load instructions.
    output reg [1:0] ImmSel,
    //! ALU operation selector.
    output reg [CONTROL_OP_WIDTH-1:0] ALUCtrl,
    //! Halt flag asserted for HLT.
    output reg halt
);

    //! Canonical asserted control value.
    localparam set = 1'b1;
    //! Canonical deasserted control value.
    localparam unset = 1'b0;

    //! HLT opcode.
    localparam HALT   = 7'b0000000;
    //! NOP opcode.
    localparam NOP    = 7'b0000001;
    //! NOT opcode.
    localparam  NOT   = 7'b0010000;
    //! OR opcode.
    localparam  OR    = 7'b0010001;
    //! AND opcode.
    localparam  AND   = 7'b0010010;
    //! XOR opcode.
    localparam  XOR   = 7'b0010011;
    //! SHL opcode.
    localparam  SHL   = 7'b0010100;
    //! SHR opcode.
    localparam  SHR   = 7'b0010101;
    //! SAR opcode.
    localparam  SAR   = 7'b0010110;
    //! ADD opcode.
    localparam  ADD   = 7'b0010111;
    //! SUB opcode.
    localparam  SUB   = 7'b0011000;
    //! MOV opcode.
    localparam  MOV   = 7'b0011001;
    //! LIL opcode for IMR[7:0].
    localparam  LIL   = 7'b0011010;
    //! LIH opcode for IMR[15:8].
    localparam  LIH   = 7'b0011011;
    //! LILL opcode for IMR[23:16].
    localparam  LILL  = 7'b0011100;
    //! LIHH opcode for IMR[27:24].
    localparam  LIHH  = 7'b0011101;
    //! LOAD opcode.
    localparam  LOAD  = 7'b0011110;
    //! STOR opcode.
    localparam  STOR  = 7'b0011111;
    //! Direct PC-relative jump opcode.
    localparam  JMP   = 7'b1000000;
    //! Long PC-relative jump opcode using JMPOFF.
    localparam  JMPL  = 7'b1000001;
    //! Conditional equal jump opcode using CMPA/CMPB.
    localparam  JPEQ  = 7'b1000010;
    //! Conditional below jump opcode using CMPA/CMPB.
    localparam  JPBLW = 7'b1000011;

    // TODO: Consider a global shared param list between this and ALU. Hardcode is fine for now.
    //! ALU selector for NOT.
    localparam  ALU_NOT = 4'b0000;
    //! ALU selector for OR.
    localparam  ALU_OR  = 4'b0001;
    //! ALU selector for AND.
    localparam  ALU_AND = 4'b0010;
    //! ALU selector for XOR.
    localparam  ALU_XOR = 4'b0011;
    //! ALU selector for SHL.
    localparam  ALU_SHL = 4'b0100;
    //! ALU selector for SHR.
    localparam  ALU_SHR = 4'b0101;
    //! ALU selector for SAR.
    localparam  ALU_SAR = 4'b0110;
    //! ALU selector for ADD.
    localparam  ALU_ADD = 4'b0111;
    //! ALU selector for SUB.
    localparam  ALU_SUB = 4'b1000;
    //! ALU selector for MOV.
    localparam  ALU_MOV = 4'b1001;


    //! True when the current opcode is one of the register-register operations.
    wire RTYPE;
    //! Range decode for register-register ALU and MOV opcodes.
    assign RTYPE = (opcode >= NOT) && (opcode <= MOV);

    //! Decodes LOAD/STOR as memory operations.
    always @(*) begin : memory_operation_decode
        if (opcode == STOR || opcode == LOAD) begin
            MemOp = set;
        end else begin
            MemOp = unset;
        end
    end

    //! Enables register writes for instructions that produce architectural register data.
    always @(*) begin : register_write_decode
        // Set only when not J-types (!opcode[6]) or when not STOR instruction
        if (!opcode[6] && opcode != STOR && opcode != HALT && opcode != NOP) begin
            RegWrite = set;
        end else begin
            RegWrite = unset;
        end
    end

    //! Decodes JPEQ equality-branch intent.
    always @(*) begin : branch_equal_decode
        if (opcode == JPEQ) begin
            BranchEqual = set;
        end else begin
            BranchEqual = unset;
        end
    end

    //! Decodes JPBLW less-than-branch intent.
    always @(*) begin : branch_less_than_decode
        if (opcode == JPBLW) begin
            BranchLt = set;
        end else begin
            BranchLt = unset;
        end
    end

    //! Decodes the jump opcode space.
    always @(*) begin : jump_class_decode
        if (opcode[6]) begin
            isJump = set;
        end else begin
            isJump = unset;
        end
    end
    //! Enables JMPOFF for JMPL and conditional branch opcodes.
    always @(*) begin : long_jump_decode
        if (opcode == JMPL || opcode == JPEQ || opcode == JPBLW) begin
            LongJump = set;
        end else begin
            LongJump = unset;
        end
    end

    //! Decodes immediate assembly instructions that write IMR lanes.
    always @(*) begin : immediate_load_decode
        if (opcode == LIL || opcode == LIH || opcode == LILL || opcode == LIHH) begin
            isImmLoad = set;
        end else begin
            isImmLoad = unset;
        end
    end

    //! Generates the data memory write strobe.
    always @(*) begin : data_memory_write_decode
        if (opcode == STOR) begin
            WriteEn = set;
        end else begin
            WriteEn = unset;
        end
    end

    //! Generates the data memory read strobe.
    always @(*) begin : data_memory_read_decode
        if (opcode == LOAD) begin
            ReadEn = set;
        end else begin
            ReadEn = unset;
        end
    end

    //! Selects register writeback source: memory, ALU, immediate byte, or zero.
    always @(*) begin : register_writeback_source_select
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

    //! Selects which byte lane of IMR receives the current imm8 value.
    //TODO: I have a feeling the lack of an else statement can cause a hazard here or something.
    always @(*) begin : immediate_lane_select
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

    //! Maps the current opcode to the ALU operation selector.
    always @(*) begin : alu_control_decode
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


    
    //! Decodes HLT into the core halt signal.
    always @(*) begin : halt_decode
        if (opcode == HALT) begin
            halt = set;
        end else begin
            halt = unset;
        end
    end

endmodule
