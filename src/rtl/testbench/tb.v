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

  integer cycle_count;
  integer max_cycles;
  integer report_fd;
  integer pass;
  reg [DATA_ADDR_SPACE-1:0] result_addr;
  reg [DATA_WORD_WIDTH-1:0] expected;
  reg [DATA_WORD_WIDTH-1:0] actual;
  reg [1023:0] vcd_path;
  reg [1023:0] report_path;

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

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  initial begin
    max_cycles = 1000;
    result_addr = 28'h0000200;
    expected = 28'd25;
    vcd_path = "cpu_tb.vcd";
    report_path = "result.json";

    void'($value$plusargs("MAX_CYCLES=%d", max_cycles));
    void'($value$plusargs("RESULT_ADDR=%h", result_addr));
    void'($value$plusargs("EXPECTED=%d", expected));
    void'($value$plusargs("VCD=%s", vcd_path));
    void'($value$plusargs("REPORT=%s", report_path));

    $dumpfile(vcd_path);
    $dumpvars(0, cpu_tb);

    cycle_count = 0;
    reset = 1'b1;
    repeat (2) @(posedge clk);
    reset = 1'b0;

    while (!halt && cycle_count < max_cycles) begin
      @(posedge clk);
      cycle_count = cycle_count + 1;
    end

    actual = read_dmem_word28(result_addr);
    pass = halt && (actual == expected);
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
        $fwrite(report_fd, "  \"cycles\": %0d,\n", cycle_count);
        $fwrite(report_fd, "  \"ic\": %0d,\n", IC);
        $fwrite(report_fd, "  \"result_addr\": %0d,\n", result_addr);
        $fwrite(report_fd, "  \"expected\": %0d,\n", expected);
        $fwrite(report_fd, "  \"actual\": %0d\n", actual_value);
        $fwrite(report_fd, "}\n");
        $fclose(report_fd);
      end else begin
        $display("WARN: could not open report file %0s", report_path);
      end
    end
  endtask

endmodule
