@echo off
rem fast, or the sitting named on the command line.
echo %date% %time% sitting %1
cd /d "%~dp0"
if "%~1"=="" (
  python.exe .\batches.py fast
) else (
  python.exe .\batches.py %*
)
