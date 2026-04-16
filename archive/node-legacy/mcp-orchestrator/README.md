# warp-mcp-orchestrator
Local MCP server to emulate:
- subagent-like task fanout (`dispatch_tasks`, `task_status`, `collect_results`)
- hook-like checks (`run_preflight`, `run_postflight`)

## Setup
1. Install dependencies:
   - `cd /Users/ima/ws/warp/mcp-orchestrator`
   - `npm install --omit=dev`
2. Warp should auto-detect `.warp/.mcp.json`.
3. Start/restart the MCP server from Warp MCP settings if needed.

## Audit
- `npm run --prefix /Users/ima/ws/warp/mcp-orchestrator audit:bulk`
- Uses npm's Bulk Advisories endpoint (`/-/npm/v1/security/advisories/bulk`) instead of deprecated legacy audit endpoint.

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

## Notes
- This is an emulation layer, not native in-agent child process orchestration.
- Task state is in-memory for the process lifetime.
