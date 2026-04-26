//! Byte-addressed data memory model with asynchronous reads and synchronous writes.
module dmem #(
    //! Width of the data byte address bus.
    parameter DATA_ADDR_SPACE = 28,
    //! Width of each architectural data word.
    parameter DATA_WORD_WIDTH = 28,
    //! Number of addressable bytes in the data memory image.
    parameter DEPTH = 4096
) (
    //! Rising-edge clock for memory writes.
    input clk,
    //! Reset carried for contract symmetry; memory contents are not cleared here.
    input reset,
    //! Halt input that blocks writes when asserted.
    input halt,
    //! Byte address used for the current read or write.
    input [DATA_ADDR_SPACE-1:0] Address,
    //! Data word written to memory on stores.
    input [DATA_WORD_WIDTH-1:0] DataIn,
    //! Data word read from memory on loads.
    output reg [DATA_WORD_WIDTH-1:0] DataOut,
    //! Enables the asynchronous read output.
    input ReadEn,
    //! Enables a synchronous memory write.
    input WriteEn
);

    //! Byte-addressed data storage loaded from data hex.
    reg [7:0] dmemory [0:DEPTH-1];
    //! Runtime path to the data hex image.
    reg [1023:0] data_hex;

`ifndef SYNTHESIS
    //! Loads data.hex or the DATA_HEX plusarg image for simulation.
    initial begin
        data_hex = "data.hex";
        if ($value$plusargs("DATA_HEX=%s", data_hex)) begin
            $display("dmem: loading %0s", data_hex);
        end else begin
            $display("dmem: loading %0s", data_hex);
        end
        $readmemh(data_hex, dmemory);
    end
`endif

    //! Asynchronously reads a 28-bit little-endian word when ReadEn is asserted.
    always @(*) begin : asynchronous_data_read
        if (ReadEn && Address + 3 < DEPTH) begin
            DataOut = {
                dmemory[Address + 3][3:0],
                dmemory[Address + 2],
                dmemory[Address + 1],
                dmemory[Address]
            };
        end else begin
            DataOut = {DATA_WORD_WIDTH{1'b0}};
        end
    end

    //! Synchronously writes a 28-bit little-endian word when WriteEn is asserted.
    always @(posedge clk) begin : synchronous_data_write
        if (!halt && WriteEn && Address + 3 < DEPTH) begin
            dmemory[Address]     <= DataIn[7:0];
            dmemory[Address + 1] <= DataIn[15:8];
            dmemory[Address + 2] <= DataIn[23:16];
            dmemory[Address + 3] <= {4'b0000, DataIn[27:24]};
        end
    end
endmodule
