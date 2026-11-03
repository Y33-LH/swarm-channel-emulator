if {[catch {
if {[llength $argv] != 3} {error "Expected BIT PS7_INIT ELF"}
set bit [file normalize [lindex $argv 0]]
set init [file normalize [lindex $argv 1]]
set elf [file normalize [lindex $argv 2]]
foreach path [list $bit $init $elf] {if {![file exists $path]} {error "Missing $path"}}
connect
after 2000
puts [targets]
proc stop_if_running {} {
 if {[catch {stop} reason] && ![string match {*Already stopped*} $reason]} {error $reason}
}
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
stop_if_running
rst -system
after 1000
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
stop_if_running
source $init
ps7_init
fpga -file $bit
ps7_post_config
loadhw -hw [file join [file dirname $init] system.hdf] -mem-ranges [list {0x43C00000 0x43C00FFF}]
puts "PL_VERSION_READBACK:"
puts [mrd 0x43C0003C]
set pl_version [lindex [mrd -value 0x43C0003C] 0]
set source_file [open [file join [file dirname [info script]] sw main.c] r]
set source_text [read $source_file]
close $source_file
if {![regexp {#define VERSION (0x[0-9a-fA-F]+)U} $source_text ignored expected_version]} {error "Missing firmware version contract"}
if {[expr {wide($pl_version)}] != [expr {wide($expected_version)}]} {error "Wrong PL version: $pl_version; expected $expected_version"}
dow $elf
con
after 3000
puts "PROGRAM_RUN_FINISHED"
disconnect
} failure]} {puts stderr "PROGRAM_FAILED: $failure";catch {disconnect};exit 1}
exit 0
