# Used both by fresh builds and resume after completed routing. Never relax clocks.
if {[get_property SLACK [get_timing_paths -max_paths 1]] < 0} {
    report_timing_summary -file "$out/board_timing_before_physopt.rpt"
    phys_opt_design -directive AggressiveExplore
    route_design
    write_checkpoint -force "$out/board_physopt.dcp"
}
report_timing_summary -file "$out/board_timing.rpt"
report_drc -file "$out/board_drc.rpt"
report_utilization -file "$out/board_utilization.rpt"
if {[get_property SLACK [get_timing_paths -max_paths 1]] < 0} {error "Board setup timing failed"}
if {[get_property SLACK [get_timing_paths -delay_type min -max_paths 1]] < 0} {error "Board hold timing failed"}
write_bitstream -force "$out/board.runs/impl_1/system_wrapper.bit"
write_hwdef -force -file "$out/swarm.hwdef"
write_sysdef -force -hwdef "$out/swarm.hwdef" -bitfile "$out/board.runs/impl_1/system_wrapper.bit" -file "$out/swarm.hdf"
