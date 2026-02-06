# Mandatory ISA Requirements
• Instruction width: 15 bits (fixed-length)
• Word size (data width): 28 bits
• Address width: 28 bits
• Memory is byte-addressable
• All registers, ALU operations, and memory accesses operate on 28-bit words


# Instruction Storage and Program Counter Semantics
Although memory is byte-addressable and instructions are 15 bits wide,
instructions are stored in memory using the following alignment rule:
- Each instruction occupies two consecutive bytes (16 bits).
- Only 15 bits*are used for the instruction encoding.
- The remaining 1 bit is unused.
- The Program Counter (PC) stores a byte address. After fetching one instruction, thePC is incremented by 2.

Instruction storage example:
Byte address N Byte address N+1
[ unused | bit 14..8 ] [ bit 7..0 ]
PC → N Next PC → N + 2