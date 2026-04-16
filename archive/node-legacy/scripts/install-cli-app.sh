#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="$HOME/.config/warp/app"
BIN_DIR="$HOME/.local/bin"
BIN_PATH="$BIN_DIR/warp-tools"

mkdir -p "$APP_ROOT"
rm -rf "$APP_ROOT"/*

cp -R "$ROOT_DIR/cli" "$APP_ROOT/cli"
cp "$ROOT_DIR/projects.registry.json" "$APP_ROOT/projects.registry.json"
cp -R "$ROOT_DIR/mcp-orchestrator" "$APP_ROOT/mcp-orchestrator"
rm -rf "$APP_ROOT/mcp-orchestrator/node_modules"

chmod +x "$APP_ROOT/cli/warp-tools.mjs"
mkdir -p "$BIN_DIR"
ln -sfn "$APP_ROOT/cli/warp-tools.mjs" "$BIN_PATH"

echo "Installed warp-tools app files to: $APP_ROOT"
echo "Installed command symlink to: $BIN_PATH"
echo ""
echo "If needed, add ~/.local/bin to PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Try:"
echo "  warp-tools list"
