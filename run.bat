@echo off
REM ===========================================
REM  ParseQuiz - serverni ishga tushirish
REM ===========================================
REM  Backend endi frontendni ham o'zi xizmat qiladi
REM  (bitta origin, bitta port) — alohida statik
REM  serverga ehtiyoj yo'q.

call .venv\Scripts\activate.bat

echo.
echo Server ishga tushmoqda...  http://localhost:8000
echo To'xtatish uchun: Ctrl+C
echo.

REM Server ko'tarilishi uchun bir oz kutib, brauzerni ochish
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
