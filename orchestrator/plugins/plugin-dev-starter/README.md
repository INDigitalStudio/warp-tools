# plugin-dev-starter
Starter bridge plugin for `orchestrator`, inspired by Anthropic's `plugin-dev` toolkit:
- reference: `https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev`

## Purpose
- provide a first built-in plugin entry in orchestrator
- validate orchestrator plugin store structure during hooks
- serve as a template for adding richer plugin adapters later

## Hook behavior
- single hook command file: `plugin_dev_starter_hook.py`
- invoked in both `preflight` and `postflight`
- validates `.warp-orchestrator.plugins.json` structure and registered plugin records

## Extending
- copy this folder to create new bridged plugins
- adjust parser mapping in `mcp_orchestrator.py` (`resolve_default_command_for_plugin`)
- add plugin-specific command translation and hook execution behavior
