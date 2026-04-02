module rule110(
    input clk,
    input load,
    input [511:0] data,
    output [511:0] q
); 

    wire [511:0] left;
    wire [511:0] right;

    always @(posedge clk) begin
        if (load) begin
            q = data;
        end else begin
            left = q >> 1;
            right = q << 1;
            q = (q ^ right) | ((~left) & right);
        end

    end

endmodule