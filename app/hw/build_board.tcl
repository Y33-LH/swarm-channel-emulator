# vivado -mode batch -source build_board.tcl -tclargs CONFIG IP_REPO OUTPUT
# Requires confirmed board config and Zynq device support. Not run on a board yet.
if {$argc != 3} {error "Expected CONFIG IP_REPO OUTPUT"}
set config [file normalize [lindex $argv 0]]
set repo [file normalize [lindex $argv 1]]
set out [file normalize [lindex $argv 2]]
source $config
if {![info exists board_verified] || !$board_verified || $board_part eq "" || $board_revision eq "" || $board_source eq "" || [dict size $ps7_properties]==0} {
 error "Board not verified. Supply exact part/revision/source and vendor PS7 properties."
}
if {[llength [get_parts -quiet $board_part]] != 1} {error "Device support missing: $board_part"}
if {[file exists "$out/board.xpr"]} {error "Use a new output directory; do not overwrite an existing board project"}
create_project board $out -part $board_part
set_property XPM_LIBRARIES {XPM_MEMORY} [current_project]
set_property ip_repo_paths $repo [current_project]
update_ip_catalog
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
set_property -dict $ps7_properties $ps
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 CONFIG.PCW_EN_CLK0_PORT 1 CONFIG.PCW_EN_RST0_PORT 1 CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 62.500000] $ps
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
if {[llength [get_bd_intf_pins -quiet ps7/DDR]]} {make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]}
create_bd_cell -type ip -vlnv swarm.local:user:swarm_minimal:1.0 swarm
set sc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 axi_bridge]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] $sc
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset_sync
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] [get_bd_cells one]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] [get_bd_cells zero]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins axi_bridge/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_bridge/M00_AXI] [get_bd_intf_pins swarm/s_axi]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/M_AXI_GP0_ACLK] [get_bd_pins axi_bridge/aclk] [get_bd_pins reset_sync/slowest_sync_clk] [get_bd_pins swarm/aclk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins reset_sync/ext_reset_in]
connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset_sync/dcm_locked] [get_bd_pins swarm/accept_enable] [get_bd_pins reset_sync/aux_reset_in]
connect_bd_net [get_bd_pins zero/dout] [get_bd_pins reset_sync/mb_debug_sys_rst]
connect_bd_net [get_bd_pins reset_sync/peripheral_aresetn] [get_bd_pins axi_bridge/aresetn] [get_bd_pins swarm/aresetn]
assign_bd_address -offset 0x43C00000 -range 4K -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs swarm/s_axi/regs]
validate_bd_design
puts "RESET_POLARITY=[get_property CONFIG.C_EXT_RESET_HIGH [get_bd_cells reset_sync]]"
if {[get_property CONFIG.C_AUX_RESET_HIGH [get_bd_cells reset_sync]] != 0} {error "Aux reset tied high requires active-low polarity"}
save_bd_design
generate_target all [get_files system.bd]
set wrapper [make_wrapper -files [get_files system.bd] -top]
add_files -norecurse $wrapper
# Extend the generated top while keeping PS/DDR names, IP address map and SDK export.
set lcd_dir [file dirname [file normalize [info script]]]
set w [open $wrapper r]; set wrapper_text [read $w]; close $w
set ports {lcd_ref,tft_clk,tft_de,tft_bl,hsync,vsync,rgb_tft,}
regsub {module system_wrapper[[:space:]]*\(} $wrapper_text "module system_wrapper (\n$ports" wrapper_text
set decl {input lcd_ref; output tft_clk,tft_de,tft_bl,hsync,vsync; output [15:0] rgb_tft;
  lcd_800 panel(.lcd_ref(lcd_ref),.tft_clk(tft_clk),.tft_de(tft_de),.tft_bl(tft_bl),.hsync(hsync),.vsync(vsync),.rgb_tft(rgb_tft));}
regsub {\);[[:space:]]*input} $wrapper_text ");\n$decl\ninput" wrapper_text
if {[string first "lcd_800 panel" $wrapper_text]<0} {
 # Some versions declare DDR ports as inout first.
 regsub {\);[[:space:]]*inout} $wrapper_text ");\n$decl\ninout" wrapper_text
}
if {[string first "lcd_800 panel" $wrapper_text]<0 || [string first $ports $wrapper_text]<0} {error "LCD top-level connection failed"}
set w [open $wrapper w]; puts -nonewline $w $wrapper_text; close $w
add_files -norecurse [list "$lcd_dir/lcd_800.v" "$lcd_dir/lcd_banner.mem"]
add_files -fileset constrs_1 -norecurse "$lcd_dir/lcd_800.xdc"
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
if {[info exists ::env(SWARM_REFERENCE_DCP)] && [file isfile $::env(SWARM_REFERENCE_DCP)]} {
 set_property INCREMENTAL_CHECKPOINT [file normalize $::env(SWARM_REFERENCE_DCP)] [get_runs impl_1]
}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation incomplete"}
open_run impl_1
source [file join [file dirname [info script]] finish_board.tcl]
puts "BOARD_BUILD_FINISHED: inspect all timing/DRC reports before hardware testing. No hardware test performed."

