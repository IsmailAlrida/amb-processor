module dmem #(
    parameter DATA_ADDR_SPACE = 28,
    parameter DATA_WORD_WIDTH = 28
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

    reg [DATA_WORD_WIDTH-1:0] dmemory [0:2**DATA_ADDR_SPACE - 1];

    initial begin
        $readmemh("data.hex", dmemory);
    end

    always @(*) begin
        if (WriteEn) begin
            dmemory[Address] = DataIn;
        end 
        if (ReadEn) begin
            DataOut = dmemory[Address];
        end
    end
endmodule
