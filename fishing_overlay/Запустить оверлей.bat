@echo off
chcp 65001 >nul
title Оверлей рыбалки IdleOn
cd /d "%~dp0"
where python >nul 2>nul || (echo Нужен Python 3.9+ с python.org ^(галочка "Add python.exe to PATH" при установке^). & pause & exit /b 1)
python -c "import numpy, mss" 2>nul || python -m pip install --user -r requirements.txt || (echo Не удалось поставить numpy и mss. & pause & exit /b 1)
python overlay.py %*
pause
