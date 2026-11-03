connect
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
stop
mwr 0xE0000000 0x128
mwr 0xE0000018 62
mwr 0xE0000034 6
mwr 0xE0000000 0x117
con
disconnect
exit
