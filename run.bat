@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python не найден.
    echo Сначала запустите "install.bat".
    echo.
    pause
    exit /b 1
)

%PY% -c "import customtkinter, pandas, numpy, matplotlib, scipy, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo Не все библиотеки установлены.
    echo Запустите "install.bat".
    echo.
    pause
    exit /b 1
)

%PY% "%~dp0Bioanalizator.py" %*

if errorlevel 1 (
    echo.
    echo Приложение завершилось с ошибкой.
    echo Подробности смотрите в файле bioanalizator.log
    echo.
    pause
)
