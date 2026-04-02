module pulse_stretcher #(
    parameter PULSE_CYCLES = 32'd50000
)(
    input  wire clk,
    input  wire rst_n,
    input  wire trigger,
    output reg  pulse_out
);

    reg [31:0] count_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count_reg  <= 32'd0;
            pulse_out  <= 1'b0;
        end else begin
            if (trigger && !pulse_out) begin
                pulse_out <= 1'b1;
                count_reg <= 32'd0;
            end else if (pulse_out) begin
                if (count_reg >= PULSE_CYCLES - 1) begin
                    pulse_out <= 1'b0;
                    count_reg <= 32'd0;
                end else begin
                    count_reg <= count_reg + 1'b1;
                end
            end
        end
    end

endmodule
