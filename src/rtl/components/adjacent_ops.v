module adjacent_and #(
    parameter WIDTH = 4,
    parameter WRAP  = 0
)(
    input  [WIDTH-1:0] in,
    output [WIDTH-1:0] out
);

    genvar i;
    generate
        for (i = 0; i < WIDTH-1; i = i + 1) begin : gen_and
            assign out[i] = in[i] & in[i+1];
        end

        if (WRAP) begin : gen_wrap
            assign out[WIDTH-1] = in[WIDTH-1] & in[0];
        end else begin : gen_no_wrap
            assign out[WIDTH-1] = 1'b0;
        end
    endgenerate

endmodule


module adjacent_or #(
    parameter WIDTH = 4,
    parameter WRAP  = 0
)(
    input  [WIDTH-1:0] in,
    output [WIDTH-1:0] out
);

    genvar i;
    generate
        for (i = 0; i < WIDTH-1; i = i + 1) begin : gen_or
            assign out[i] = in[i] | in[i+1];
        end

        if (WRAP) begin : gen_wrap
            assign out[WIDTH-1] = in[WIDTH-1] | in[0];
        end else begin : gen_no_wrap
            assign out[WIDTH-1] = 1'b0;
        end
    endgenerate

endmodule


module adjacent_xor #(
    parameter WIDTH = 4,
    parameter WRAP  = 1
)(
    input  [WIDTH-1:0] in,
    output [WIDTH-1:0] out
);

    genvar i;
    generate
        for (i = 0; i < WIDTH-1; i = i + 1) begin : gen_xor
            assign out[i] = in[i] ^ in[i+1];
        end

        if (WRAP) begin : gen_wrap
            assign out[WIDTH-1] = in[WIDTH-1] ^ in[0];
        end else begin : gen_no_wrap
            assign out[WIDTH-1] = 1'b0;
        end
    endgenerate

endmodule