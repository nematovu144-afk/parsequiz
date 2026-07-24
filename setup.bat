@echo off
REM ===========================================
REM  ParseQuiz - Windows setup skripti
REM  Bir marta ishga tushiring: setup.bat
REM ===========================================

echo.
echo [1/4] Virtual muhit yaratilmoqda...
python -m venv .venv
if errorlevel 1 (
    echo XATO: Python topilmadi. python.org dan Python 3.11+ o'rnating.
    pause
    exit /b 1
)

echo.
echo [2/4] Virtual muhit faollashtirilmoqda...
call .venv\Scripts\activate.bat

echo.
echo [3/4] Kutubxonalar o'rnatilmoqda...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/4] .env fayl tayyorlanmoqda...
if not exist .env (
    copy .env.example .env
    echo .env fayl yaratildi.
) else (
    echo .env fayl allaqachon mavjud.
)

echo.
echo ===========================================
echo  TAYYOR!
echo.
echo  Serverni ishga tushirish uchun:
echo     run.bat
echo.
echo  Yoki VS Code da: F5 tugmasi
echo ===========================================
pause
