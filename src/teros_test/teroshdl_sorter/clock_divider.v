module clock_divider #(
    parameter DIVISOR = 32'd25000000
)(
    input  wire clk,
    input  wire rst_n,
    output reg  clk_out
);

    reg [31:0] count_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count_reg <= 32'd0;
            clk_out   <= 1'b0;
        end else begin
            if (count_reg >= DIVISOR - 1) begin
                count_reg <= 32'd0;
                clk_out   <= ~clk_out;
            end else begin
                count_reg <= count_reg + 1'b1;
            end
        end
    end

endmodule
