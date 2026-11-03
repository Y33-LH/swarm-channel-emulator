if {[catch {
connect -url tcp:127.0.0.1:3121
puts [targets]
disconnect
} e]} {puts "PROBE_FAILED: $e";exit 1}
exit
