@echo off
chcp 65001 > nul
echo ====================================================
echo  Persian TTS Web UI Launcher
echo ====================================================
echo در حال اجرای سرور محلی تبدیل متن به گفتار...
echo پس از بالا آمدن سرور، آدرس زیر را در مرورگر باز کنید:
echo http://127.0.0.1:8000
echo.
.\env\Scripts\python.exe scripts\server.py
pause
