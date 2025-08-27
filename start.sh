#!/usr/bin/env bash
set -euo pipefail

# Cross-platform builder & runner for the local Greenspace app
# - Builds static Next.js UI
# - Creates Python venv and installs FastAPI server deps
# - Packages binaries for macOS (x86_64/arm64) and Windows using PyInstaller
# - Starts the local server for the current OS

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT_DIR/greenspace-app"
SERVER_MAIN="$ROOT_DIR/local_app/main.py"

echo "==> Building Next.js static export"
pushd "$APP_DIR" >/dev/null
# Temporarily disable Next.js API routes (served by FastAPI locally)
API_DIR="$APP_DIR/src/app/api"
API_DIR_BAK="$APP_DIR/src/app/__api_disabled__"
if [[ -d "$API_DIR" ]]; then
  mv "$API_DIR" "$API_DIR_BAK"
fi
npm install
npm run export
# Restore API dir (for dev usage if needed)
if [[ -d "$API_DIR_BAK" ]]; then
  mv "$API_DIR_BAK" "$API_DIR"
fi
popd >/dev/null

echo "==> Creating Python virtual environment"
PYTHON_BIN="python3"
if [[ "${OS:-}" == "Windows_NT" ]]; then
  PYTHON_BIN="python"
fi

VENV_DIR="$ROOT_DIR/local_venv"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if [[ "${OS:-}" == "Windows_NT" ]]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/Scripts/activate"
else
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
fi

echo "==> Installing server dependencies"
pip install --upgrade pip
pip install -r "$ROOT_DIR/local_app/requirements.txt"
pip install pyinstaller

OUT_DIR="$ROOT_DIR/dist"
mkdir -p "$OUT_DIR"

echo "==> Packaging executables with PyInstaller"
# Common data files so the binary can find UI and public assets at runtime
COMMON_DATA=(
  "greenspace-app/out|greenspace-app/out"
  "greenspace-app/public|greenspace-app/public"
  "cities.json|cities.json"
)

# PyInstaller uses ':' as separator on POSIX and ';' on Windows
PYI_SEP=":"
if [[ "${OS:-}" == "Windows_NT" ]]; then
  PYI_SEP=";"
fi

DATA_ARGS=()
for d in "${COMMON_DATA[@]}"; do
  SRC="${d%%|*}"
  DST="${d##*|}"
  DATA_ARGS+=(--add-data "${SRC}${PYI_SEP}${DST}")
done

# macOS build (current arch)
echo "  -> macOS native build"
pyinstaller --noconfirm \
  --onefile \
  --name greenspace-local-mac \
  "${DATA_ARGS[@]}" \
  "$SERVER_MAIN"
mv "$ROOT_DIR/dist/greenspace-local-mac" "$OUT_DIR/" || true

# Windows build (requires running on Windows or cross-compilation toolchain)
if [[ "${OS:-}" == "Windows_NT" ]]; then
  echo "  -> Windows build"
  pyinstaller --noconfirm \
    --onefile \
    --name greenspace-local-win.exe \
    ${DATA_ARGS[@]} \
    "$SERVER_MAIN"
  mv "$ROOT_DIR/dist/greenspace-local-win.exe" "$OUT_DIR/" || true
else
  echo "  -> Skipping Windows exe (run this script on Windows to produce .exe)"
fi

echo "==> Starting local server"
if [[ -x "$OUT_DIR/greenspace-local-mac" && "$(uname)" == "Darwin" ]]; then
  "$OUT_DIR/greenspace-local-mac" &
  PID=$!
  echo "Opened server (PID $PID). URL: http://127.0.0.1:8000"
else
  # Fallback to venv python
  python "$SERVER_MAIN" &
  PID=$!
  echo "Opened server (PID $PID). URL: http://127.0.0.1:8000"
fi

sleep 1
if [[ "${OS:-}" == "Windows_NT" ]]; then
  command -v cmd.exe >/dev/null 2>&1 && cmd.exe /c start http://127.0.0.1:8000 || true
elif command -v open >/dev/null 2>&1; then
  open http://127.0.0.1:8000 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://127.0.0.1:8000 || true
fi

echo "==> Artifacts in $OUT_DIR"
echo "Done."


