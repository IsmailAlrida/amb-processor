//! Sixteen-slot architectural register file with asynchronous reads and synchronous writes.
module reg_file #(
    //! Width of each register word.
    parameter DATA_WORD_WIDTH = 28,
    //! Width of each register selector.
    parameter ADDR_WIDTH = 4,
    //! Number of register slots implemented by the file.
    parameter NUM_OF_REGS = 16
) (
    //! Rising-edge clock for register writes.
    input clk,
    //! Active-high reset that clears all register slots.
    input reset,
    //! Halt input that blocks further writes when asserted.
    input halt,
    //! Source register selector for Rb.
    input [ADDR_WIDTH-1:0] ReadAddrRb,
    //! Destination register selector for Ra.
    input [ADDR_WIDTH-1:0] ReadAddrRa,
    //! Register selector targeted by the writeback port.
    input [ADDR_WIDTH-1:0] WriteAddr,
    //! Data presented to the writeback port.
    input [DATA_WORD_WIDTH-1:0] WriteData,
    //! Write enable for the writeback port.
    input RegWrite,
    //! Asynchronous read data for Rb.
    output reg [DATA_WORD_WIDTH-1:0] ReadDataRb,
    //! Asynchronous read data for Ra.
    output reg [DATA_WORD_WIDTH-1:0] ReadDataRa,
    //! Current MEMOFF register value exported to the CPU datapath.
    output [DATA_WORD_WIDTH-1:0] MEMOFF_OUT,
    //! Current JMPOFF register value exported to the CPU datapath.
    output [DATA_WORD_WIDTH-1:0] JMPOFF_OUT,
    //! IMR byte-lane selector for immediate assembly writes.
    input [1:0] ImmSel
);

    //! Register selector for general register R0.
    localparam R0 = 4'b0000;
    //! Register selector for general register R1.
    localparam R1 = 4'b0001;
    //! Register selector for general register R2.
    localparam R2 = 4'b0010;
    //! Register selector for general register R3.
    localparam R3 = 4'b0011;
    //! Register selector for general register R4.
    localparam R4 = 4'b0100;
    //! Register selector for general register R5.
    localparam R5 = 4'b0101;
    //! Register selector for general register R6.
    localparam R6 = 4'b0110;
    //! Register selector for general register R7.
    localparam R7 = 4'b0111;
    //! Register selector for the instruction counter mirror slot.
    localparam R8 = 4'b1000;
    //! Register selector for the stack pointer slot.
    localparam SP = 4'b1001;
    //! Register selector for the loop counter slot.
    localparam LC = 4'b1010;
    //! Register selector for the immediate assembly register.
    localparam IMR = 4'b1011;
    //! Register selector for the long-jump base offset.
    localparam JMPOFF = 4'b1100;
    //! Register selector for the memory base offset.
    localparam MEMOFF = 4'b1101;
    //! Register selector for the first compare operand.
    localparam CMPA = 4'b1110;
    //! Register selector for the second compare operand.
    localparam CMPB = 4'b1111;
    
    //! Loop index used when reset clears the register array.
    integer i;
    
    //TODO: Fix this if needed
    //! Backing storage for all architectural register slots.
    reg [DATA_WORD_WIDTH-1:0] registry [0:NUM_OF_REGS-1];

    //! Asynchronously reads the selected Ra and Rb register slots.
    always @(*) begin : asynchronous_register_read
        ReadDataRa = registry[ReadAddrRa];
        ReadDataRb = registry[ReadAddrRb];
    end

    //! Exposes MEMOFF directly for memory address generation.
    assign MEMOFF_OUT = registry[MEMOFF];
    //! Exposes JMPOFF directly for long jump address generation.
    assign JMPOFF_OUT = registry[JMPOFF];

    // Can only put WriteData in registry[WriteAddr] if !halt and RegWrite. 
    // Optionally, if WriteAddr == IMR, then use ImmSel to multiplex where data overwrites
    //! Synchronously clears registers on reset and writes either a full register or an IMR lane.
    always @(posedge clk or posedge reset) begin : synchronous_register_write
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
