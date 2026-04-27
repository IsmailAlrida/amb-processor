module jam_detector #(
    parameter MAX_STALL_CYCLES = 32'd1000000
)(
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    input  wire sensor_entry,
    input  wire clear_jam,
    output reg  jam_fault
);

    reg [31:0] stall_count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stall_count <= 32'd0;
            jam_fault   <= 1'b0;
        end else if (clear_jam) begin
            stall_count <= 32'd0;
            jam_fault   <= 1'b0;
        end else if (!enable || !sensor_entry) begin
            stall_count <= 32'd0;
        end else if (!jam_fault) begin
            if (stall_count >= MAX_STALL_CYCLES - 1) begin
                jam_fault <= 1'b1;
            end else begin
                stall_count <= stall_count + 1'b1;
            end
        end
    end

endmodule
