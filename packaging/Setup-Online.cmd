@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0Install.ps1" -Mode Online
exit /b %errorlevel%
