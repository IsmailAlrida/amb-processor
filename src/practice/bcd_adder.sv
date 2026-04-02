module top_module ( 
    input [15:0] a, b,
    input cin,
    output cout,
    output [15:0] sum );

    wire [4:0] carries;
    assign carries[0] = cin;
    assign cout = carries[4];

    genvar i;
    generate
        for ( i=0 ; i < 4 ; i++ ) begin : bcd_fadd
            bcd_fadd bcd_fadder (
                .a(a[4*i +: 4]),
                .b(b[4*i +: 4]),
                .cin(carries[i]),
                .cout(carries[i+1]),
                .sum(sum[4*i])
            );
        end
    endgenerate
endmodule
