@echo off
echo.
echo =============================================
echo   Endfield Gacha Tracker - Build EXE
echo =============================================
echo.

echo [Check] Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Installing packages...
python -m pip install customtkinter pillow pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages.
    pause
    exit /b 1
)
echo.

echo [2/3] Building EXE... (1-2 min)
python -m PyInstaller --onefile --windowed --name "EndfieldGachaTracker" --hidden-import customtkinter --hidden-import PIL endfield_tracker_gui.py
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)
echo.

echo [3/3] Done!
echo   Run: dist\EndfieldGachaTracker.exe
echo.
pause

