@echo off
"%~dp0runtime\python\python.exe" -X utf8 -B "%~dp0refresh_dev.py" %*
pause
