#!/usr/bin/env bash
set -euo pipefail

# Build script for macOS PyInstaller bundles.
# Usage:
#   ./build_assembler_mac.sh [onedir|onefile] [native|arm64|x86_64|universal2]
#
# Examples:
#   ./build_assembler_mac.sh
#   ./build_assembler_mac.sh onedir arm64
#   ./build_assembler_mac.sh onefile x86_64

MODE="${1:-onedir}"
ARCH="${2:-native}"

case "${MODE}" in
  onedir|onefile) ;;
  *)
    echo "Usage: ./build_assembler_mac.sh [onedir|onefile] [native|arm64|x86_64|universal2]"
    exit 1
    ;;
esac

case "${ARCH}" in
  native|arm64|x86_64|universal2) ;;
  *)
    echo "Invalid architecture: ${ARCH}"
    echo "Allowed values: native, arm64, x86_64, universal2"
    exit 1
    ;;
esac

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python not found in PATH."
  exit 1
fi

ENTRY="src/assembler/__main__.py"
APP_NAME="amb-assembler"

ARGS=(
  --noconfirm
  --clean
  --windowed
  --paths src
  --name "${APP_NAME}"
  --noupx
)

if [[ "${MODE}" == "onedir" ]]; then
  echo "Building macOS onedir bundle (recommended for faster startup)..."
  ARGS+=(--onedir)
else
  echo "Building macOS onefile bundle (portable, slower startup)..."
  ARGS+=(--onefile)
fi

if [[ "${ARCH}" != "native" ]]; then
  ARGS+=(--target-architecture "${ARCH}")
fi

# Optional bundle identifier for cleaner macOS metadata/signing flows.
if [[ -n "${BUNDLE_ID:-}" ]]; then
  ARGS+=(--osx-bundle-identifier "${BUNDLE_ID}")
fi

# Prefer .icns for macOS if available; fallback to .ico if that's all we have.
if [[ -f "assets/amb.icns" ]]; then
  ARGS+=(--icon "assets/amb.icns")
elif [[ -f "assets/amb.ico" ]]; then
  echo "Note: assets/amb.icns not found. Using assets/amb.ico as fallback."
  ARGS+=(--icon "assets/amb.ico")
else
  echo "Note: no app icon file found in assets/. Building without --icon."
fi

"${PYTHON_BIN}" -m PyInstaller "${ARGS[@]}" "${ENTRY}"

echo
echo "Build complete."
echo "Output location: dist/${APP_NAME}"
if [[ "${MODE}" == "onefile" ]]; then
  echo "Binary: dist/${APP_NAME}"
else
  echo "App bundle: dist/${APP_NAME}/${APP_NAME}.app"
fi
