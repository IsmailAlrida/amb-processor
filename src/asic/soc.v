module soc (
    input clk,
    input reset,
    output halt
);

    wire [27:0] IC;
    wire [15:0] instr;

    wire [27:0] data_addr;
    wire [27:0] data_wdata;
    wire [27:0] data_rdata;
    wire dmem_read_en;
    wire dmem_write_en;

    cpu cpu_inst (
        .clk(clk),
        .reset(reset),
        .halt(halt),
        .IC(IC),
        .instr(instr),
        .DataAddress(data_addr),
        .DataMemoryWrite(data_wdata),
        .DataMemoryRead(data_rdata),
        .DmemReadEn(dmem_read_en),
        .DmemWriteEn(dmem_write_en)
    );

    sram_1rw1r_32_256_8_sky130 dmem (
    .clk0(clk),
    .csb0(csb0),
    .web0(web0),
    .wmask0(wmask0),
    .addr0(addr0),
    .din0(din0),
    .dout0(dout0),

    .clk1(clk),
    .csb1(csb1),
    .addr1(addr1),
    .dout1(dout1)
);

sram_1rw1r_32_256_8_sky130 imem (
    .clk0(clk),
    .csb0(csb0),
    .web0(web0),
    .wmask0(wmask0),
    .addr0(addr0),
    .din0(din0),
    .dout0(dout0),

    .clk1(clk),
    .csb1(csb1),
    .addr1(addr1),
    .dout1(dout1)
);
    // hardware instruction/data memories go here

endmodule