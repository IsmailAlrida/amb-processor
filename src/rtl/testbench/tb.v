`timescale 1ns/1ps

module cpu_tb;

  // Parameters
  localparam DATA_ADDR_SPACE = 28;
  localparam DATA_WORD_WIDTH = 28;
  localparam INSTRUCTION_WIDTH = 16;
  localparam INSTRUCTION_ADDRESS_SPACE = 28;
  localparam REG_ADDR_WIDTH = 4;
  localparam NUM_OF_REGS = 16;
  localparam IMEM_DEPTH = 4096;
  localparam DMEM_DEPTH = 4096;

  // Ports
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

  // Waveform-facing aliases. These do not change the CPU contract; they just
  // put the important CPU datapath/control probes at the cpu_tb scope.
  wire debug_halt;
  wire [INSTRUCTION_ADDRESS_SPACE-1:0] debug_IC;
  wire [INSTRUCTION_WIDTH-1:0] debug_instr;
  wire [6:0] debug_opcode;
  wire [DATA_ADDR_SPACE-1:0] debug_DataAddress;
  wire [DATA_WORD_WIDTH-1:0] debug_DataMemoryWrite;
  wire [DATA_WORD_WIDTH-1:0] debug_DataMemoryRead;
  wire debug_DmemReadEn;
  wire debug_DmemWriteEn;
  wire debug_RegWrite;
  wire [1:0] debug_RegDest;
  wire debug_MemOp;
  wire debug_BranchEqual;
  wire debug_BranchLt;
  wire debug_isJump;
  wire debug_LongJump;
  wire debug_isImmLoad;
  wire [3:0] debug_ALUCtrl;
  wire [1:0] debug_ImmSel;
  wire [2:0] debug_CMPType;
  wire [3:0] debug_ReadRegRa;
  wire [3:0] debug_ReadRegRb;
  wire [3:0] debug_WriteReg;
  wire [DATA_WORD_WIDTH-1:0] debug_ReadDataRa;
  wire [DATA_WORD_WIDTH-1:0] debug_ReadDataRb;
  wire [DATA_WORD_WIDTH-1:0] debug_OperandA;
  wire [DATA_WORD_WIDTH-1:0] debug_OperandB;
  wire [DATA_WORD_WIDTH-1:0] debug_ALURes;
  wire debug_zero;
  wire debug_altb;
  wire [DATA_WORD_WIDTH-1:0] debug_RegDataWrite;
  wire debug_WillBranch;
  wire [INSTRUCTION_ADDRESS_SPACE-1:0] debug_NextIC;

  integer cycle_count;
  integer max_cycles;
  integer report_fd;
  integer pass;
  integer check_result;
  reg [DATA_ADDR_SPACE-1:0] result_addr;
  reg [DATA_WORD_WIDTH-1:0] expected;
  reg [DATA_WORD_WIDTH-1:0] actual;
  reg [DATA_WORD_WIDTH-1:0] live_result;
  reg actual_valid;
  reg [1023:0] vcd_path;
  reg [1023:0] report_path;
  integer max_cycles_plusarg_seen;
  integer check_result_plusarg_seen;
  integer result_addr_plusarg_seen;
  integer expected_plusarg_seen;
  integer vcd_plusarg_seen;
  integer report_plusarg_seen;

  cpu #(
    .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
    .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
    .INSTRUCTION_WIDTH(INSTRUCTION_WIDTH),
    .INSTRUCTION_ADDRESS_SPACE(INSTRUCTION_ADDRESS_SPACE),
    .REG_ADDR_WIDTH(REG_ADDR_WIDTH),
    .NUM_OF_REGS(NUM_OF_REGS)
  ) cpu_inst (
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

  imem #(
    .INSTRUCTION_WIDTH(INSTRUCTION_WIDTH),
    .INSTRUCTION_ADDRESS_SPACE(INSTRUCTION_ADDRESS_SPACE),
    .DEPTH(IMEM_DEPTH)
  ) imem_inst (
    .clk(clk),
    .reset(reset),
    .halt(halt),
    .IC(IC),
    .instr(instr)
  );

  dmem #(
    .DATA_ADDR_SPACE(DATA_ADDR_SPACE),
    .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
    .DEPTH(DMEM_DEPTH)
  ) dmem_inst (
    .clk(clk),
    .reset(reset),
    .halt(halt),
    .Address(DataAddress),
    .DataIn(DataMemoryWrite),
    .DataOut(DataMemoryRead),
    .ReadEn(DmemReadEn),
    .WriteEn(DmemWriteEn)
  );

  assign debug_halt = halt;
  assign debug_IC = IC;
  assign debug_instr = instr;
  assign debug_opcode = cpu_inst.opcode;
  assign debug_DataAddress = DataAddress;
  assign debug_DataMemoryWrite = DataMemoryWrite;
  assign debug_DataMemoryRead = DataMemoryRead;
  assign debug_DmemReadEn = DmemReadEn;
  assign debug_DmemWriteEn = DmemWriteEn;
  assign debug_RegWrite = cpu_inst.RegWrite;
  assign debug_RegDest = cpu_inst.RegDest;
  assign debug_MemOp = cpu_inst.MemOp;
  assign debug_BranchEqual = cpu_inst.BranchEqual;
  assign debug_BranchLt = cpu_inst.BranchLt;
  assign debug_isJump = cpu_inst.isJump;
  assign debug_LongJump = cpu_inst.LongJump;
  assign debug_isImmLoad = cpu_inst.isImmLoad;
  assign debug_ALUCtrl = cpu_inst.ALUCtrl;
  assign debug_ImmSel = cpu_inst.ImmSel;
  assign debug_CMPType = cpu_inst.CMPType;
  assign debug_ReadRegRa = cpu_inst.ReadRegRa;
  assign debug_ReadRegRb = cpu_inst.ReadRegRb;
  assign debug_WriteReg = cpu_inst.WriteReg;
  assign debug_ReadDataRa = cpu_inst.ReadDataRa;
  assign debug_ReadDataRb = cpu_inst.ReadDataRb;
  assign debug_OperandA = cpu_inst.OperandA;
  assign debug_OperandB = cpu_inst.OperandB;
  assign debug_ALURes = cpu_inst.ALURes;
  assign debug_zero = cpu_inst.zerof;
  assign debug_altb = cpu_inst.altb;
  assign debug_RegDataWrite = cpu_inst.RegDataWrite;
  assign debug_WillBranch = cpu_inst.WillBranch;
  assign debug_NextIC = cpu_inst.NextIC;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  always @(posedge clk) begin
    #1 live_result = read_dmem_word28(result_addr);
  end

  initial begin
    max_cycles = 1000;
    check_result = 1;
    result_addr = 28'h0000200;
    expected = 28'd25;
    actual = {DATA_WORD_WIDTH{1'b0}};
    live_result = {DATA_WORD_WIDTH{1'b0}};
    actual_valid = 1'b0;
    vcd_path = "cpu_tb.vcd";
    report_path = "result.json";

    max_cycles_plusarg_seen = $value$plusargs("MAX_CYCLES=%d", max_cycles);
    check_result_plusarg_seen = $value$plusargs("CHECK_RESULT=%d", check_result);
    result_addr_plusarg_seen = $value$plusargs("RESULT_ADDR=%h", result_addr);
    expected_plusarg_seen = $value$plusargs("EXPECTED=%d", expected);
    vcd_plusarg_seen = $value$plusargs("VCD=%s", vcd_path);
    report_plusarg_seen = $value$plusargs("REPORT=%s", report_path);

    $dumpfile(vcd_path);
    $dumpvars(0, cpu_tb);

    $display("cpu_tb config: max_cycles=%0d%s check_result=%0d%s result_addr=0x%07h%s expected=%0d%s",
             max_cycles, max_cycles_plusarg_seen ? " (plusarg)" : " (default)",
             check_result, check_result_plusarg_seen ? " (plusarg)" : " (default)",
             result_addr, result_addr_plusarg_seen ? " (plusarg)" : " (default)",
             expected, expected_plusarg_seen ? " (plusarg)" : " (default)");

    cycle_count = 0;
    reset = 1'b1;
    repeat (2) @(posedge clk);
    reset = 1'b0;

    while (!halt && cycle_count < max_cycles) begin
      @(posedge clk);
      cycle_count = cycle_count + 1;
    end

    actual = read_dmem_word28(result_addr);
    live_result = actual;
    actual_valid = 1'b1;
    pass = halt && (!check_result || actual === expected);
    write_report(pass, actual);

    if (pass) begin
      $display("PASS: cycles=%0d result[0x%07h]=%0d", cycle_count, result_addr, actual);
      $finish;
    end else begin
      $display("FAIL: halt=%0b cycles=%0d result[0x%07h]=%0d expected=%0d",
               halt, cycle_count, result_addr, actual, expected);
      $fatal(1);
    end
  end

  function [DATA_WORD_WIDTH-1:0] read_dmem_word28;
    input [DATA_ADDR_SPACE-1:0] addr;
    begin
      if (addr + 3 < DMEM_DEPTH) begin
        read_dmem_word28 = {
          dmem_inst.dmemory[addr + 3][3:0],
          dmem_inst.dmemory[addr + 2],
          dmem_inst.dmemory[addr + 1],
          dmem_inst.dmemory[addr]
        };
      end else begin
        read_dmem_word28 = {DATA_WORD_WIDTH{1'b0}};
      end
    end
  endfunction

  task write_report;
    input pass_value;
    input [DATA_WORD_WIDTH-1:0] actual_value;
    begin
      report_fd = $fopen(report_path, "w");
      if (report_fd != 0) begin
        $fwrite(report_fd, "{\n");
        $fwrite(report_fd, "  \"pass\": %s,\n", pass_value ? "true" : "false");
        $fwrite(report_fd, "  \"halt\": %s,\n", halt ? "true" : "false");
        $fwrite(report_fd, "  \"check_result\": %0d,\n", check_result);
        $fwrite(report_fd, "  \"cycles\": %0d,\n", cycle_count);
        $fwrite(report_fd, "  \"ic\": %0d,\n", IC);
        $fwrite(report_fd, "  \"result_addr\": %0d,\n", result_addr);
        $fwrite(report_fd, "  \"result_addr_hex\": \"%07h\",\n", result_addr);
        $fwrite(report_fd, "  \"expected\": %0d,\n", expected);
        $fwrite(report_fd, "  \"expected_hex\": \"%07h\",\n", expected);
        $fwrite(report_fd, "  \"actual\": %0d,\n", actual_value);
        $fwrite(report_fd, "  \"actual_hex\": \"%07h\",\n", actual_value);
        $fwrite(report_fd, "  \"actual_valid\": %0d,\n", actual_valid);
        $fwrite(report_fd, "  \"live_result\": %0d,\n", live_result);
        $fwrite(report_fd, "  \"live_result_hex\": \"%07h\",\n", live_result);
        $fwrite(report_fd, "  \"max_cycles_plusarg_seen\": %0d,\n", max_cycles_plusarg_seen);
        $fwrite(report_fd, "  \"check_result_plusarg_seen\": %0d,\n", check_result_plusarg_seen);
        $fwrite(report_fd, "  \"result_addr_plusarg_seen\": %0d,\n", result_addr_plusarg_seen);
        $fwrite(report_fd, "  \"expected_plusarg_seen\": %0d,\n", expected_plusarg_seen);
        $fwrite(report_fd, "  \"vcd_plusarg_seen\": %0d,\n", vcd_plusarg_seen);
        $fwrite(report_fd, "  \"report_plusarg_seen\": %0d\n", report_plusarg_seen);
        $fwrite(report_fd, "}\n");
        $fclose(report_fd);
      end else begin
        $display("WARN: could not open report file %0s", report_path);
      end
    end
  endtask

endmodule
