$ErrorActionPreference='Stop'
$root=(Split-Path -Parent $PSScriptRoot).Replace('\','/')
$out=Join-Path $root ('results\mixed_sim_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item -Path "$root/rtl/*.mem" -Destination $out
Push-Location $out
try {
 $files=@(Get-ChildItem -LiteralPath "$root/rtl" -Filter *.sv | ForEach-Object FullName)
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv -i "$root/rtl" @files "$root/tests/tb_mixed_nodes.sv" *> compile.log
 if($LASTEXITCODE){throw 'Mixed compile failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_mixed_nodes -L xpm -s mixed_sim -debug typical -timescale 1ns/1ps *> elaborate.log
 if($LASTEXITCODE){throw 'Mixed elaboration failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' mixed_sim -tclbatch "$root/tests/run_sim.tcl" *> simulation.log
 Get-Content simulation.log -Tail 15
 if($LASTEXITCODE -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'MIXED_NODES_PHY_PASS')){throw 'Mixed simulation failed'}
 Write-Output "MIXED_SIMULATION_PASS $out"
} finally {Pop-Location}
