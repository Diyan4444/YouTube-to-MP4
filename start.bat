@echo off
setlocal enabledelayedexpansion
title StreamVault - YouTube to MP4 ^& MP3 Media Utility

:: Guarantee execution from the directory where start.bat resides
cd /d "%~dp0"

:: Guarantee execution from the directory where start.bat resides
cd /d "%~dp0"

echo =====================================================================
echo  StreamVault - YouTube to MP4 ^& MP3 Local Media Utility
echo =====================================================================
echo [*] Root Directory: %CD%
echo.

:: 1. Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [WARNING] Virtual environment not found in %CD%\venv.
    echo Please run 'install.bat' first to install required dependencies.
    echo.
    set /p run_install="Would you like to run install.bat now? (Y/N): "
    if /i "!run_install!"=="Y" (
        call install.bat
        if !errorlevel! neq 0 (
            echo.
            echo [ERROR] Installation failed with exit code !errorlevel!.
            echo StreamVault cannot start until dependencies are installed properly.
            pause
            exit /b !errorlevel!
        )
        if not exist "venv\Scripts\python.exe" (
            echo.
            echo [ERROR] Virtual environment installation was not completed.
            echo Please run install.bat directly to resolve any setup issues.
            pause
            exit /b 1
        )
    ) else (
        exit /b 1
    )
)

:: 2. Activate virtual environment
call "venv\Scripts\activate.bat"

:: 3. Launch Application on port 3000
echo [*] Starting StreamVault on http://localhost:3000 ...
echo [*] Press Ctrl+C in this terminal window to stop the application.
echo.

python "backend\app.py"

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Application exited with code %errorlevel%.
    pause
)
