@echo off
chcp 65001 > nul
echo ====================================================
echo  Persian TTS Web UI Launcher
echo ====================================================
echo در حال اجرای سرور محلی تبدیل متن به گفتار...
echo مرورگر وب به صورت خودکار باز خواهد شد:
echo http://127.0.0.1:8000
echo.
start /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
.\env\Scripts\python.exe scripts\server.py
pause
