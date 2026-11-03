param([switch]$Stop)
$ErrorActionPreference='Stop'
$assistantRoot='D:\digitalcircuit\local_assistant'
$pidFile=Join-Path $assistantRoot 'server_pid.txt'
$exe=Join-Path $assistantRoot 'runtime\llama-server.exe'
if(Test-Path -LiteralPath $pidFile){
 $assistantPid=[int](Get-Content -LiteralPath $pidFile)
 $process=Get-Process -Id $assistantPid -ErrorAction SilentlyContinue
 if($process -and $process.Path -eq $exe){
  if($Stop){Stop-Process -Id $assistantPid;Remove-Item -LiteralPath $pidFile;Write-Output 'ASSISTANT_STOPPED'}
  else {Write-Output 'ASSISTANT_ALREADY_RUNNING'}
  exit 0
 }
}
if($Stop){exit 0}
$model=Join-Path $assistantRoot 'Qwen3-0.6B-Q8_0.gguf'
if(!(Test-Path -LiteralPath $model) -or !(Test-Path -LiteralPath $exe)){throw 'Local model not installed. Run tools/install_local_assistant.py first.'}
$arguments=@('-m',$model,'--alias','Swarm-Qwen3-0.6B-Q8','--host','127.0.0.1','--port','8882','--threads','4','--threads-batch','4','--ctx-size','8192','--parallel','1','--reasoning','off','--no-webui')
$process=Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $assistantRoot 'server_stdout.log') -RedirectStandardError (Join-Path $assistantRoot 'server_stderr.log')
$process.Id | Set-Content -LiteralPath $pidFile
Write-Output "ASSISTANT_STARTED pid=$($process.Id) local=127.0.0.1:8882"
