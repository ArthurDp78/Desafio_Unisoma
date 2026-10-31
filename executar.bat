@echo off
setlocal
py -3.12 "%~dp0ensalamento.py"
if errorlevel 1 pause
