@echo off
chcp 65001 > nul
title Push to GitHub
cd /d "%~dp0"
echo ====================================================
echo  Persian TTS - Push to GitHub
echo ====================================================
echo Sending commits to https://github.com/hamid-morsali-786/persian_tts ...
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [OK] Push successful! Your code is live on GitHub.
) else (
    echo [ERROR] Push failed. Please check the error message above.
)
echo.
pause
