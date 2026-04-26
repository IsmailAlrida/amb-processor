module reg_file #(
    parameter DATA_WORD_WIDTH = 28,
    parameter ADDR_WIDTH = 4,
    parameter NUM_OF_REGS = 16
) (
    input clk,
    input reset,
    input halt,
    input [ADDR_WIDTH-1:0] ReadAddrRb,
    input [ADDR_WIDTH-1:0] ReadAddrRa,
    input [ADDR_WIDTH-1:0] WriteAddr,
    input [DATA_WORD_WIDTH-1:0] WriteData,
    input RegWrite,
    output reg [DATA_WORD_WIDTH-1:0] ReadDataRb,
    output reg [DATA_WORD_WIDTH-1:0] ReadDataRa,
    output [DATA_WORD_WIDTH-1:0] MEMOFF_OUT,
    output [DATA_WORD_WIDTH-1:0] JMPOFF_OUT,
    input [1:0] ImmSel
);

    localparam R0 = 4'b0000;
    localparam R1 = 4'b0001;
    localparam R2 = 4'b0010;
    localparam R3 = 4'b0011;
    localparam R4 = 4'b0100;
    localparam R5 = 4'b0101;
    localparam R6 = 4'b0110;
    localparam R7 = 4'b0111;
    localparam R8 = 4'b1000;
    localparam SP = 4'b1001;
    localparam LC = 4'b1010;
    localparam IMR = 4'b1011;
    localparam JMPOFF = 4'b1100;
    localparam MEMOFF = 4'b1101;
    localparam CMPA = 4'b1110;
    localparam CMPB = 4'b1111;
    
    integer i;
    
    //TODO: Fix this if needed
    reg [DATA_WORD_WIDTH-1:0] registry [0:NUM_OF_REGS-1];

    always @(*) begin
        ReadDataRa = registry[ReadAddrRa];
        ReadDataRb = registry[ReadAddrRb];
    end

    assign MEMOFF_OUT = registry[MEMOFF];
    assign JMPOFF_OUT = registry[JMPOFF];

    // Can only put WriteData in registry[WriteAddr] if !halt and RegWrite. 
    // Optionally, if WriteAddr == IMR, then use ImmSel to multiplex where data overwrites
    always @(posedge clk or posedge reset) begin
        if (reset) begin
            for (i = 0; i < NUM_OF_REGS; i++) begin
                registry[i] <= {DATA_WORD_WIDTH{1'b0}};
            end
        end else if (!halt && RegWrite) begin
            if (WriteAddr == IMR) begin
                // ImmSel Multiplexing
                case (ImmSel)
                    2'b00: registry[IMR][7:0]   <= WriteData [7:0];
                    2'b01: registry[IMR][15:8]  <= WriteData [7:0];
                    2'b10: registry[IMR][23:16] <= WriteData [7:0];
                    2'b11: registry[IMR][27:24] <= WriteData [3:0];
                endcase

            end else begin
                registry[WriteAddr] <= WriteData;
            end
        end else begin
            // pass. Dont write anything
        end
    end

endmodule
