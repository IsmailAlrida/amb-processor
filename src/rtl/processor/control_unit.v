module controller #(
    parameter OPCODE_WIDTH = 7,
    parameter CONTROL_OP_WIDTH = 4
) (
    input clk,
    input reset,
    input [OPCODE_WIDTH-1:0] opcode,
    output MemOp,
    output RegWrite,
    output BranchEqual,
    output BranchLt,
    output isJump,
    output LongJump,
    output isImmLoad,
    output WriteEn,
    output ReadEn,
    output [1:0] RegDest,
    output [1:0] ImmSel,
    output [CONTROL_OP_WIDTH-1:0] ALUCtrl,
    output halt
);
endmodule
