module top_module( 
    input  [99:0] in,
    output [98:0] out_both,
    output [99:1] out_any,
    output [99:0] out_different
);
	// This is actually so much better than doing a for loop, meet VECTOR SLICING. Something i shoudlve done a long time ago
    assign out_both           = in[98:0] & in[99:1];
    assign out_any            = in[99:1] | in[98:0];
    assign out_different[98:0]= in[98:0] ^ in[99:1];
    assign out_different[99]  = in[99] ^ in[0];

endmodule