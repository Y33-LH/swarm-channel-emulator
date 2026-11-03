# One invocation packages the core for Zynq, then builds the PS+PL design.
if {[catch {
set here [file dirname [file normalize [info script]]]
source "$here/board_config.wildfire7020.tcl"
if {[llength [get_parts -quiet $board_part]] != 1} {
    error "BLOCKED: Zynq-7000 device support missing ($board_part). No bitstream generated."
}
set run [file normalize "$here/../results/board_[clock format [clock seconds] -format %Y%m%d_%H%M%S]"]
set argv [list "$run/core" $board_part package_only]
set argc 3
source "$here/check_core.tcl"
# check_core defines 'here' itself; restore this entry's location.
set here [file dirname [file normalize [info script]]]
set argv [list "$here/board_config.wildfire7020.tcl" "$run/core/ip_repo" "$run/board"]
set argc 3
source "$here/build_board.tcl"
} failure options]} {
    puts stderr "BUILD_FAILED: $failure"
    exit 1
}
exit 0
