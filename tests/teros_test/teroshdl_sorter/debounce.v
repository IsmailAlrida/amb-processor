module debounce #(
    parameter COUNT_MAX = 32'd250000
)(
    input  wire clk,
    input  wire rst_n,
    input  wire noisy_in,
    output reg  clean_out
);

    reg [31:0] count_reg;
    reg        sync_ff1;
    reg        sync_ff2;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync_ff1  <= 1'b0;
            sync_ff2  <= 1'b0;
            count_reg <= 32'd0;
            clean_out <= 1'b0;
        end else begin
            sync_ff1 <= noisy_in;
            sync_ff2 <= sync_ff1;

            if (sync_ff2 == clean_out) begin
                count_reg <= 32'd0;
            end else begin
                if (count_reg >= COUNT_MAX - 1) begin
                    clean_out <= sync_ff2;
                    count_reg <= 32'd0;
                end else begin
                    count_reg <= count_reg + 1'b1;
                end
            end
        end
    end

endmodule
