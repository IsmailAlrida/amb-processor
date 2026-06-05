//! Byte-addressed instruction memory model with asynchronous instruction fetch.
module imem #(
    //! Width of each returned instruction word.
    parameter INSTRUCTION_WIDTH = 16,
    //! Width of the instruction byte address bus.
    parameter INSTRUCTION_ADDRESS_SPACE = 28,
    //! Number of addressable bytes in the memory image.
    parameter DEPTH = 4096
) (
    //! Clock carried for contract symmetry with the CPU core.
    input clk,
    //! Reset carried for contract symmetry; memory contents are not cleared here.
    input reset,
    //! Halt carried for contract symmetry with the CPU core.
    input halt,
    //! Byte address of the instruction to fetch.
    input [INSTRUCTION_ADDRESS_SPACE-1:0] IC,
    //! Instruction word assembled from two adjacent bytes.
    output reg [INSTRUCTION_WIDTH-1:0] instr
);

    //! Byte-addressed instruction storage loaded from program hex.
    reg [7:0] imemory [0:DEPTH-1];
    //! Runtime path to the program hex image.
    reg [1023:0] program_hex;

`ifndef SYNTHESIS
    //! Loads program.hex or the PROGRAM_HEX plusarg image for simulation.
    integer init_idx;

    initial begin
        for (init_idx = 0; init_idx < DEPTH; init_idx = init_idx + 1)
            imemory[init_idx] = 8'h00;

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
    //! Asynchronously returns the 16-bit instruction at the current byte address.
    always @(*) begin : asynchronous_instruction_fetch
        if (IC + 1 < DEPTH) begin
            instr = {imemory[IC], imemory[IC + 1]};
        end else begin
            instr = {INSTRUCTION_WIDTH{1'b0}};
        end
    end
endmodule
