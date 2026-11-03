set here [file dirname [file normalize [info script]]]
set hdf [file normalize [lindex $argv 0]]
set workspace [file normalize [lindex $argv 1]]
if {[catch {
setws $workspace
createhw -name swarm_hw -hwspec $hdf
createbsp -name swarm_bsp -hwproject swarm_hw -proc ps7_cortexa9_0 -os standalone
createapp -name swarm_app -hwproject swarm_hw -proc ps7_cortexa9_0 -bsp swarm_bsp -app {Empty Application} -lang C
foreach name {transport.h link_control.h hardware_nodes.h telemetry_wire.h dedup_cache.h runtime_memory.h main.c payload_driver.c payload_driver.h network.c network.h scene.c scene.h scene_product.c channel_model.c channel_model.h terrain_model.h formation_points.h} {
 file copy -force "$here/sw/$name" "$workspace/swarm_app/src/$name"
}
configapp -app swarm_app -add libraries m
configapp -app swarm_app compiler-optimization {Optimize more (-O2)}
source "$here/hw/configure_sdk_memory.tcl"
projects -build
if {![file exists "$workspace/swarm_app/Debug/swarm_app.elf"]} {error "SDK did not produce ELF; inspect compiler diagnostics"}
puts "SDK_BUILD_FINISHED"
} failure]} {puts "SDK_BUILD_FAILED: $failure"; exit 1}
exit
