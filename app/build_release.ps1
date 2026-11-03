param([string]$ExistingBuild='')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$python=Join-Path $root '..\runtime\python\python.exe'
$vivado=$env:SWARM_VIVADO
$xsct=$env:SWARM_XSCT
if(!$ExistingBuild){
 & $vivado -mode batch -source "$root\hw\build_verified_entry.tcl" -log "$root\results\build.log" -journal "$root\results\build.jou"
 if($LASTEXITCODE -ne 0){throw 'Vivado build failed; no release adopted'}
 $ExistingBuild=(Get-ChildItem -LiteralPath "$root\results" -Directory -Filter 'board_*' | Sort-Object Name -Descending | Select-Object -First 1).FullName
}
$build=(Resolve-Path -LiteralPath $ExistingBuild).Path
if(!$build.StartsWith((Join-Path $root 'results')+'\',[System.StringComparison]::OrdinalIgnoreCase)){throw 'Build must be under this project results folder'}
$hdf=Join-Path $build 'board\swarm.hdf'
if(!(Test-Path -LiteralPath $hdf)){throw 'Missing hardware handoff'}
$workspace=Join-Path $root 'sdk_workspace_product'
# A full hardware build always regenerates its BSP from the new handoff.
# Retain the previous SDK workspace until the fresh build succeeds.
$stamp=Get-Date -Format yyyyMMdd_HHmmss_fff
$freshWorkspace=Join-Path $root "results\sdk_rebuild_$stamp"
$sdkLog=Join-Path $root "results\sdk_rebuild_$stamp.log"
& $xsct "$root\build_sdk.tcl" $hdf $freshWorkspace *> $sdkLog
if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath $sdkLog -SimpleMatch 'SDK_BUILD_FINISHED')){throw 'SDK build failed; previous workspace retained'}
if(!(Test-Path -LiteralPath "$freshWorkspace\swarm_app\Debug\swarm_app.elf")){throw 'Fresh SDK has no executable'}
$rootAbsolute=[IO.Path]::GetFullPath($root).TrimEnd('\')+'\'
$backup=Join-Path $root "results\sdk_previous_$stamp"
foreach($target in @($workspace,$freshWorkspace,$backup)){
 if(![IO.Path]::GetFullPath($target).StartsWith($rootAbsolute,[StringComparison]::OrdinalIgnoreCase)){throw 'SDK workspace path outside project'}
}
if(Test-Path -LiteralPath $workspace){Move-Item -LiteralPath $workspace -Destination $backup}
Copy-Item -LiteralPath $freshWorkspace -Destination $workspace -Recurse
& $python "$root\tools\adopt_product_build.py" $build
if($LASTEXITCODE -ne 0){throw 'Build evidence checks failed: inspect timing, RTL and PS initialization'}
& $python "$root\tools\development_manifest.py"
if($LASTEXITCODE -ne 0){throw 'Manifest generation failed'}
Write-Output 'PRODUCT_BUILD_READY_NOT_YET_ACCEPTED: run hardware tests before declaring acceptance.'
