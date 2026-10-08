@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" menu.py
if errorlevel 1 echo El proceso no se completo. Conservar el mensaje de error.
pause
exit /b
:missing
echo Primero ejecutar 01_INSTALAR.cmd.
pause
exit /b 1
