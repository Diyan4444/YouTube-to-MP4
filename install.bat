@echo off
setlocal enabledelayedexpansion
title StreamVault - Centralized Dependency Installer

:: Guarantee execution from the directory where install.bat resides
cd /d "%~dp0"

echo =====================================================================
echo  StreamVault - Automated Dependency Installation
echo =====================================================================
echo [*] Installation Directory: %CD%
echo.

:: ---------------------------------------------------------------------
:: 1. CHECK PYTHON
:: ---------------------------------------------------------------------
echo [CHECK] Python runtime...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [MISSING] Python is not installed or not in PATH.
    echo [*] Attempting to install Python via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    where python >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Automatic installation of Python failed.
        echo Please manually install Python 3.10+ from: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo [INSTALLED] Python installed successfully.
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [FOUND] %%i
)

:: ---------------------------------------------------------------------
:: 2. CHECK NODE.JS
:: ---------------------------------------------------------------------
echo.
echo [CHECK] Node.js runtime...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [MISSING] Node.js is not installed or not in PATH.
    echo [*] Installing Node.js via winget...
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    where node >nul 2>&1
    if !errorlevel! neq 0 (
        echo [WARNING] Automatic installation of Node.js failed.
        echo Node.js is recommended for yt-dlp challenge solving.
        echo You can manually install it later from: https://nodejs.org/
    ) else (
        echo [INSTALLED] Node.js installed successfully.
    )
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo [FOUND] Node.js %%i
)

:: ---------------------------------------------------------------------
:: 3. CHECK FFMPEG & FFPROBE
:: ---------------------------------------------------------------------
echo.
echo [CHECK] FFmpeg media tools...
set "FFMPEG_FOUND=0"
set "FFPROBE_FOUND=0"

where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    set "FFMPEG_FOUND=1"
    for /f "delims=" %%i in ('where ffmpeg 2^>^&1') do (
        echo [FOUND] FFmpeg executable: %%i
        goto :after_ffmpeg_where
    )
)
:after_ffmpeg_where

where ffprobe >nul 2>&1
if %errorlevel% equ 0 (
    set "FFPROBE_FOUND=1"
    for /f "delims=" %%i in ('where ffprobe 2^>^&1') do (
        echo [FOUND] FFprobe executable: %%i
        goto :after_ffprobe_where
    )
)
:after_ffprobe_where

if "!FFMPEG_FOUND!"=="1" if "!FFPROBE_FOUND!"=="1" (
    echo [OK] FFmpeg and FFprobe media tools are fully accessible.
    goto :after_ffmpeg_check
)

if "!FFMPEG_FOUND!"=="0" (
    echo [MISSING] FFmpeg was not detected in PATH.
)
if "!FFPROBE_FOUND!"=="0" (
    echo [MISSING] FFprobe was not detected in PATH.
)

echo [*] Attempting to install FFmpeg via winget...
winget install Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements

:: Re-verify accessibility after winget attempt
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    set "FFMPEG_FOUND=1"
)
where ffprobe >nul 2>&1
if %errorlevel% equ 0 (
    set "FFPROBE_FOUND=1"
)

if "!FFMPEG_FOUND!"=="1" if "!FFPROBE_FOUND!"=="1" (
    echo [INSTALLED] FFmpeg and FFprobe installed successfully via winget.
) else (
    echo [WARNING] FFmpeg and/or FFprobe are still not accessible.
    echo Audio extraction to MP3 and 1080p+ video merging require FFmpeg and FFprobe.
    echo Please download FFmpeg and add its bin folder to your PATH from:
    echo https://ffmpeg.org/download.html
)

:after_ffmpeg_check

:: ---------------------------------------------------------------------
:: 4. SETUP VIRTUAL ENVIRONMENT & PYTHON DEPENDENCIES
:: ---------------------------------------------------------------------
echo.
echo [CHECK] Python virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating virtual environment in .\venv ...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [CREATED] Virtual environment created.
) else (
    echo [FOUND] Existing virtual environment detected.
)

echo.
echo [*] Checking and installing Python dependencies...
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install -r "backend\requirements.txt"

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies from backend\requirements.txt.
    pause
    exit /b 1
)

echo [SUCCESS] Python dependencies verified and ready.
echo.
echo =====================================================================
echo  Installation complete. You can now start the application by running:
echo  start.bat
echo =====================================================================
echo.
