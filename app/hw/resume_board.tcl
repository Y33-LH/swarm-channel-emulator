if {[catch {
set here [file dirname [file normalize [info script]]]
set out [file normalize [lindex $argv 0]]
open_project "$out/board.xpr"
open_run impl_1
source "$here/finish_board.tcl"
puts "BOARD_BUILD_FINISHED: post-route physical optimization and original timing gates."
} failure]} {puts stderr "BUILD_FAILED: $failure";exit 1}
exit 0
