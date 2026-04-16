# github-starter
Starter GitHub integration adapter plugin for `orchestrator`.

## Purpose
- provide a concrete second plugin adapter beyond `plugin-dev-starter`
- translate GitHub-style Claude plugin install commands into orchestrator hook commands
- run lightweight environment checks useful for future GitHub plugin flows

## Hook behavior
- script: `github_starter_hook.py`
- validates plugin store structure for GitHub-related plugin records
- checks whether current repository appears to use a GitHub remote
- prints informational notices for missing GitHub auth environment variables

## Typical translated command target
- `claude plugin install github@claude-plugins-official --scope user`
