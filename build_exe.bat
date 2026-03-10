@echo off
echo.
echo =============================================
echo   Endfield Gacha Tracker - Build EXE
echo =============================================
echo.

echo [1/3] Installing packages...
pip install customtkinter pillow pyinstaller
echo.

echo [2/3] Building EXE... (1-2 min)
python -m PyInstaller --onefile --windowed --name "EndfieldGachaTracker" --hidden-import customtkinter --hidden-import PIL endfield_tracker_gui.py
echo.

echo [3/3] Done!
echo   Run: dist\EndfieldGachaTracker.exe
echo.
pause
