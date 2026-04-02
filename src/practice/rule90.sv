module rule90(
    input clk,
    input load,
    input [511:0] data,
    output [511:0] q ); 

    reg [512: -1] data_with_edges;
    assign data_with_edges[512] = 1'b0;
    assign data_with_edges[-1] = 1'b0;

    integer i;
    always @(posedge clk) begin
        if (load) begin
            data_with_edges[511:0] <= data;
        end else begin
            for (i=0; i < 512 ;i++ ) begin
                data_with_edges[i] <= data_with_edges[i-1]^data_with_edges[i+1];
				//need to somehow update the data_with_edges to reflect th               
            end
        end
    end
    
    assign q = data_with_edges[511:0];
endmodule


/*

The problem statement from HDLbits for those curious:
Rule 90 is a one-dimensional cellular automaton with interesting properties.

The rules are simple. There is a one-dimensional array of cells (on or off). At each time step, 
the next state of each cell is the XOR of the cell's two current neighbours. A more verbose way of expressing 
this rule is the following table, where a cell's next state is a function of itself and its two neighbours:

Left	Center	Right	Center's next state
1	1	1	0
1	1	0	1
1	0	1	0
1	0	0	1
0	1	1	1
0	1	0	0
0	0	1	1
0	0	0	0
(The name "Rule 90" comes from reading the "next state" column: 01011010 is decimal 90.)


In this circuit, create a 512-cell system (q[511:0]), and advance by one time step each clock cycle. 
The load input indicates the state of the system should be loaded with data[511:0]. Assume the boundaries (q[-1] and q[512]) 
are both zero (off).



So APPARENTLY, if we did this instead of the for loop:

    q = (q << 1) ^ (q >> 1);

We would get the same result.

Doing something like << 1 or >> 1 to a vector such as q shifts the whole array to the right/left once
so what this means for this specific problem to acheive q[n] = q[n-1] ^ q[n+1]:

Index:          [3]   [2]   [1]   [0]
-----------------------------------------
q >> 1:          0   q[3]  q[2]  q[1]   <-- All Left Neighbors
q << 1:        q[2]  q[1]  q[0]    0    <-- All Right Neighbors
-----------------------------------------
XOR Result:    Next  Next  Next  Next   (All 4 bits calculated at once!)
-- Source: Gemini

Next is then equal to what we wanted and it is calculated all in parallel rather than a serial for loop
*/