@echo off
echo ========================================
echo Building Trends Application
echo ========================================

echo.
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [2/3] Building with PyInstaller...
pyinstaller trends.spec --clean --noconfirm

echo.
echo [3/3] Done!
echo.
echo Output: dist\Trends\
echo.
pause


