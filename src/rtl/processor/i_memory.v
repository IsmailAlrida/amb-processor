module imem #(
    parameter INSTRUCTION_WIDTH = 16,
    parameter INSTRUCTION_ADDRESS_SPACE = 28
) (
    input clk,
    input reset,
    input halt,
    input [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    output [INSTRUCTION_WIDTH-1:0] instr
);
endmodule
