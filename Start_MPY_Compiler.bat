@echo off
echo Starting MPY Cross Compiler backend...
cd /d "%~dp0"
python mpy_compiler_backend.py
if errorlevel 1 (
    echo.
    echo FAILED to start. Make sure Python and mpy_cross are installed.
    echo Install mpy_cross: pip install mpy-cross
    pause
)
