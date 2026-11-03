$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$run=Join-Path $root 'results/fec_vectors'
$viv='D:\Xilinx\Vivado\2018.3\bin'
Get-ChildItem -LiteralPath (Join-Path $root 'rtl') -Filter 'turbo*.mem' | Copy-Item -Destination $run -Force
Push-Location $run
try {
 & "$viv\xvlog.bat" -sv "$root\rtl\fec_encoder.sv" "$root\rtl\fec_decoder.sv" "$root\tests\tb_fec.sv" 2>&1 | Tee-Object compile.log
 if($LASTEXITCODE -ne 0){throw 'FEC compile failed'}
 & "$viv\xelab.bat" tb_fec -s fec_sim -timescale 1ns/1ps 2>&1 | Tee-Object elaborate.log
 if($LASTEXITCODE -ne 0){throw 'FEC elaborate failed'}
 & "$viv\xsim.bat" fec_sim -runall 2>&1 | Tee-Object simulation.log
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'FEC_ALL_PASS cases=16')){throw 'FEC simulation did not pass'}
}finally{Pop-Location}
