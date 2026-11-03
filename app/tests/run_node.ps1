$ErrorActionPreference='Stop'
$root=(Split-Path -Parent $PSScriptRoot).Replace('\','/')
$out=Join-Path $root ('results\node_sim_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $out | Out-Null
Push-Location $out
try {
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv "$root\rtl\hardware_node.sv" "$root\tests\tb_hardware_node.sv" *> compile.log
 if($LASTEXITCODE){throw 'Node compile failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_hardware_node -s node_sim -debug typical -timescale 1ns/1ps *> elaborate.log
 if($LASTEXITCODE){throw 'Node elaboration failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' node_sim -tclbatch "$root/tests/run_sim.tcl" *> simulation.log
 Get-Content simulation.log -Tail 14
 if($LASTEXITCODE -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'HARDWARE_NODE_UNIT_PASS')){throw 'Node simulation failed'}
 Write-Output "NODE_SIMULATION_PASS $out"
} finally {Pop-Location}
