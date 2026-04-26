yosys
read_verilog /home/alrida_ismail/github/amb-processor/src/rtl/processor/reg_file.v
hierarchy -top moduleName  # Replace 'moduleName' with the actual name inside your .v file
proc                       # Converts behavioral code to logic gates/blocks
show