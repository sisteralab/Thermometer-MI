@echo off
setlocal

if "%1"=="" (
    exit /b
) else (
    set "Tag=%1"
)

pyinstaller main.py -n "Therometer-MI_%Tag%" --console --onefile