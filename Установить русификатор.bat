@echo off
chcp 65001 >nul
title Русификатор Legends of Idleon
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patcher\run.ps1" install %*
echo.
if errorlevel 1 (echo Установка не удалась, сообщение об ошибке выше.) else (echo Готово. Язык переключается кнопкой в заголовке окна игры или 8-м флагом на экране выбора персонажа.)
pause
