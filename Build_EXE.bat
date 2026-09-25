@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Install 64-bit Python 3.13 from https://www.python.org/downloads/windows/ first.
    pause
    exit /b 1
)
py -3.13 -m venv .build_env
if errorlevel 1 goto failed
.build_env\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.0
if errorlevel 1 goto failed
.build_env\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name HERA_CSV --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 hera_csv.py
if errorlevel 1 goto failed
echo.
echo Created: %CD%\dist\HERA_CSV.exe
start "" explorer.exe /select,"%CD%\dist\HERA_CSV.exe"
pause
exit /b 0
:failed
echo.
echo Build failed. Check the error above.
pause
exit /b 1
