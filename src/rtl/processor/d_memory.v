module dmem #(
    parameter DATA_ADDR_SPACE = 28,
    parameter DATA_WORD_WIDTH = 28,
    parameter DEPTH = 4096
) (
    input clk,
    input reset,
    input halt,
    input [DATA_ADDR_SPACE-1:0] Address,
    input [DATA_WORD_WIDTH-1:0] DataIn,
    output reg [DATA_WORD_WIDTH-1:0] DataOut,
    input ReadEn,
    input WriteEn
);

    reg [7:0] dmemory [0:DEPTH-1];
    reg [1023:0] data_hex;

`ifndef SYNTHESIS
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

    always @(*) begin
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

    always @(posedge clk) begin
        if (!halt && WriteEn && Address + 3 < DEPTH) begin
            dmemory[Address]     <= DataIn[7:0];
            dmemory[Address + 1] <= DataIn[15:8];
            dmemory[Address + 2] <= DataIn[23:16];
            dmemory[Address + 3] <= {4'b0000, DataIn[27:24]};
        end
    end
endmodule
