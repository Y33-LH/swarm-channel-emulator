$ErrorActionPreference='Stop';$root=$PSScriptRoot;$run=Join-Path $root 'results/phy_vectors';$viv='D:\Xilinx\Vivado\2018.3\bin'
Get-ChildItem -LiteralPath (Join-Path $root 'rtl') -Filter '*.mem' | Copy-Item -Destination $run -Force
Push-Location $run
try {
 $files=@('sample_bram','fec_decoder','dbpsk_capture','phase_atan','div_u64','dbpsk_metric','phy_receiver')|ForEach-Object {"$root\rtl\$_.sv"}
 & "$viv\xvlog.bat" -sv -i "$root\rtl" @files "$root\tests\tb_phy.sv" 2>&1 | Tee-Object compile.log
 if($LASTEXITCODE -ne 0){throw 'compile failed'}
 & "$viv\xelab.bat" tb_phy -L xpm -s phy_sim -timescale 1ns/1ps -debug typical 2>&1 | Tee-Object elaborate.log
 if($LASTEXITCODE -ne 0){throw 'elaborate failed'}
 & "$viv\xsim.bat" phy_sim -runall 2>&1 | Tee-Object simulation.log
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'PHY_ALL_PASS')){throw 'PHY simulation failed'}
}finally{Pop-Location}
