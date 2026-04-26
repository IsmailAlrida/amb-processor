module imem #(
    parameter INSTRUCTION_WIDTH = 16,
    parameter INSTRUCTION_ADDRESS_SPACE = 28,
    parameter DEPTH = 4096
) (
    input clk,
    input reset,
    input halt,
    input [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    output reg [INSTRUCTION_WIDTH-1:0] instr
);

    reg [7:0] imemory [0:DEPTH-1];
    reg [1023:0] program_hex;

`ifndef SYNTHESIS
    initial begin
        program_hex = "program.hex";
        if ($value$plusargs("PROGRAM_HEX=%s", program_hex)) begin
            $display("imem: loading %0s", program_hex);
        end else begin
            $display("imem: loading %0s", program_hex);
        end
        $readmemh(program_hex, imemory);
    end
`endif

    // I dont think this module should care about resetting IC. IC will be reset externally
    always @(*) begin
        if (IC + 1 < DEPTH) begin
            instr = {imemory[IC], imemory[IC + 1]};
        end else begin
            instr = {INSTRUCTION_WIDTH{1'b0}};
        end
    end
endmodule
