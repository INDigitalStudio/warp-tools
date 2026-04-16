#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="$HOME/.config/warp/app"
BIN_DIR="$HOME/.local/bin"
BIN_PATH="$BIN_DIR/warp-tools"
rm -rf "$APP_ROOT"
mkdir -p "$APP_ROOT"

cp "$ROOT_DIR/pyproject.toml" "$APP_ROOT/pyproject.toml"
cp "$ROOT_DIR/projects.registry.json" "$APP_ROOT/projects.registry.json"
cp -R "$ROOT_DIR/cli" "$APP_ROOT/cli"
cp -R "$ROOT_DIR/orchestrator" "$APP_ROOT/orchestrator"

rm -rf "$APP_ROOT/.venv" "$APP_ROOT/__pycache__"
rm -rf "$APP_ROOT/orchestrator/.venv" "$APP_ROOT/orchestrator/__pycache__"

uv sync --project "$APP_ROOT" --no-dev
mkdir -p "$BIN_DIR"
ln -sfn "$APP_ROOT/.venv/bin/warp-tools" "$BIN_PATH"

printf "Installed warp-tools app files to: %s\n" "$APP_ROOT"
printf "Installed command symlink to: %s\n" "$BIN_PATH"
printf "\n"
printf "If needed, add ~/.local/bin to PATH:\n"
printf "  export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
printf "\n"
printf "Try:\n"
printf "  warp-tools list\n"
