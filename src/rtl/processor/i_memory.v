module imem #(
    parameter
    DATA_ADDR_SPACE = 28,
    DATA_WORD_WIDTH = 28
) (
    input [DATA_ADDR_SPACE-1:0] addr,
    input [DATA_WORD_WIDTH-1:0] data,
    input [1:0] read_write_flags,
    output reg [DATA_WORD_WIDTH-1:0] out,
    output reg error_flag
);

    reg [DATA_WORD_WIDTH-1:0] storage [0:2**DATA_ADDR_SPACE-1];
    // Just for debugging
    assign wire mem_read = read_write_flags[0];
    assign wire mem_write = read_write_flags[1];
    // TODO: This needs to be FINISHED. Clean it up
    $readmemh("program.hex", storage);
    
    always @(*) begin
        casez (read_write_flags)
            2'b00: error_flag = 1'b0; // No read nor write, no data change
            2'b01: out = storage[addr]; // Read memory at that address
            2'b10: storage[addr] = data; // Write memory at that address
            2'b11: error_flag = 1'b1; // This is an illegal state we should handle
            default: error_flag = 1'b1;
        endcase
    end
endmodule