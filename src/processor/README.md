This folder here is for the HDL files of our processor, where we will write in verilog our cool new hardware.

btw, here some neat note tidbits for stuff:

``` verilog

// ============================================================================
// VERILOG ASSIGNMENT & CONCATENATION CHEAT SHEET
// ============================================================================

module assignment_pro_tricks (
    input  logic [7:0]  a, b,        // 8-bit inputs
    input  logic [31:0] inst,       // 32-bit CPU Instruction
    input  logic        sel, clk,   // Control signals
    output logic [31:0] out_32,     // 32-bit output
    output logic [7:0]  out_8,      // 8-bit output
    output logic        zero_flag,  // 1-bit status
    output logic        carry_out   // 1-bit overflow
);

    // 1. CONCATENATION (Bundling)
    // Combines multiple signals into one larger bus.
    wire [15:0] bundle = {a, b}; 


    // 2. UNPACKING (The Splitter)
    // Great for Instruction Decoding. Breaks a bus into named pieces.
    wire [5:0]  opcode;
    wire [4:0]  rs, rt;
    wire [15:0] immediate;
    assign {opcode, rs, rt, immediate} = inst; 


    // 3. REPLICATION (Sign Extension)
    // Repeat a bit N times. Syntax: {number_of_times{signal}}
    // Example: Sign-extending an 8-bit number to 32-bit by repeating the MSB.
    assign out_32 = { {24{a[7]}}, a };


    // 4. ARITHMETIC WITH CARRY-OUT
    // By making the Left-Hand Side (LHS) 1-bit wider, you "capture" the overflow bit.
    assign {carry_out, out_8} = a + b;


    // 5. REDUCTION OPERATORS (The "Super Gate")
    // Applies a single gate (AND, OR, XOR) across EVERY bit in a bus.
    assign zero_flag = ~|out_8;   // "NOR" reduction: Returns 1 only if all bits are 0.
    wire all_ones    = &a;        // Returns 1 only if every bit in 'a' is 1.
    wire parity      = ^a;        // XOR reduction: Returns 1 if there's an odd number of 1s.


    // 6. CONDITIONAL ASSIGNMENT (The 1-Line Mux)
    // Syntax: (condition) ? (value_if_true) : (value_if_false)
    assign out_8 = (sel) ? a : b;


    // 7. SWIZZLING (Bit Reordering / Endianness)
    // Manually re-mapping bits. This creates NO logic gates, just wires!
    wire [7:0] reversed_a = {a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]};


    // 8. SHIFT BY CONCATENATION (Hard-wired shift)
    // Much more "obvious" to the synthesizer than using << or >> for fixed amounts.
    // Logic: Multiply 'a' by 4 (Shift left 2) and pad with zeros.
    wire [9:0] times_four = {a, 2'b00};


    // 9. THE "DON'T CARE" MASK
    // Using concatenation to modify only specific bits while keeping others.
    wire [31:0] modified_inst = {inst[31:16], 16'hFFFF}; // Force lower 16 bits to 1.

endmodule


```