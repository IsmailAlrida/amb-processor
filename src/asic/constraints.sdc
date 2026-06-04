# Bare CPU timing constraints.

create_clock [get_ports clk] -name clk -period 50

set_false_path -from [get_ports reset]

set_input_delay 5 -clock clk [get_ports {instr[*] DataMemoryRead[*]}]
set_output_delay 5 -clock clk [all_outputs]
