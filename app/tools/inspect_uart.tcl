connect
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
stop
puts [rrd pc]
puts [rrd r0]
puts [rrd sp]
foreach addr {0xE0000000 0xE0000004 0xE0000018 0xE000002C 0xE0000034} {puts [mrd $addr]}
puts [mrd 0xF8000154]
con
disconnect
exit
