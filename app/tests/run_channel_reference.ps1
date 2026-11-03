$ErrorActionPreference='Stop'
$root=(Split-Path -Parent $PSScriptRoot).Replace('\','/')
$out=Join-Path $root ('results/channel_reference_'+(Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item -Path "$root/rtl/*.mem" -Destination $out
Push-Location $out
try {
 $files=@(Get-ChildItem -LiteralPath "$root/rtl" -Filter *.sv | ForEach-Object FullName)
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv -i "$root/rtl" @files "$root/tests/tb_channel_model.sv" *> compile.log
 if($LASTEXITCODE){throw 'Channel reference compile failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_channel_model -L xpm -s channel_reference -debug typical -timescale 1ns/1ps *> elaborate.log
 if($LASTEXITCODE){throw 'Channel reference elaboration failed'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' channel_reference -runall *> simulation.log
 if($LASTEXITCODE -or !(Select-String -LiteralPath simulation.log -SimpleMatch 'CHANNEL_MODEL_SAMPLES')){throw 'Channel reference simulation failed'}
 & 'D:\miniconda\python.exe' -X utf8 "$root/tests/check_channel_samples.py" $out
 if($LASTEXITCODE){throw 'Channel numerical reference failed'}
} finally {Pop-Location}
