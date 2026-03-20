@echo off
title Batch Zicon Generator
echo ============================================
echo  Batch Zicon Generator - Source Edition
echo ============================================
echo.

:: Check if Electron is already installed
if exist "node_modules\electron\dist\electron.exe" (
    echo Electron is already installed. Starting app...
    echo.
    "node_modules\electron\dist\electron.exe" .
    goto :end
)

:: Check if npm is available
where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js / npm not found!
    echo Please install Node.js from https://nodejs.org
    echo Then run this batch file again.
    pause
    goto :end
)

echo Installing dependencies (first run only)...
echo This may take a few minutes...
echo.
npm install --save-dev electron@28
if errorlevel 1 (
    echo.
    echo ERROR: npm install failed. Check your internet connection.
    pause
    goto :end
)

echo.
echo Starting Batch Zicon Generator...
echo.
npm start

:end
pause
