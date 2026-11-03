$ErrorActionPreference = 'Stop'
$root=$PSScriptRoot.Replace('\','/')
$out=Join-Path $root ('results\sim_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item -Path "$root\rtl\*.mem" -Destination $out
Copy-Item -Path "$root\reference\receiver_*.mem" -Destination $out
Push-Location $out
try {
 $files=@(Get-ChildItem -LiteralPath "$root\rtl" -Filter *.sv | ForEach-Object FullName)
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv -i "$root\rtl" @files "$root\tests\tb_payload.sv" "$root\tests\tb_independent_rx.sv" 2>&1 | Tee-Object compile.log
 if($LASTEXITCODE -ne 0){throw 'xvlog failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_payload -L xpm -s payload_sim -debug typical -timescale 1ns/1ps 2>&1 | Tee-Object elaborate.log
 if($LASTEXITCODE -ne 0){throw 'xelab failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' payload_sim -tclbatch "$root/tests/run_sim.tcl" 2>&1 | Tee-Object simulation.log
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath simulation.log -Pattern '^PAYLOAD_AXI_PASS')){throw 'simulation did not pass'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_independent_rx -L xpm -s independent_rx -debug typical -timescale 1ns/1ps 2>&1 | Tee-Object independent_elaborate.log
 if($LASTEXITCODE -ne 0){throw 'independent RX elaborate failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' independent_rx -tclbatch "$root/tests/run_sim.tcl" 2>&1 | Tee-Object independent_simulation.log
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath independent_simulation.log -Pattern '^INDEPENDENT_RX_PASS')){throw 'independent RX simulation did not pass'}
 Write-Output "SIMULATION_PASS evidence=$out"
} finally {Pop-Location}


