# warp-tools

`warp-tools` is a Python-based CLI and local MCP orchestration toolkit for managing Warp subprojects and plugin-driven workflows.

## Purpose

This repository provides:

- A **project management CLI** (`warp-tools`) to install and update managed subprojects into a Warp global directory.
- A **local MCP server** (`warp-orchestrator`) that emulates task fanout and pre/post hook execution.
- A **plugin bridge** that translates Claude-style plugin commands into orchestrator-managed plugin records.

The goal is to make local Warp tool management and plugin automation reproducible, scriptable, and easy to operate.

## Main Components

- `cli/`
  - Source for the `warp-tools` command.
  - Supports project lifecycle commands (`list`, `install`, `update`).
  - Supports plugin lifecycle/config/marketplace/integration commands via the orchestrator bridge.
- `orchestrator/`
  - Source for `warp-orchestrator`, a local MCP server.
  - Provides task dispatch and hook tool surfaces.
  - Includes plugin runtime, scoped plugin records, config/secret stores, and marketplace support.
- `projects.registry.json`
  - Declares managed projects, install locations, dependency install commands, audit commands, and MCP server entries.
- `archive/node-legacy/`
  - Preserved Node implementation from earlier iterations.

## Key Capabilities

- Install/update managed projects into a global Warp directory.
- Merge MCP server entries into existing `.mcp.json` schemas.
- Translate/register Claude-style plugin commands.
- Run preflight/postflight and generic hook events with plugin hooks.
- Manage plugins by scope (`user`, `project`, `local`).
- Persist plugin config with sensitive values split into a dedicated secret store.
- Register/list/install/update marketplace-backed plugins.
- Aggregate plugin integrations (MCP, LSP, channel declarations).

## Quick Start

### Prerequisites

- Python 3.11+
- `uv`

### Install dependencies

For repository development:

- Root project:
  - `uv sync --no-dev`
- Orchestrator project:
  - `uv sync --project orchestrator --no-dev`

### Basic CLI usage

- List managed projects:
  - `warp-tools list`
- Install orchestrator:
  - `warp-tools install orchestrator`
- Update orchestrator:
  - `warp-tools update orchestrator`

### Plugin command examples

- Register a Claude-style plugin command:
  - `warp-tools plugin add -- --cmd true --hooks preflight`
- List plugins:
  - `warp-tools plugin list`
- Install from local plugin directory:
  - `warp-tools plugin install-dir /path/to/plugin --scope user`

## Repository Layout

- `cli/` — CLI implementation
- `orchestrator/` — local MCP server and plugin runtime
- `tests/` — CLI-facing tests
- `orchestrator/tests/` — orchestrator tests
- `specs/` — Speckit feature specs/tasks
- `.specify/` — Speckit workflow templates and scripts
- `archive/node-legacy/` — archived Node-era implementation

## Notes

- Current active implementation is Python + `uv`.
- Decisions and historical context are documented in `decisions.md`.
