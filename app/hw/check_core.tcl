# Generic OOC target only, NOT a confirmed board part or board bitstream.
set here [file dirname [file normalize [info script]]]
set root [file normalize "$here/../.."]
set out [file normalize [lindex $argv 0]]
set target [lindex $argv 1]
if {$target eq ""} {set target xc7z020clg400-1}
file mkdir $out
create_project core_check "$out/project" -part $target
set_property XPM_LIBRARIES {XPM_MEMORY} [current_project]
set_param general.maxThreads 1
set_param synth.maxThreads 1
add_files [glob "$here/../rtl/*.sv" "$here/../rtl/*.vh" "$here/../rtl/*.mem"]
set_property include_dirs "$here/../rtl" [current_fileset]
set_property top axi_minimal [current_fileset]
update_compile_order -fileset sources_1
ipx::package_project -root_dir "$out/ip_repo/swarm_minimal" -vendor swarm.local -library user -taxonomy /UserIP -import_files -set_current true
set core [ipx::current_core]
set_property name swarm_minimal $core
set_property display_name {DBPSK independent PN acquisition} $core
set_property version 1.0 $core
set_property description {Independent sample-only DBPSK receiver; explicit PN acquisition baseline} $core
set_property supported_families [list [get_property FAMILY [get_parts $target]] Production] $core
ipx::infer_bus_interfaces xilinx.com:interface:aximm_rtl:1.0 $core
ipx::infer_bus_interfaces xilinx.com:signal:clock_rtl:1.0 $core
ipx::infer_bus_interfaces xilinx.com:signal:reset_rtl:1.0 $core
set axi [ipx::get_bus_interfaces -of_objects $core -filter {BUS_TYPE_VLNV == xilinx.com:interface:aximm:1.0}]
if {[llength $axi] != 1} {error "Expected one AXI interface: $axi"}
set axi_name [get_property NAME $axi]
set clk_if [ipx::get_bus_interfaces aclk -of_objects $core]
if {[llength $clk_if] != 1} {error "Clock interface not inferred"}
ipx::associate_bus_interfaces -busif $axi_name -clock aclk $core
set reset_param [ipx::add_bus_parameter ASSOCIATED_RESET $clk_if]
set_property value aresetn $reset_param
set frequency [ipx::add_bus_parameter FREQ_HZ $clk_if]
set_property value 62500000 $frequency
set protocol [ipx::add_bus_parameter PROTOCOL $axi]
set_property value AXI4LITE $protocol
set memory [ipx::get_memory_maps $axi_name -of_objects $core]
if {[llength $memory] == 0} {set memory [ipx::add_memory_map $axi_name $core]}
foreach old_block [ipx::get_address_blocks -of_objects $memory] {
 ipx::remove_address_block [get_property NAME $old_block] $memory
}
set block [ipx::add_address_block regs $memory]
set_property range 4096 $block
set_property width 32 $block
set_property usage register $block
set_property slave_memory_map_ref $axi_name $axi
ipx::create_xgui_files $core
ipx::check_integrity $core
ipx::save_core $core
if {[lindex $argv 2] ne "package_only"} {
synth_design -top axi_minimal -part $target -mode out_of_context
create_clock -name aclk -period 16.000 [get_ports aclk]
write_checkpoint "$out/core_synth.dcp"
report_utilization -file "$out/utilization_synth.rpt"
opt_design
place_design
route_design
report_timing_summary -file "$out/timing_routed.rpt"
report_utilization -file "$out/utilization_routed.rpt"
report_drc -file "$out/drc.rpt"
write_checkpoint "$out/core_routed.dcp"
set paths [get_timing_paths -max_paths 1]
if {[llength $paths] == 0} {error "No internal timing paths"}
set slack [get_property SLACK $paths]
if {$slack < 0} {error "Internal setup timing failed: $slack"}
set f [open "$out/result.txt" w]
puts $f "CORE_OOC_PASS part=$target period_ns=20 setup_slack_ns=$slack"
puts $f "Not board validation. External AXI timing and physical board configuration are not covered."
close $f
puts "CORE_OOC_PASS slack=$slack"
}
close_project
