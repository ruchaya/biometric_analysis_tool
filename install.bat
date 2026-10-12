@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo    Установка библиотек для Bioanalizator
echo ============================================
echo.

set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python не найден.
    echo Установите Python 3.10 или новее: https://www.python.org/downloads/
    echo При установке отметьте "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo Используется Python:
%PY% --version
echo.
echo Обновление pip...
%PY% -m pip install --upgrade pip
echo.
echo Установка библиотек из requirements.txt...
%PY% -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo Не удалось установить все библиотеки.
    echo Проверьте подключение к интернету и повторите попытку.
    echo.
    pause
    exit /b 1
)

echo.
echo Готово! Все библиотеки установлены.
echo Запускайте приложение файлом "run.bat".
echo.
pause
