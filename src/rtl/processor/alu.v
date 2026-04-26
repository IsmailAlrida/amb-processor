//! This is the Arithmetic Logic Unit. It tackles the functions NOT, OR, AND, XOR, SHL, SHR, SAR, ADD, SUB, MOV
module alu #(
    //! Specifies the width of data words in the ALU
    parameter DATA_WORD_WIDTH = 28,
    //! Specifies the bit address space for all possible instructions. Now we have 10 instruction, making 4 bits the necessary amount for ALUCtrl.
    parameter CONTROL_OP_WIDTH = 4
) (
    //! Device clock
    input clk,
    //! External reset signal
    input reset,
    //! External halt signal
    input halt,
    //! Operand A consumes either the destination register (Ra) or the memory offset register (MEMOFF) for memory operations
    input [DATA_WORD_WIDTH-1:0] OperandA,
    //! Operand B consumes the source register data (Rb)
    input [DATA_WORD_WIDTH-1:0] OperandB,
    //! ALU control multiplexes which operation to carry out with the given data
    input [CONTROL_OP_WIDTH-1:0] ALUCtrl,
    //! A [DATA_wORD_WIDTH-1:0] result of the ALU operation
    output reg [DATA_WORD_WIDTH-1:0] result,
    //! Zero flag set when the result of an operation is 0
    output reg zero,
    //! A-less-than-B flag is set when... A is less than B (OperandA < OperandB). 
    output reg altb
);


    //TODO: Document this for the teroshdl documenter

    localparam  ALU_NOT = 4'b0000;
    localparam  ALU_OR  = 4'b0001;
    localparam  ALU_AND = 4'b0010;
    localparam  ALU_XOR = 4'b0011;
    localparam  ALU_SHL = 4'b0100;
    localparam  ALU_SHR = 4'b0101;
    localparam  ALU_SAR = 4'b0110;
    localparam  ALU_ADD = 4'b0111;
    localparam  ALU_SUB = 4'b1000;
    localparam  ALU_MOV = 4'b1001;


    //! Selects which of the many operations to conduct on Operand A and Operand B
    always @(*) begin : operation_select
        case (ALUCtrl)
            //! Invert OperandA
            // TODO: Add another NOT method to use the hardware efficiently by inverting BOTH OpA and OpB
            ALU_NOT : begin
                result = ~OperandA;
            end 
            ALU_OR : begin
                result = OperandA | OperandB;
            end
            ALU_AND : begin
                result = OperandA & OperandB;
            end
            ALU_XOR : begin
                result = OperandA ^^ OperandB;
            end
            ALU_SHL : begin
                result = OperandA << OperandB;
            end
            ALU_SHR : begin
                result = OperandA >> OperandB;
            end
            ALU_SAR : begin
                result = OperandA >>> OperandB;
            end
            ALU_ADD : begin
                result = OperandA + OperandB;
            end
            ALU_SUB : begin
                result = OperandA - OperandB;
            end
            ALU_MOV : begin
                result = OperandB;
            end

            //! Do nothing. Write back Ra as is.
            default:  result = OperandA;
        endcase

        zero = (OperandA == OperandB);
        altb = (OperandA < OperandB);
    end

endmodule
