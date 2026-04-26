// Array sum benchmark
// N = 5
// ARRAY = [3, 7, 2, 9, 4]
// RESULT should become 25 at address 0x0200.

// R0 = sum
// R1 = LEN pointer
// R2 = len
// R3 = index
// R4 = 1
// R5 = 4-byte word stride
// R6 = array/result pointer
// R7 = current element

LIL 0x00
LIH 0x01
MOV R1, IMR
LOAD R2, R1

LIL 0x00
LIH 0x00
MOV R0, IMR
MOV R3, IMR

LIL 0x01
LIH 0x00
MOV R4, IMR

LIL 0x04
LIH 0x00
MOV R5, IMR

LIL 0x04
LIH 0x01
MOV R6, IMR

loop:
MOV CMPA, R3
MOV CMPB, R2
JPBLW body
JMP done

body:
LOAD R7, R6
ADD R0, R7
ADD R6, R5
ADD R3, R4
JMP loop

done:
LIL 0x00
LIH 0x02
MOV R6, IMR
STOR R0, R6
HLT
