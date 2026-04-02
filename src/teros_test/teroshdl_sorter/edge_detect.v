module edge_detect (
    input  wire clk,
    input  wire rst_n,
    input  wire signal_in,
    output wire rise_pulse,
    output wire fall_pulse
);

    reg signal_d;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            signal_d <= 1'b0;
        else
            signal_d <= signal_in;
    end

    assign rise_pulse =  signal_in & ~signal_d;
    assign fall_pulse = ~signal_in &  signal_d;

endmodule
