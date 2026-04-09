module cpu #(
    parameter
    DATA_ADDR_SPACE = 28,
    DATA_WORD_WIDTH = 28,
    REG_ADDR_WIDTH = 5,
    NUM_OF_REGS = 16,
) (
    input clk;
);
    reg_file #(
        .DATA_WORD_WIDTH(DATA_WORD_WIDTH),
        .ADDR_WIDTH(REG_ADDR_WIDTH),
        .NUM_OF_REGS(NUM_OF_REGS)
    ) reg_file_inst (
        .addr(),
        .data(),
        .write_en(),
        .out(),
        .JMPOFF(),
        .CMPA(),
        .CMPB(),
        .IC(),
        .SP(),
        .LC(),
        .SC()
    );

endmodule