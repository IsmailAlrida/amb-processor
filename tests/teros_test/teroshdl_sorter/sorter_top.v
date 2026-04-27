module sorter_top #(
    parameter DEBOUNCE_COUNT    = 32'd250000,
    parameter JAM_MAX_CYCLES    = 32'd1000000,
    parameter DIVERTER_PULSE_CYCLES = 32'd50000,
    parameter HEARTBEAT_DIVISOR = 32'd25000000
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        btn_start,
    input  wire        btn_stop,
    input  wire        btn_clear_jam,
    input  wire        sensor_entry,
    input  wire [1:0]  item_type,

    output wire        conveyor_motor,
    output wire        diverter_a,
    output wire        diverter_b,
    output wire        diverter_c,
    output wire        diverter_reject,
    output wire        alarm_jam,
    output wire        heartbeat_led,
    output wire [1:0]  state_dbg,
    output wire [15:0] total_count,
    output wire [15:0] count_a,
    output wire [15:0] count_b,
    output wire [15:0] count_c,
    output wire [15:0] count_reject,
    output wire [63:0] status_word
);

    wire start_db;
    wire stop_db;
    wire clear_db;

    wire start_pulse;
    wire stop_pulse;
    wire clear_pulse;
    wire entry_rise;

    wire accepting_items;
    wire jam_fault;

    wire route_a_raw;
    wire route_b_raw;
    wire route_c_raw;
    wire route_reject_raw;

    wire item_accepted;

    debounce #(.COUNT_MAX(DEBOUNCE_COUNT)) u_db_start (
        .clk(clk),
        .rst_n(rst_n),
        .noisy_in(btn_start),
        .clean_out(start_db)
    );

    debounce #(.COUNT_MAX(DEBOUNCE_COUNT)) u_db_stop (
        .clk(clk),
        .rst_n(rst_n),
        .noisy_in(btn_stop),
        .clean_out(stop_db)
    );

    debounce #(.COUNT_MAX(DEBOUNCE_COUNT)) u_db_clear (
        .clk(clk),
        .rst_n(rst_n),
        .noisy_in(btn_clear_jam),
        .clean_out(clear_db)
    );

    edge_detect u_edge_start (
        .clk(clk),
        .rst_n(rst_n),
        .signal_in(start_db),
        .rise_pulse(start_pulse),
        .fall_pulse()
    );

    edge_detect u_edge_stop (
        .clk(clk),
        .rst_n(rst_n),
        .signal_in(stop_db),
        .rise_pulse(stop_pulse),
        .fall_pulse()
    );

    edge_detect u_edge_clear (
        .clk(clk),
        .rst_n(rst_n),
        .signal_in(clear_db),
        .rise_pulse(clear_pulse),
        .fall_pulse()
    );

    edge_detect u_edge_entry (
        .clk(clk),
        .rst_n(rst_n),
        .signal_in(sensor_entry),
        .rise_pulse(entry_rise),
        .fall_pulse()
    );

    conveyor_fsm u_fsm (
        .clk(clk),
        .rst_n(rst_n),
        .start_cmd(start_pulse),
        .stop_cmd(stop_pulse),
        .jam_fault(jam_fault),
        .clear_fault(clear_pulse),
        .motor_enable(conveyor_motor),
        .accepting_items(accepting_items),
        .state_dbg(state_dbg)
    );

    jam_detector #(.MAX_STALL_CYCLES(JAM_MAX_CYCLES)) u_jam (
        .clk(clk),
        .rst_n(rst_n),
        .enable(conveyor_motor),
        .sensor_entry(sensor_entry),
        .clear_jam(clear_pulse),
        .jam_fault(jam_fault)
    );

    route_decoder u_decoder (
        .item_type(item_type),
        .route_a(route_a_raw),
        .route_b(route_b_raw),
        .route_c(route_c_raw),
        .route_reject(route_reject_raw)
    );

    assign item_accepted = entry_rise & accepting_items & ~jam_fault;

    pulse_stretcher #(.PULSE_CYCLES(DIVERTER_PULSE_CYCLES)) u_div_a (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(item_accepted & route_a_raw),
        .pulse_out(diverter_a)
    );

    pulse_stretcher #(.PULSE_CYCLES(DIVERTER_PULSE_CYCLES)) u_div_b (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(item_accepted & route_b_raw),
        .pulse_out(diverter_b)
    );

    pulse_stretcher #(.PULSE_CYCLES(DIVERTER_PULSE_CYCLES)) u_div_c (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(item_accepted & route_c_raw),
        .pulse_out(diverter_c)
    );

    pulse_stretcher #(.PULSE_CYCLES(DIVERTER_PULSE_CYCLES)) u_div_reject (
        .clk(clk),
        .rst_n(rst_n),
        .trigger(item_accepted & route_reject_raw),
        .pulse_out(diverter_reject)
    );

    item_counter #(.WIDTH(16)) u_counter (
        .clk(clk),
        .rst_n(rst_n),
        .item_valid(item_accepted),
        .route_a(route_a_raw),
        .route_b(route_b_raw),
        .route_c(route_c_raw),
        .route_reject(route_reject_raw),
        .total_count(total_count),
        .count_a(count_a),
        .count_b(count_b),
        .count_c(count_c),
        .count_reject(count_reject)
    );

    clock_divider #(.DIVISOR(HEARTBEAT_DIVISOR)) u_heartbeat (
        .clk(clk),
        .rst_n(rst_n),
        .clk_out(heartbeat_led)
    );

    status_packer u_status (
        .state_dbg(state_dbg),
        .jam_fault(jam_fault),
        .motor_enable(conveyor_motor),
        .heartbeat(heartbeat_led),
        .route_a(route_a_raw),
        .route_b(route_b_raw),
        .route_c(route_c_raw),
        .route_reject(route_reject_raw),
        .total_count(total_count),
        .count_a(count_a),
        .count_b(count_b),
        .count_c(count_c),
        .count_reject(count_reject),
        .status_word(status_word)
    );

    assign alarm_jam = jam_fault;

endmodule
