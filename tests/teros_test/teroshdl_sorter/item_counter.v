module item_counter #(
    parameter WIDTH = 16
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             item_valid,
    input  wire             route_a,
    input  wire             route_b,
    input  wire             route_c,
    input  wire             route_reject,
    output reg [WIDTH-1:0]  total_count,
    output reg [WIDTH-1:0]  count_a,
    output reg [WIDTH-1:0]  count_b,
    output reg [WIDTH-1:0]  count_c,
    output reg [WIDTH-1:0]  count_reject
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            total_count   <= {WIDTH{1'b0}};
            count_a       <= {WIDTH{1'b0}};
            count_b       <= {WIDTH{1'b0}};
            count_c       <= {WIDTH{1'b0}};
            count_reject  <= {WIDTH{1'b0}};
        end else if (item_valid) begin
            total_count <= total_count + 1'b1;

            if (route_a)
                count_a <= count_a + 1'b1;

            if (route_b)
                count_b <= count_b + 1'b1;

            if (route_c)
                count_c <= count_c + 1'b1;

            if (route_reject)
                count_reject <= count_reject + 1'b1;
        end
    end

endmodule
