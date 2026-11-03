set here [file dirname [file normalize [info script]]]
set workspace [file normalize [lindex $argv 0]]
if {[catch {
setws $workspace
foreach name {transport.h link_control.h hardware_nodes.h telemetry_wire.h dedup_cache.h runtime_memory.h main.c payload_driver.c payload_driver.h network.c network.h scene.c scene.h scene_product.c channel_model.c channel_model.h terrain_model.h formation_points.h} {
 file copy -force "$here/sw/$name" "$workspace/swarm_app/src/$name"
}
source "$here/hw/configure_sdk_memory.tcl"
projects -build
if {![file exists "$workspace/swarm_app/Debug/swarm_app.elf"]} {error "ELF missing"}
puts "FIRMWARE_REBUILT"
} reason]} {puts stderr $reason;exit 1}
exit
