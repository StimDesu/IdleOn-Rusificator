@echo off
rem Steam launch options:  "<path to this file>" %%command%%
rem Re-applies the translation after game updates, then starts the game.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0patcherun.ps1" ensure -Game "%~1"
start "" %*
