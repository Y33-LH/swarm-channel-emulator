& (Join-Path $PSScriptRoot "..\..\runtime\python\python.exe") -X utf8 -B (Join-Path $PSScriptRoot "..\..\launcher.py") --action ai
exit $LASTEXITCODE
