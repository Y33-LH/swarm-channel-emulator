param([switch]$Program)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$buildInfo=Get-Content -LiteralPath "$root\docs\product_build.json" -Raw | ConvertFrom-Json
$sdkWorkspace=$buildInfo.sdk_workspace
if(!$sdkWorkspace -or !(Test-Path -LiteralPath "$sdkWorkspace\swarm_hw\system.hdf")){throw 'Matching SDK workspace missing; run a fresh build_sdk.tcl with ready/system.hdf first'}
& 'D:\Xilinx\SDK\2018.3\bin\xsct.bat' "$root\rebuild_firmware.tcl" "$sdkWorkspace" *> "$root\results\sdk_rebuild.log"
if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath "$root\results\sdk_rebuild.log" -SimpleMatch 'FIRMWARE_REBUILT')){throw 'Firmware build failed; read results/sdk_rebuild.log'}
& "$root\..\runtime\python\python.exe" -X utf8 -B "$root\tools\development_manifest.py" "$sdkWorkspace"
if($LASTEXITCODE -ne 0){throw 'Manifest failed'}
if($Program){
 & 'D:\Xilinx\SDK\2018.3\bin\xsct.bat' "$root\program_run.tcl" "$root\ready\system_wrapper.bit" "$root\ready\ps7_init.tcl" "$root\ready\swarm_app.elf" *> "$root\results\program_latest.log"
 if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath "$root\results\program_latest.log" -SimpleMatch 'PROGRAM_RUN_FINISHED')){throw 'Board load failed'}
}
