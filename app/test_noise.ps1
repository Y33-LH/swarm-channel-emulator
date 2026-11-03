$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$out=Join-Path $root ('results\noise_sim_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item -Path "$root\rtl\*.mem" -Destination $out
& 'D:\miniconda\python.exe' "$root\tests\make_noise_testbench.py"
Push-Location $out
try {
 $files=@(Get-ChildItem -LiteralPath "$root\rtl" -Filter *.sv | ForEach-Object FullName)
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv -i "$root\rtl" @files "$root\tests\tb_noise_link.sv" 2>&1 | Tee-Object compile.log
 if($LASTEXITCODE -ne 0){throw 'compile failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_noise_link -L xpm -s noise_sim -debug typical -timescale 1ns/1ps 2>&1 | Tee-Object elaborate.log
 if($LASTEXITCODE -ne 0){throw 'elaboration failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' noise_sim -runall 2>&1 | Tee-Object simulation.log
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'NOISE_LINK_PASS')){throw 'Noise test failed'}
 Write-Output "NOISE_SIMULATION_PASS evidence=$out"
}finally{Pop-Location}
