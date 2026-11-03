@echo off
chcp 65001 >nul
title Русификатор Legends of Idleon
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patcher\run.ps1" uninstall %*
echo.
pause
