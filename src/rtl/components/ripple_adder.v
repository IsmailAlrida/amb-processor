// ripple_adder.v
module ripc_adder #(paramter BIT_WIDTH = 28)( 
    input [BIT_WIDTH-1:0] a, b,
    input cin,
    output [BIT_WIDTH-1:0] cout,
    output [BIT_WIDTH-1:0] sum );
    
    // How can i assign the first cout[i-1] to be cin?
    // assign wire something = cin;
    wire [BIT_WIDTH:0] carry;
    assign carry[0] = cin;
    assign cout = carry[BIT_WIDTH:1];
  
    genvar i;
    generate
        for (i = 0; i < BIT_WIDTH; i++) begin : adder_gen_loop     
            fadd fadder(
                .a(a[i]),
                .b(b[i]),
                .sum(sum[i]),
                .cout(carry[i+1]),
                .cin(carry[i])
            );
        end
    endgenerate
                      

endmodule
