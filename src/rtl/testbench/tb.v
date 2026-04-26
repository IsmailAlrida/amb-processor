
module cpu_tb;

  // Parameters
  localparam DATA_ADDR_SPACE = 28;
  localparam DATA_WORD_WIDTH = 28;
  localparam INSTRUCTION_WIDTH = 16;
  localparam INSTRUCTION_ADDRESS_SPACE = 28;
  localparam REG_ADDR_WIDTH = 4;
  localparam NUM_OF_REGS = 16;

  //Ports
  reg clk;
  reg reset;
  wire halt;
  wire [INSTRUCTION_ADDRESS_SPACE-1:0] IC;
  wire [INSTRUCTION_WIDTH-1:0] instr;
  wire [DATA_ADDR_SPACE-1:0] DataAddress;
  wire [DATA_WORD_WIDTH-1:0] DataMemoryWrite;
  wire [DATA_WORD_WIDTH-1:0] DataMemoryRead;
  wire DmemReadEn;
  wire DmemWriteEn;

  cpu # (
    .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
    .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
    .INSTRUCTION_WIDTH(INSTRUCTION_WIDTH),
    .INSTRUCTION_ADDRESS_SPACE(INSTRUCTION_ADDRESS_SPACE),
    .REG_ADDR_WIDTH(REG_ADDR_WIDTH),
    .NUM_OF_REGS(NUM_OF_REGS)
  )
  cpu_inst (
    .clk(clk),
    .reset(reset),
    .halt(halt),
    .IC(IC),
    .instr(instr),
    .DataAddress(DataAddress),
    .DataMemoryWrite(DataMemoryWrite),
    .DataMemoryRead(DataMemoryRead),
    .DmemReadEn(DmemReadEn),
    .DmemWriteEn(DmemWriteEn)
  );

   imem # (
    .INSTRUCTION_WIDTH(INSTRUCTION_WIDTH),
    .INSTRUCTION_ADDRESS_SPACE(INSTRUCTION_ADDRESS_SPACE)
   )
   imem_inst(
    .clk(clk),
    .reset(reset),
    .halt(halt),
    .IC(IC),
    .instr(instr)
   );

   dmem # (
    .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
    .DATA_WORD_WIDTH(DATA_WORD_WIDTH)
   )
   dmem_inst(
    .clk(clk),
    .reset(reset),
    .halt(halt),
    .Address(DataAddress),
    .DataIn(DataMemoryWrite),
    .DataOut(DataMemoryRead),
    .ReadEn(DmemReadEn),
    .WriteEn(DmemWriteEn)
   );

  initial begin
    clk = 1'b0;
    reset = 1'b1;
    #20 reset = 1'b0;
  end

  always #5 clk = !clk;

endmodule
