module reg_file #(
    parameter 
    DATA_WORD_WIDTH = 28,
    ADDR_WIDTH = 5,
    NUM_OF_REGS = 16
) (
    input clk, reset,
    input [ADDR_WIDTH-1:0] addr,
    input [DATA_WORD_WIDTH-1:0] data,
    input write_en,
    output reg [DATA_WORD_WIDTH-1:0] out, JMPOFF, CMPA, CMPB, IC, SP, LC, SC
);

    // Registers from 0000 through 0111 are genera purpose
    // 1000 is the IC/Instruction Counter/Program Counter ... Yeah, no. Might just make this GPR 
    // 1001 is the Stack pointer
    // 1010 is the loop counter
    // 1011 is the shift count
    // 1100 is the jump offset (JMPOFF)
    // 1110 is the compare operand A (CMPA)
    // 1111 is the compare operand B (CMPB)
    // FYI: For our compares, CMPA is the lefthand operand and CMPB is the righthand operand
    // What that means is that for something like our JBLW instruction, we jump if CMPA < CMPB. 
    reg [DATA_WORD_WIDTH-1:0] file [0:NUM_OF_REGS-1];

    // For debugging and external use -- read ONLY. 
    // TODO: In higher models be VEEEEEERy sure not write to these files. Actually can we do them here?
    assign IC = file[8];
    assign SP = file[9];
    assign LC = file[10];
    assign SC = file[11];
    assign JMPOFF = file[12];
    assign CMPA = file[14];
    assign CMPB = file[15];

    reg [DATA_WORD_WIDTH-1:0] last_reg;  

    assign wire is_ic_selected = (addr == 8);
    assign wire is_write_to_ic = write_en && is_ic_selected;

    // TODO: this part is a bit messy in terms of logic. the end goal is to increment the IC by 2 whenever we DONT write. 
    // As for what last_reg is for, it's just to store the previous register so in cycles where the IC is selected but not written to, we can still read
    // The old register value BECAUSE we already expose the IC as an output, so having it stay on that pin is a waste; better just show the older value.
    always @(posedge clk) begin
        if (is_write_to_ic) begin
            // Only time we EVER write to IC is if WRITE MODE and IC SELECTED.   
            IC <= data; 
        end else if (is_ic_selected && !write_en) begin  
            // TODO: and that begs the question, should we make IC available via out port? I mean we already have it, but we should treat all cases
            // Something. Anyways, this is for later
            // You know what, let's just do the "obvious" thing and just increment it. 
            out <= last_reg;
            file[8] <= file[8] + 2;

        end else if (!is_ic_selected && write_en) begin
            file[addr] <= data;
            file[8] <= file[8] + 2;

        end else begin // Not selected, not write enabled, this is reg read mode
            file[8] <= file[8] + 2; 
        end
    end
    always @(negedge clk) begin
        out <= file[addr];
    end
    
    
endmodule