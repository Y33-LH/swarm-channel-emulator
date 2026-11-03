set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root results board_20261101_042658 board board.runs impl_1 system_wrapper_routed.dcp]
report_utilization -hierarchical -hierarchical_depth 7 -file [file join $root results current_hierarchy_utilization.rpt]
puts CURRENT_HIERARCHY_FINISHED
close_design
