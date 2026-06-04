# amb-processor

## Building the CPU with LibreLane

This workflow assumes you're working on the repo from Ubuntu, and if you're a windows user, there is always [WSL2 Ubuntu](link/to/wsl2/ubuntu/setup) to get yourself started. 

First, be sure to have [LibreLane](link/to/librelane/docs) installed, and follow the steps to set it up.

After having done that, open a new terminal and enter the Nix development shell for LibreLane, then run the thing using the repo's ASIC config:

```bash
# If you don't have ubuntu setup, I highly recommend using it for this :)
cd /path/to/librelane
nix develop
python3 -m librelane --pdk-root /path/to/pdk-root /path/to/amb-processor/src/asic/config.yaml
```

For the outputs I [published](path/to/build/output), I used the Skywater130 process' PDK.

Some useful file links you might want to take a look at after running LibreLane:

```text
src/asic/runs/<RUN_TAG>/final/gds/cpu.gds
src/asic/runs/<RUN_TAG>/final/lef/cpu.lef
src/asic/runs/<RUN_TAG>/final/nl/cpu.nl.v
src/asic/runs/<RUN_TAG>/final/pnl/cpu.pnl.v
src/asic/runs/<RUN_TAG>/final/sdc/cpu.sdc
src/asic/runs/<RUN_TAG>/final/spice/cpu.spice
src/asic/runs/<RUN_TAG>/final/metrics.csv
```

- [The CPU's GDS output](src/asic/runs/RUN_2026-06-04_13-02-11/final/gds/cpu.gds)
- [The CPU's final metrics](src/asic/runs/RUN_2026-06-04_13-02-11/final/metrics.csv)
