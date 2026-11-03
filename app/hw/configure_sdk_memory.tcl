# Source-controlled memory reservation, applied to fresh and incremental builds.
# Large UART response scratch buffers live in BSS. Keep a separate 32 KiB stack
# reserve and verify its painted high-water/guard on the actual hardware.
set linker_script [file join $workspace swarm_app src lscript.ld]
set input [open $linker_script r]
set linker_text [read $input]
close $input
if {![regsub {_STACK_SIZE = DEFINED\(_STACK_SIZE\) \? _STACK_SIZE : 0x[0-9a-fA-F]+;} $linker_text {_STACK_SIZE = DEFINED(_STACK_SIZE) ? _STACK_SIZE : 0x8000;} linker_text]} {
    error "Cannot establish the source-controlled ARM stack reserve"
}
set output [open $linker_script w]
puts -nonewline $output $linker_text
close $output
puts "ARM_STACK_RESERVED_BYTES=32768"
