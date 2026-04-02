// pipe_reg.v
module pipe_reg #(parameter WIDTH = 32) (
    input clk, reset, flush, stall,
    input  [WIDTH-1:0] d,
    output reg [WIDTH-1:0] q
);
    always @(posedge clk) begin
        if (reset || flush) q <= 0;
        else if (!stall)    q <= d;
    end
endmodule