module popcount #(
    parameter WIDTH = 28
)(
    input  [WIDTH-1:0] in,
    output reg [$clog2(WIDTH+1)-1:0] out
);

    integer i;
    always @(*) begin
        out = 0;
        for (i = 0; i < WIDTH; i = i + 1)
            out = out + in[i];
    end

endmodule