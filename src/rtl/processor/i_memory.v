module imem #(
    parameter INSTRUCTION_WIDTH = 16,
    parameter INSTRUCTION_ADDRESS_SPACE = 28
) (
    input clk,
    input reset,
    input halt,
    input [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    output reg [INSTRUCTION_WIDTH-1:0] instr
);

    reg [7:0] imemory [0:2**INSTRUCTION_ADDRESS_SPACE -1];

    initial begin
        $readmemh("program.hex", imemory);
    end

    // I dont think this module should care about resetting IC. IC will be reset externally
    always @(*) begin
        instr = imemory[IC];
    end
endmodule
