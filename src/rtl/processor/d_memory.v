module dmem #(
    parameter DATA_ADDR_SPACE = 28,
    parameter DATA_WORD_WIDTH = 28
) (
    input clk,
    input reset,
    input halt,
    input [DATA_ADDR_SPACE-1:0] Address,
    input [DATA_WORD_WIDTH-1:0] DataIn,
    output [DATA_WORD_WIDTH-1:0] DataOut,
    input ReadEn,
    input WriteEn
);
endmodule
