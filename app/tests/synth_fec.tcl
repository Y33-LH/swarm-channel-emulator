set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root results fec_synthesis]
file mkdir $out
cd $out
foreach f [glob $root/rtl/turbo*.mem] {file copy -force $f .}
read_verilog -sv $root/rtl/fec_decoder.sv
synth_design -top fec_decoder -part xc7z020clg400-2
create_clock -period 20 [get_ports clk]
report_utilization -file utilization.rpt
report_timing_summary -file timing.rpt
write_checkpoint -force decoder.dcp
exit
