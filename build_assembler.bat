@echo off
setlocal

set "MODE=%~1"
if "%MODE%"=="" set "MODE=onedir"

set "ENTRY=src/assembler/__main__.py"
set "COMMON_FLAGS=--noconfirm --clean --windowed --paths src --icon assets/amb.ico --name amb-assembler --noupx"

if /I "%MODE%"=="onedir" (
    echo Building onedir package ^(recommended: faster startup^)...
    python -m PyInstaller %COMMON_FLAGS% --onedir "%ENTRY%"
    goto :eof
)

if /I "%MODE%"=="onefile" (
    echo Building onefile package ^(portable but slower startup^)...
    python -m PyInstaller %COMMON_FLAGS% --onefile "%ENTRY%"
    goto :eof
)

echo Usage: build_assembler.bat [onedir^|onefile]
exit /b 1
