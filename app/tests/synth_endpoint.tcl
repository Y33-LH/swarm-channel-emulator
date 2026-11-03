set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results endpoint_synthesis]
file mkdir $out
cd $out
foreach f [glob $root/rtl/*.mem] {file copy -force $f .}
set_property include_dirs [list $root/rtl] [current_fileset]
read_verilog -sv [glob $root/rtl/*.sv]
synth_design -top axi_minimal -part xc7z020clg400-2
create_clock -period 20 [get_ports aclk]
report_utilization -file utilization.rpt
report_timing_summary -file timing.rpt
write_checkpoint -force endpoint.dcp
exit
