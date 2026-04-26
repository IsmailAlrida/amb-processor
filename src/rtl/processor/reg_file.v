module reg_file #(
    parameter DATA_WORD_WIDTH = 28,
    parameter ADDR_WIDTH = 5,
    parameter NUM_OF_REGS = 16
) (
    input clk,
    input reset,
    input halt,
    input [ADDR_WIDTH-1:0] ReadAddr1,
    input [ADDR_WIDTH-1:0] ReadAddr2,
    input [ADDR_WIDTH-1:0] WriteAddr,
    input [DATA_WORD_WIDTH-1:0] WriteData,
    input RegWrite,
    output [DATA_WORD_WIDTH-1:0] ReadData1,
    output [DATA_WORD_WIDTH-1:0] ReadData2,
    output [DATA_WORD_WIDTH-1:0] MEMOFF,
    output [DATA_WORD_WIDTH-1:0] JMPOFF,
    input [1:0] ImmSel
);
endmodule
