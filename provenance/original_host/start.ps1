param([string]$PortName='COM4',[int]$HttpPort=8888,[switch]$NoBrowser,[switch]$RulesOnly)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$url="http://127.0.0.1:$HttpPort"
if(!$RulesOnly){
 try {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$root\tools\start_assistant.ps1"
  if($LASTEXITCODE -ne 0){Write-Warning 'Local assistant did not start. Rules remain available; the UI shows its actual status.'}
 } catch {Write-Warning "Local assistant unavailable: $($_.Exception.Message). Rules remain available."}
}
$already=$false
try {
 $info=Invoke-RestMethod -Uri "$url/api/info" -TimeoutSec 2
 if($info.root -ne $root){throw "Port $HttpPort belongs to another application."}
 $already=$true
} catch {
 if($_.Exception.Message -like '*belongs to another*'){throw}
}
if(!$already){
 $python='D:\miniconda\python.exe'
 if(!(Test-Path -LiteralPath $python)){throw "Python not found: $python"}
 $stamp=Get-Date -Format yyyyMMdd_HHmmss
 $stdout=Join-Path $root "results\service_$stamp.log"
 $stderr=Join-Path $root "results\service_${stamp}_error.log"
 $p=Start-Process -FilePath $python -ArgumentList @('-X','utf8','-B','tools/server.py','--port',$PortName,'--http',"$HttpPort") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 $ready=$false
 for($i=0;$i -lt 25;$i++){
  Start-Sleep -Milliseconds 400
  try{$info=Invoke-RestMethod -Uri "$url/api/info" -TimeoutSec 2;if($info.root -eq $root){$ready=$true;break}}catch{}
 }
 if(!$ready){throw "Service did not start. Read $stderr"}
}
if(!$NoBrowser){Start-Process "$url/#causal"}
Write-Host "Swarm product console: $url"
Write-Host 'Connect the board; if it was power-cycled, use Load Firmware in the UI.'
