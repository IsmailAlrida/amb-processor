#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "amb-assembler.spec" ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python not found in PATH." >&2
  exit 1
fi

echo "Building AMB Assembler macOS app from amb-assembler.spec..."
"${PYTHON_BIN}" -m PyInstaller --noconfirm --clean amb-assembler.spec

echo
echo "Build complete."
echo "Onedir output: dist/amb-assembler"
echo "App bundle: dist/amb-assembler.app"
