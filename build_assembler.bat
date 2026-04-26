@echo off
setlocal

if not exist "amb-assembler.spec" (
    echo Run this script from the repository root.
    exit /b 1
)

echo Building AMB Assembler onedir package from amb-assembler.spec...
python -m PyInstaller --noconfirm --clean amb-assembler.spec
exit /b %ERRORLEVEL%
