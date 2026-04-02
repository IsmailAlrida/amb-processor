module conveyor_fsm (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start_cmd,
    input  wire       stop_cmd,
    input  wire       jam_fault,
    input  wire       clear_fault,
    output reg        motor_enable,
    output reg        accepting_items,
    output reg [1:0]  state_dbg
);

    localparam S_IDLE  = 2'd0;
    localparam S_RUN   = 2'd1;
    localparam S_PAUSE = 2'd2;
    localparam S_JAM   = 2'd3;

    reg [1:0] state_next;

    always @(*) begin
        state_next = state_dbg;

        case (state_dbg)
            S_IDLE: begin
                if (start_cmd)
                    state_next = S_RUN;
            end

            S_RUN: begin
                if (jam_fault)
                    state_next = S_JAM;
                else if (stop_cmd)
                    state_next = S_PAUSE;
            end

            S_PAUSE: begin
                if (start_cmd)
                    state_next = S_RUN;
            end

            S_JAM: begin
                if (clear_fault)
                    state_next = S_IDLE;
            end

            default: state_next = S_IDLE;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_dbg <= S_IDLE;
        else
            state_dbg <= state_next;
    end

    always @(*) begin
        motor_enable    = 1'b0;
        accepting_items = 1'b0;

        case (state_dbg)
            S_RUN: begin
                motor_enable    = 1'b1;
                accepting_items = 1'b1;
            end

            S_PAUSE: begin
                motor_enable    = 1'b0;
                accepting_items = 1'b0;
            end

            S_JAM: begin
                motor_enable    = 1'b0;
                accepting_items = 1'b0;
            end

            default: begin
                motor_enable    = 1'b0;
                accepting_items = 1'b0;
            end
        endcase
    end

endmodule
