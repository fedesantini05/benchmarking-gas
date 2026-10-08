@echo off
setlocal
cd /d "%~dp0"
echo Preparando Python 3.12 para este paquete...
py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12)"
if errorlevel 1 goto missing
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --no-index --find-links wheels -r requirements.txt
if errorlevel 1 goto failed
echo Instalacion terminada. Abrir 02_VERIFICAR.cmd.
pause
exit /b 0
:missing
echo Instalar Python 3.12 con el launcher de Windows y volver a ejecutar.
echo Alternativa desde terminal: python -m venv .venv
echo Luego: .venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
pause
exit /b 1
:failed
echo La instalacion no se completo. Copiar el mensaje de error para revisarlo.
pause
exit /b 1
