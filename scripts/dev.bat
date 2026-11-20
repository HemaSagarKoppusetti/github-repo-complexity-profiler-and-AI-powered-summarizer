@echo off
REM Double-click launcher for the development environment
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0dev.ps1"
pause
