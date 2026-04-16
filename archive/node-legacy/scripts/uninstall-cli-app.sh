#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$HOME/.config/warp/app"
BIN_PATH="$HOME/.local/bin/warp-tools"

rm -rf "$APP_ROOT"
rm -f "$BIN_PATH"

echo "Removed app directory: $APP_ROOT"
echo "Removed command symlink: $BIN_PATH"
