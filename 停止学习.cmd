@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apps\learn\stop.ps1"
if errorlevel 1 pause
