
# General Purpose Registers

Our microprocessor has 16 28-bit registers
the first one R0 - R7 are general purpose and can be used by the user in any operation
IC is the instruction counter register the holds the value of the next instruction to be executed. after an instruction is done its value will be increased by two each time.
SP is the stack pointer : it will be used with stack operations if needed in the future.
LC is the loop counter : it hold the value for number of loop when used with jumps functions
SHC is the shift counter : it holds the amount of bits to be shifted during shift operations (SHL, SHR, SAR).
JMPOFF : holds the jmp offset value that will be added to the jmp function immediate during long jump operations
MEMOFF : holds the memory offset value that will be added to the load and store functions immediate.

CMPA and CMPB are used in the branching instructions JPBLW and JPEQ where CMPA is the first item in the inequality and CMPB is the second item. 


# Register to Register operations 

The opcode is define by MSbits as 001 the remaining bits define the function.
Ra is the destination and Rb is the source for binary operations.
The result will be written in the destination and override its value and the source will remain the same.

7 bits of opcode , 4 bits of register a select and 4 bits of register b select 

NOT [R]         |    001 0000
OR [R] , [R]    |    001 0001
AND [R] , [R]   |    001 0010
XOR [R] , [R]   |    001 0011
SHL [R]         |    001 0100
SHR [R]         |    001 0101
SAR [R]         |    001 0110
ADD [R] , [R]   |    001 0111
SUB [R] , [R]   |    001 1000
MOV [R] , [R]   |    001 1001

### Shift operation behavior (no ambiguity)

- SHL, SHR, and SAR use one register operand only (the destination register).
- The shift amount is read from SHC.
- The encoded Rb field is ignored for SHL/SHR/SAR.
- Example: `LIL SHC, 4` then `SHL R0` shifts `R0` by 4 bits.
- For shift amounts greater than or equal to register width (28 bits):
  - SHL result is 0
  - SHR result is 0
  - SAR result is sign-filled (all 1s for negative, all 0s for positive)

# General operations 

These will share the register to register format due to it having 7 bits and they start with 000 and don't care about register values

HLT   000 0000 halt CPU operations 
NOP  000 0000   proceed with no action

# Jump operation 

These start with the value 01 and has 4 functions. the jump immediate can be up to 11 bits
4 bits of opcode and the 11 bits for the immediate.
## JMP [imm]  (0100)

this function jumps the programme from the current instruction into (immediate value) instructions later 

in hardware first the immediate value is shifted by 1 bit because the instruction counter move by 2 each time and then the value is added to the instruction counter

## JMPL [imm] (0101) : long jump

this function jumps the programme from the current instruction into the immediate value after

in hardware first the immediate value is shifted by 1 bit and then added to the JMPOFF register value and lastly the resultant value is added to the instruction counter

## JPEQ [imm] (0110 ) and JPBLW [imm] (0111)

works similar to the long jmp but only happen with the condition is met wither it being equal or below **(the instruction can only be used with CMPA and CMPB registers to do comparison. if you want to compare to items the values must be moved to them where CMPA is the first item and CMPB is the second item)**. using any of them with the jump function and code manipulations can give the opposite conditions such as Jump not equal or jump above

## Immediate operations 

it has only 4 functions and defined with the MSB of the opcode as 1 
3 bits of opcode , 4 bits of register select and the 8 bits for the immediate.
we choose the immediate value to be 8 to be compatible with the memory being byte addressable

## LIL [R] , [imm] (100)

this function loads the immediate value into the first bits of the register (7 - 0) 

## LIH [R] , [imm] (101)

this function loads the immediate value into the second lowest 8 bits of the register (15 - 8) 

## LOAD [R] , [imm] (110)

This function loads the value from the memory address of the immediate + the MEMOFF register value to the selected register

## STOR [R] , [imm] (111)

This function loads the value from the selected register to the memory address of the immediate + the MEMOFF register value
