# Apparently

Really long path names can cause truncation of hexadecimal data when getting them. 

How did we find out?

unsigned apps can launch under App Translocation, which gives bundled files very long temporary paths. Older RTL runs passed on MacOS those long hex paths directly through Verilog plusargs, which could truncate `program.hex` or `data.hex` paths and leave instruction/data memory partially loaded or zeroed. The runner now stages RTL hex inputs into `~/.amb-processor/rtl_sim/...` before simulation. Future RTL cleanup can widen or replace the fixed-size Verilog path buffers, but staging should remain for portable packaged runs.
