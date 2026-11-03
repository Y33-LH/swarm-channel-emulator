& (Join-Path $PSScriptRoot "..\runtime\python\python.exe") -X utf8 -B (Join-Path $PSScriptRoot "..\launcher.py") --action start
exit $LASTEXITCODE
