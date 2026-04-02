// This is only for learning, but guess what, that is cool.
module comparator #(
    parameter IN_BIT_WIDTH = 28
) (
    input [IN_BIT_WIDTH-1:0] a,
    input [IN_BIT_WIDTH-1:0] b,
    output out
);
    assign out = (a == b); // Apparantly you can generate comparators like this
endmodule