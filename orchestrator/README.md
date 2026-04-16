# warp-orchestrator
Local MCP server to emulate:
- subagent-like task fanout (`dispatch_tasks`, `task_status`, `collect_results`)
- hook-like checks (`run_preflight`, `run_postflight`)
- Claude plugin bridge (`translate_claude_plugin`, `add_claude_plugin`, `list_plugins`, `remove_plugin_by_name`, `clear_plugins`)

## Setup
1. Install dependencies:
   - `uv sync --project /Users/ima/ws/warp/orchestrator --no-dev`
2. Warp should auto-detect `.warp/.mcp.json`.
3. Start/restart the MCP server from Warp MCP settings if needed.

## Audit
- `uv run --project /Users/ima/ws/warp/orchestrator --with pip-audit pip-audit`

## Tool overview
- `dispatch_tasks`
  - start one or more shell tasks
  - supports parallel or sequential mode
  - optional `waitForCompletion`
- `task_status`
  - inspect single task or batch status
- `collect_results`
  - summarize batch results
- `run_preflight` / `run_postflight`
  - run command sequences before/after dispatch
  - automatically includes registered plugin hook commands for that hook target
- `translate_claude_plugin`
  - parse a Claude-style `plugin add` or `plugin install` command line and return translated orchestrator plugin config
- `add_claude_plugin`
  - register translated plugin config into local plugin store
  - supports both `claude plugin add ...` and `claude plugin install ...`
  - supports slash/plural variants such as `claude /plugins add ...`
  - supports hook options such as `--if`, `--timeout`, `--once`, `--async`, `--status-message`, and `--matcher`
- `run_hook_event`
  - run any supported hook event target (not only pre/post wrappers)
  - accepts aliases such as `session_start`, `pre_tool_use`, and canonical event names
- Plugin lifecycle tools
  - `install_plugin_directory`
  - `refresh_plugin`
  - `set_plugin_enabled`
  - `list_plugins`, `remove_plugin_by_name`, `clear_plugins`
- Plugin config tools
  - `set_plugin_user_config`, `get_plugin_user_config`
  - `set_plugin_channel_config`
- Plugin integration tools
  - `list_plugin_integrations` (aggregated MCP/LSP/channel payloads)
- Marketplace tools
  - `register_marketplace`, `list_marketplaces`
  - `install_marketplace_plugin`, `update_marketplace_plugin`

## Claude plugin bridge workflow
1. Translate and/or add a plugin from a Claude plugin command line:
   - `add_claude_plugin(commandLine="claude plugin add lint --cmd true --hooks preflight")`
   - `add_claude_plugin(commandLine="claude plugin install plugin-dev@anthropics-claude-code")`
   - `add_claude_plugin(commandLine="claude plugin install --source @claude-plugins-official github --scope user")`
2. Run orchestrator hooks:
   - `run_preflight(commands=["true"])`
3. Registered plugin commands for `preflight` are executed alongside inline hook commands.
4. Optional hook controls on plugin records:
   - `if`: shell condition command checked before hook execution; non-zero exit skips the hook.
   - `timeoutSeconds`: per-hook timeout.
   - `once`: remove plugin record after one execution.
   - `async`: run plugin command in background (non-blocking).
   - hook JSON output support (`{"continue": false, "stopReason": "..."}`) to stop hook continuation.
## Plugin directory install workflow
1. Install from local plugin directory:
   - `install_plugin_directory(pluginDir=\"/path/to/plugin\", scope=\"user\")`
2. Refresh after local plugin updates:
   - `refresh_plugin(name=\"my-plugin\", scope=\"user\")`
3. Optional lifecycle and config updates:
   - `set_plugin_enabled(name=\"my-plugin\", enabled=False, scope=\"user\")`
   - `set_plugin_user_config(name=\"my-plugin\", key=\"token\", value=\"...\", sensitive=True)`
   - `set_plugin_channel_config(name=\"my-plugin\", key=\"mode\", value=\"fast\")`
4. List resolved integrations:
   - `list_plugin_integrations()`

## Built-in starter plugin
- Orchestrator includes `plugin-dev-starter` by default as the first built-in plugin.
- It is adapted from `plugin-dev` concepts and stored under:
  - `plugins/plugin-dev-starter`
- Hook command:
  - `plugins/plugin-dev-starter/plugin_dev_starter_hook.py`
- Purpose:
  - validate plugin store structure
  - serve as starter pattern for future plugin adapters

## Additional starter adapter
- Orchestrator includes a concrete GitHub adapter starter at:
  - `plugins/github-starter`
- Install command targets that map to GitHub aliases (for example `github@claude-plugins-official`) are translated to:
  - `plugins/github-starter/github_starter_hook.py`
- GitHub starter is not auto-registered by default; it is registered when a matching plugin install command is added.
- Known install targets now use adapter manifests (`plugin.json`) to derive default hook commands/metadata.

## Plugin store
- Registered plugin definitions are persisted in `.warp-orchestrator.plugins.json`.
- You can override the file path with `WARP_ORCHESTRATOR_PLUGIN_STORE`.
- Sensitive plugin config values are persisted in `.warp-orchestrator.plugin-secrets.json`.
- Marketplace definitions are persisted in `.warp-orchestrator.marketplaces.json`.
- You can override those paths with:
  - `WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE`
  - `WARP_ORCHESTRATOR_MARKETPLACE_STORE`
- From `warp-tools`, you can manage the store with:
  - `warp-tools plugin list`
  - `warp-tools plugin remove <name>`
  - `warp-tools plugin clear`
  - `warp-tools plugin install-dir <path>`
  - `warp-tools plugin refresh <name>`
  - `warp-tools plugin enable|disable <name>`
  - `warp-tools plugin config-set|config-get ...`
  - `warp-tools plugin channel-config-set ...`
  - `warp-tools plugin integrations`
  - `warp-tools plugin marketplace-add|marketplace-list|marketplace-install|marketplace-update ...`

## Notes
- This is an emulation layer, not native in-agent child process orchestration.
- Task state is in-memory for the process lifetime.
