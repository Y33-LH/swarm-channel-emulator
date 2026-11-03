@echo off
chcp 65001 >nul
"%~dp0runtime\python\python.exe" -X utf8 -B "%~dp0launcher.py" %*
if errorlevel 1 pause
