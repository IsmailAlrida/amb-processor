module bcd_adder #(
    parameter DIGITS = 100
)(
    input  [DIGITS*4-1:0] a,
    input  [DIGITS*4-1:0] b,
    input  cin,
    output cout,
    output [DIGITS*4-1:0] sum
);

    wire [DIGITS:0] carries;
    assign carries[0] = cin;
    assign cout = carries[DIGITS];

    genvar i;
    generate
        for (i = 0; i < DIGITS; i = i + 1) begin : bcd_add_gen
            bcd_fadd bcd_fadder (
                .a   (a[i*4+3 : i*4]),
                .b   (b[i*4+3 : i*4]),
                .cin (carries[i]),
                .cout(carries[i+1]),
                .sum (sum[i*4+3 : i*4])
            );
        end
    endgenerate

endmodule

//BY the way, localparam makes private, non-overridable parameters. 