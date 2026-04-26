#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "amb-assembler.spec" ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi

PYINSTALLER="${PYINSTALLER:-.venv/bin/pyinstaller}"
if [[ ! -x "$PYINSTALLER" ]]; then
  PYINSTALLER="pyinstaller"
fi

echo "Building AMB Assembler onedir package from amb-assembler.spec..."
"$PYINSTALLER" --noconfirm --clean amb-assembler.spec
