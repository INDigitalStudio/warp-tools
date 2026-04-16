# Decisions Log
## 2026-04-16: Keep Node implementation archived while making Python+uv default
- Active runtime for `warp-tools` and `orchestrator` is Python with `uv`.
- Previous Node implementation is preserved under `archive/node-legacy` instead of being discarded.

## 2026-04-16: Preserve CLI behavior during migration
- `warp-tools` command name remains unchanged.
- Command parity is preserved for `list`, `install`, and `update`, including `--skip-install`, `--global-dir`, and activation flags.

## 2026-04-16: Keep MCP config merge compatibility
- The CLI still merges into whichever existing server map shape is present:
  - `mcpServers`
  - `mcp_servers`
  - `servers`
  - `mcp.servers`

## 2026-04-16: Add Claude plugin bridge to orchestrator hooks
- `orchestrator` can ingest Claude-style `plugin add` command lines and translate them into local plugin records.
- Plugin records are persisted to `.warp-orchestrator.plugins.json` and automatically executed by `run_preflight`/`run_postflight` when hook targets match.

## 2026-04-16: Bootstrap plugin-dev-starter as default plugin
- `orchestrator` now includes a built-in `plugin-dev-starter` plugin under `orchestrator/plugins/plugin-dev-starter`.
- Command translation supports both Claude-style `plugin add` and `plugin install` flows, with `plugin-dev` install targets automatically mapped to starter hook commands.

## 2026-04-16: Add second starter adapter and stricter install translation
- Added `github-starter` under `orchestrator/plugins/github-starter` as a concrete second adapter pattern.
- `plugin install` translation now maps known targets (`plugin-dev`, `github`) to starter hook commands and returns an explicit error for unsupported targets unless `--cmd/--command` is provided.
- Translation now supports slash/plural command variants and marketplace-first option forms such as `--source @marketplace plugin`.

## 2026-04-16: Expose plugin add/install through warp-tools CLI
- Added `warp-tools plugin add ...` and `warp-tools plugin install ...` command paths.
- Plugin commands are translated and registered by the installed `orchestrator` project, with plugin state persisted to the orchestrator plugin store.

## 2026-04-16: Plugin command supports prompt + auto-install readiness flow
- `warp-tools plugin` now checks whether `orchestrator` is installed and has a usable virtualenv before plugin registration.
- In interactive terminals, the command prompts to install/repair `orchestrator` when missing.
- In non-interactive usage, `--auto-install` can be passed to perform install/repair automatically.

## 2026-04-16: Adapt plugin and hook runtime semantics from free-code patterns
- `orchestrator` now validates richer plugin records (including `hookCommands`, `if`, `timeoutSeconds`, `once`, `async`, `statusMessage`, and `matcher`) before use.
- Install-target translation now prefers starter adapter manifests (`plugin.json`) to derive hook commands/metadata for known targets.
- Hook execution now supports condition-based skips, per-hook timeouts, async background launch, one-shot plugin removal, and JSON control output (`continue`/`stopReason`) for command hooks.
- `warp-tools plugin` now includes management commands: `list`, `remove`, and `clear` in addition to `add`/`install`.

## 2026-04-16: Expand plugin platform state and lifecycle to scoped records
- Plugin identity is now scope-aware (`name@scope`) with supported scopes `user`, `project`, and `local`.
- Lifecycle operations can target specific scope records, and enabled/disabled state is persisted per scoped plugin record.
- Plugin directory installs and refreshes ingest manifest-backed components (hooks, commands/skills/agents/output styles metadata, user config schema, MCP/LSP/channels) into normalized plugin records.

## 2026-04-16: Split sensitive plugin config and add marketplace/integration surfaces
- Sensitive user config values are persisted in `.warp-orchestrator.plugin-secrets.json`, separate from non-sensitive plugin store values.
- Marketplace definitions are persisted in `.warp-orchestrator.marketplaces.json` and can drive install/update flows through catalog entries.
- Orchestrator now exposes aggregated plugin integration payloads (MCP/LSP/channel declarations) with runtime substitution from persisted config values.
- Added a generic `run_hook_event` execution surface so plugin hooks can run on any supported event alias beyond the dedicated pre/postflight wrappers.

## 2026-04-16: Extend warp-tools plugin command routing beyond add/install/list/remove/clear
- `warp-tools plugin` now routes lifecycle/config actions (`install-dir`, `refresh`, `enable`, `disable`, `config-set`, `config-get`, `channel-config-set`).
- `warp-tools plugin` now routes integration and marketplace actions (`integrations`, `marketplace-add`, `marketplace-list`, `marketplace-install`, `marketplace-update`).
- Existing plugin command paths remain backward compatible with prior output behavior for add/install/list/remove/clear.
