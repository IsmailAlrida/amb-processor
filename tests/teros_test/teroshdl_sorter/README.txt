TerosHDL demo project: Conveyor Sorter Controller

Top module: sorter_top

Hierarchy:
- sorter_top
  - debounce (x3)
  - edge_detect (x4)
  - conveyor_fsm
  - jam_detector
  - route_decoder
  - pulse_stretcher (x4)
  - item_counter
  - clock_divider
  - status_packer

Suggested TerosHDL top: sorter_top

Notes:
- item_type selects route: 00=A, 01=B, 10=C, 11=reject
- sensor_entry rising edge accepts a new item when FSM is in RUN
- jam_detector faults if sensor_entry stays high too long while motor is enabled
- diverter outputs are stretched pulses, useful for a cleaner diagram and timing paths
