@echo off
REM ===========================================
REM  Quiz Parser - serverlarni ishga tushirish
REM ===========================================

call .venv\Scripts\activate.bat

echo.
echo Backend ishga tushmoqda...  http://localhost:8000/docs
echo Frontend ishga tushmoqda... http://localhost:5500
echo.
echo To'xtatish uchun: Ctrl+C
echo.

REM Frontend statik serverni alohida oynada ochish
start "Quiz Parser - Frontend" cmd /k ".venv\Scripts\python.exe -m http.server 5500 --directory frontend"

REM Brauzerni ochish
timeout /t 2 /nobreak >nul
start http://localhost:5500

REM Backend shu oynada
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
