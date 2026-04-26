
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.regression import TestFactory

@cocotb.test()
async def run_test(dut):
  PERIOD = 10

  dut.clk = 0
  dut.reset = 0
  dut.instr = 0
  dut.DataMemoryRead = 0


  await Timer(20*PERIOD, units='ns')
  halt = dut.halt.value
  IC = dut.IC.value
  DataAddress = dut.DataAddress.value
  DataMemoryWrite = dut.DataMemoryWrite.value
  DmemReadEn = dut.DmemReadEn.value
  DmemWriteEn = dut.DmemWriteEn.value




# Register the test.
factory = TestFactory(run_test)
factory.generate_tests()