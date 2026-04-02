
module fadd (
    input a,b,cin,
    output cout,sum
);
    assign {cout, sum} = a+b+cin;
endmodule

module top_module (
    input [3:0] x,
    input [3:0] y, 
    output [4:0] sum);

    wire [4:0] carries;
    assign carries[0] = 1'b0;
    
    genvar i;
    generate
        for (i = 0; i < 4 ; i++ ) begin : gen_add_loop

            fadd fadder(
                .a(x[i]),
                .b(y[i]),
                .sum(sum[i]),
                .cout(carries[i+1]),
                .cin(carries[i])
            );
            
        end
    endgenerate
    assign sum[4] = carries[4];
   
endmodule

