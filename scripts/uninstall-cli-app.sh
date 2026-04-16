#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="$HOME/.config/warp/app"
BIN_PATH="$HOME/.local/bin/warp-tools"

rm -rf "$APP_ROOT"
rm -f "$BIN_PATH"
printf "Removed app directory: %s\n" "$APP_ROOT"
printf "Removed command symlink: %s\n" "$BIN_PATH"
