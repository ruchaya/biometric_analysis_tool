# Build the application into a single exe with PyInstaller.
# Run:  powershell -ExecutionPolicy Bypass -File .\exe\build.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$here = $PSScriptRoot
$icon = Join-Path $root "assets\bioanalizator.ico"
$logo = Join-Path $root "assets\bioanalizator.png"
$versionFile = Join-Path $root "assets\version_info.txt"

py -m pip install --quiet pyinstaller | Out-Null

py -m PyInstaller --noconfirm --clean --onefile --windowed --name Bioanalizator `
    --icon "$icon" `
    --version-file "$versionFile" `
    --add-data "$icon;assets" `
    --add-data "$logo;assets" `
    --distpath "$here\dist" --workpath "$here\build" --specpath "$here" `
    --collect-all customtkinter `
    --hidden-import openpyxl --hidden-import xlrd `
    --hidden-import pandas.io.excel._openpyxl --hidden-import pandas.io.excel._xlrd `
    --exclude-module torch --exclude-module torchvision --exclude-module torchaudio `
    --exclude-module functorch --exclude-module torchgen --exclude-module triton `
    "$root\main.py"

Write-Host ""
Write-Host "Done: $here\dist\Bioanalizator.exe"
