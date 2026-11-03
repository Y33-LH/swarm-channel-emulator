# xsct 命令 → OpenOCD 命令的桥接（供 ps7_init.tcl 使用）
proc read32 {addr} { mem2array mem32v 32 $addr 1; return $mem32v(0) }
proc mwr {args} {
    if {[lindex $args 0] eq "-force"} { set args [lrange $args 1 end] }
    mww [lindex $args 0] [lindex $args 1]
}
proc mask_write {addr mask value} {
    set cur [read32 $addr]
    mww $addr [expr {($cur & ~$mask) | ($value & $mask)}]
}
proc mask_poll {addr mask} {
    for {set i 0} {$i < 4000} {incr i} {
        if {[expr {[read32 $addr] & $mask}] == $mask} { return }
        after 1
    }
    error "mask_poll timeout at $addr"
}
# xsct 的 mrd 返回 8 位十六进制无前缀字符串（ps7_init.tcl 的 mask_poll/ps_version 依赖此格式）
proc mrd {args} { return [format "%08x" [expr {[read32 [lindex $args 0]] & 0xffffffff}]] }
