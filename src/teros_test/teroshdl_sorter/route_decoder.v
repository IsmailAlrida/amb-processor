module route_decoder (
    input  wire [1:0] item_type,
    output reg        route_a,
    output reg        route_b,
    output reg        route_c,
    output reg        route_reject
);

    always @(*) begin
        route_a      = 1'b0;
        route_b      = 1'b0;
        route_c      = 1'b0;
        route_reject = 1'b0;

        case (item_type)
            2'b00: route_a      = 1'b1;
            2'b01: route_b      = 1'b1;
            2'b10: route_c      = 1'b1;
            2'b11: route_reject = 1'b1;
            default: route_reject = 1'b1;
        endcase
    end

endmodule
