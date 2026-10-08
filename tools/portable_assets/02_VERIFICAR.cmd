@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" verify_all.py
if errorlevel 1 goto failed
echo Prueba Python correcta. Falta la revision manual en Excel.
pause
exit /b 0
:missing
echo Primero ejecutar 01_INSTALAR.cmd.
pause
exit /b 1
:failed
echo La prueba no se completo correctamente. Conservar mensajes e informes.
pause
exit /b 1
