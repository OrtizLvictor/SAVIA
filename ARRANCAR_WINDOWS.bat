@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist .venv ( %PY% -m venv .venv || goto error )
call .venv\Scripts\activate.bat || goto error
if not exist .venv\.savia_deps_installed (
  python -m pip install --disable-pip-version-check -r requirements.txt || goto error
  type nul > .venv\.savia_deps_installed
)
python iniciar.py
pause
exit /b 0
:error
echo Error iniciando SAVIA. Verifica Python 3.11-3.13 y conexion a internet.
pause
exit /b 1
