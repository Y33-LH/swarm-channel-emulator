$ErrorActionPreference='Stop'
$root=(Split-Path $PSScriptRoot).Replace('\','/')
$out="$root/results/post_sim"
New-Item -ItemType Directory -Path $out -Force | Out-Null
Push-Location $out
try {
 & 'D:\Xilinx\Vivado\2018.3\bin\xvlog.bat' --sv "$root/results/post_synth.v" "$root/results/tb_post.sv" 'D:/Xilinx/Vivado/2018.3/data/verilog/src/glbl.v'
 if($LASTEXITCODE -ne 0){throw 'post compile'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xelab.bat' tb_payload glbl -L unisims_ver -L unimacro_ver -L secureip -s post_check -debug typical
 if($LASTEXITCODE -ne 0){throw 'post elaborate'}
 & 'D:\Xilinx\Vivado\2018.3\bin\xsim.bat' post_check -tclbatch "$root/tests/run_sim.tcl"
}finally{Pop-Location}
