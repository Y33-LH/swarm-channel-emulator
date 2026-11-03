set build [file normalize [lindex $argv 0]]
open_checkpoint "$build/board/board.runs/impl_1/system_wrapper_routed.dcp"
foreach pattern {*fec* *channel/receiver/* *channel/receiver/acquisition/* *channel/* *rx/* *tx/*} {
 set regs [get_cells -hier -filter "NAME =~ $pattern && IS_SEQUENTIAL == 1"]
 if {[llength $regs]} {
  puts "GROUP $pattern"
  report_timing -to $regs -max_paths 1 -path_type summary
 }
}
report_timing -max_paths 100 -nworst 1 -path_type summary -file "$build/critical_paths.rpt"
exit
