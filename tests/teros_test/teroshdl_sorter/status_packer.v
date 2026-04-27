module status_packer (
    input  wire [1:0]  state_dbg,
    input  wire        jam_fault,
    input  wire        motor_enable,
    input  wire        heartbeat,
    input  wire        route_a,
    input  wire        route_b,
    input  wire        route_c,
    input  wire        route_reject,
    input  wire [15:0] total_count,
    input  wire [15:0] count_a,
    input  wire [15:0] count_b,
    input  wire [15:0] count_c,
    input  wire [15:0] count_reject,
    output wire [63:0] status_word
);

    assign status_word = {
        8'hA5,
        state_dbg,
        jam_fault,
        motor_enable,
        heartbeat,
        3'b000,
        total_count[7:0],
        count_a[7:0],
        count_b[7:0],
        count_c[7:0],
        count_reject[7:0],
        4'b0000,
        route_reject,
        route_c,
        route_b,
        route_a
    };

endmodule
