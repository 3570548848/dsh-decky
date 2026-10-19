#!/usr/bin/env bash
#
# Build and package the plugin as a Decky-installable ZIP.
#
# Layout requirement (this is not cosmetic — read decky-loader's
# backend/decky_loader/browser.py):
#
#   for f in plugin_zip.namelist():
#       if f.endswith("/plugin.json") and f.count("/") == 1:
#
# The archive must contain EXACTLY ONE top-level directory holding plugin.json
# at depth 1, because the installer does `ZipFile(...).extractall(plugin_path)`
# straight into ~/homebrew/plugins/. Without that wrapper directory, files would
# be dumped loose into the plugins root and the plugin would never load.
#
# Dev-only files (src/, tsconfig.json, tests/, node_modules/) are deliberately
# excluded: Decky only loads plugin.json, package.json, main.py and dist/.
#
# Usage:  ./package.sh            # builds dist/, then writes ../dsh-decky.zip
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR_NAME="dsh-decky"
OUT_ZIP="$(dirname "$HERE")/${PLUGIN_DIR_NAME}.zip"

# 1. Frontend must exist: a Decky plugin without dist/index.js loads an empty
#    panel (the frontend entry the loader imports is dist/index.js).
if [ ! -f "$HERE/dist/index.js" ]; then
  echo "!! dist/index.js is missing. Build it first:  pnpm install && pnpm run build" >&2
  echo "   (@decky/rollup needs a Linux x64 host for its native rollup binary.)" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

PKG="$STAGE/$PLUGIN_DIR_NAME"
mkdir -p "$PKG/py_modules" "$PKG/dist"

# Runtime files only.
cp "$HERE/plugin.json" "$PKG/plugin.json"
cp "$HERE/package.json" "$PKG/package.json"
cp "$HERE/main.py" "$PKG/main.py"
cp "$HERE/dist/index.js" "$PKG/dist/index.js"
[ -f "$HERE/py_modules/.keep" ] && cp "$HERE/py_modules/.keep" "$PKG/py_modules/.keep" || true

rm -f "$OUT_ZIP"
( cd "$STAGE" && zip -qr "$OUT_ZIP" "$PLUGIN_DIR_NAME" )

echo "Built $OUT_ZIP"
unzip -l "$OUT_ZIP"
