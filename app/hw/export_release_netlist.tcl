set build [file normalize [lindex $argv 0]]
open_checkpoint "$build/board/board.runs/system_swarm_0_synth_1/system_swarm_0.dcp"
write_verilog -force -mode funcsim "$build/actual_core_netlist.v"
exit
