module moduleName #(
    parameter 
    DATA_WORD_WIDTH = 28,
    ADDR_WIDTH = 5,
    NUM_OF_REGS = 16
) (
    input clk,
    input [ADDR_WIDTH-1:0] addr,
    input [DATA_WORD_WIDTH-1:0] data,
    input write_en,
    output reg [DATA_WORD_WIDTH-1:0] out, JMPOFF, CMPA, CMPB, IC, SP, LC, SC
);

    always @(*) begin
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
        reg [DATA_WORD_WIDTH-1:0] reg_file [0:NUM_OF_REGS-1];

        // For debugging and external use -- read ONLY. 
        // TODO: In higher models be VEEEEEERy sure not write to these files. Actually can we do them here?
        assign IC = reg_file[8];
        assign SP = reg_file[9];
        assign LC = reg_file[10];
        assign SC = reg_file[11];
        assign JMPOFF = reg_file[12];
        assign CMPA = reg_file[14];
        assign CMPB = reg_file[15];

        //TODO: Consider removing IC fromm the register file and keep it seperated
        always @(*) begin
            if (write_en) begin
                casez (addr)
                    4'b0000: reg_file[0] = data;
                    4'b0001: reg_file[1] = data;
                    4'b0010: reg_file[2] = data;
                    4'b0011: reg_file[3] = data;
                    4'b0100: reg_file[4] = data;
                    4'b0101: reg_file[5] = data;
                    4'b0110: reg_file[6] = data;
                    4'b0111: reg_file[7] = data;
                    4'b1000: reg_file[8] = data; // How the heck we gonna increment this lad if it is not on clock edge???
                    4'b1001: reg_file[9] = data;
                    4'b1010: reg_file[10] = data;
                    4'b1011: reg_file[11] = data;
                    4'b1100: reg_file[12] = data;
                    4'b1101: reg_file[13] = data;
                    4'b1110: reg_file[14] = data;
                    4'b1111: reg_file[15] = data;
                    default: out = out; //TODO: Check if this latching behavior is dangerous for real hardware
                endcase
            end else begin
                casez (addr)
                    4'b0000: out = reg_file[0];
                    4'b0001: out = reg_file[1];
                    4'b0010: out = reg_file[2];
                    4'b0011: out = reg_file[3];
                    4'b0100: out = reg_file[4];
                    4'b0101: out = reg_file[5];
                    4'b0110: out = reg_file[6];
                    4'b0111: out = reg_file[7];
                    4'b1000: out = reg_file[8];
                    4'b1001: out = reg_file[9];
                    4'b1010: out = reg_file[10];
                    4'b1011: out = reg_file[11];
                    4'b1100: out = reg_file[12];
                    4'b1101: out = reg_file[13];
                    4'b1110: out = reg_file[14];
                    4'b1111: out = reg_file[15];
                    default: out = out; // Same here
                endcase
            end
        end 
    end

    assign out = reg_file[addr]; // always display register data at the port. 
    
        
    
endmodule