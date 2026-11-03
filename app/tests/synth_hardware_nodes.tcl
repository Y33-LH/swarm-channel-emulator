set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results node_resource_check]
file mkdir $out
cd $out
create_project -in_memory -part xc7z020clg400-2
set_param general.maxThreads 2
read_verilog -sv $root/rtl/hardware_node.sv
synth_design -top hardware_node -part xc7z020clg400-2 -mode out_of_context
create_clock -period 16 [get_ports clk]
report_utilization -file utilization.rpt
report_timing_summary -file timing.rpt
write_checkpoint -force node.dcp
exit
