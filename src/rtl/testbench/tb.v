`timescale 1ns/1ps

//! Standalone RTL harness that connects the CPU core to instruction/data memories and checks benchmark results.
module cpu_tb;

  // Parameters
  //! Width of the data memory byte address bus.
  localparam DATA_ADDR_SPACE = 28;
  //! Width of each CPU data word.
  localparam DATA_WORD_WIDTH = 28;
  //! Stored instruction width.
  localparam INSTRUCTION_WIDTH = 16;
  //! Width of the instruction counter byte address.
  localparam INSTRUCTION_ADDRESS_SPACE = 28;
  //! Width of architectural register selectors.
  localparam REG_ADDR_WIDTH = 4;
  //! Number of architectural register slots.
  localparam NUM_OF_REGS = 16;
  //! Number of bytes in the instruction memory model.
  localparam IMEM_DEPTH = 4096;
  //! Number of bytes in the data memory model.
  localparam DMEM_DEPTH = 4096;

  // Ports
  //! Testbench-generated CPU clock.
  reg clk;
  //! Testbench-generated active-high reset.
  reg reset;
  //! Halt signal produced by the CPU core.
  wire halt;
  //! Current instruction byte address from the CPU.
  wire [INSTRUCTION_ADDRESS_SPACE-1:0] IC;
  //! Instruction word returned by instruction memory.
  wire [INSTRUCTION_WIDTH-1:0] instr;
  //! CPU data memory byte address.
  wire [DATA_ADDR_SPACE-1:0] DataAddress;
  //! CPU store data bus.
  wire [DATA_WORD_WIDTH-1:0] DataMemoryWrite;
  //! CPU load data bus.
  wire [DATA_WORD_WIDTH-1:0] DataMemoryRead;
  //! CPU data memory read enable.
  wire DmemReadEn;
  //! CPU data memory write enable.
  wire DmemWriteEn;

  //! Number of executed cycles observed by the harness.
  integer cycle_count;
  //! Timeout limit before the harness fails the run.
  integer max_cycles;
  //! File descriptor used for result report emission.
  integer report_fd;
  //! Final pass/fail result computed by the harness.
  integer pass;
  //! Enables or bypasses final result comparison.
  integer check_result;
  //! Data memory byte address sampled as the benchmark result.
  reg [DATA_ADDR_SPACE-1:0] result_addr;
  //! Expected benchmark result value.
  reg [DATA_WORD_WIDTH-1:0] expected;
  //! Final sampled value from data memory after halt or timeout.
  reg [DATA_WORD_WIDTH-1:0] actual;
  //! Live sampled value from data memory at result_addr for waveform debugging.
  reg [DATA_WORD_WIDTH-1:0] live_result;
  //! Indicates that actual has been sampled and is valid.
  reg actual_valid;
  //! VCD output path selected by default or plusarg.
  reg [1023:0] vcd_path;
  //! JSON report output path selected by default or plusarg.
  reg [1023:0] report_path;
  //! Records whether MAX_CYCLES was provided as a plusarg.
  integer max_cycles_plusarg_seen;
  //! Records whether CHECK_RESULT was provided as a plusarg.
  integer check_result_plusarg_seen;
  //! Records whether RESULT_ADDR was provided as a plusarg.
  integer result_addr_plusarg_seen;
  //! Records whether EXPECTED was provided as a plusarg.
  integer expected_plusarg_seen;
  //! Records whether VCD was provided as a plusarg.
  integer vcd_plusarg_seen;
  //! Records whether REPORT was provided as a plusarg.
  integer report_plusarg_seen;

  //! CPU core under test.
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

  //! Instruction memory model connected to the CPU fetch interface.
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

  //! Data memory model connected to the CPU load/store interface.
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

  //! Generates the free-running testbench clock.
  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  //! Samples the benchmark result memory word one timestep after each clock edge.
  always @(posedge clk) begin : live_result_sample
    #1 live_result = read_dmem_word28(result_addr);
  end

  //! Configures the run, applies reset, waits for halt or timeout, and writes the final report.
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

  //! Reads a 28-bit little-endian word directly from the data memory model.
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

  //! Writes a JSON-style report with pass/fail, timing, plusarg, and result fields.
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
