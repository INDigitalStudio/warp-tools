# Tasks: Orchestrator Plugin Platform Full Lifecycle Expansion

**Input**: Migrated from legacy plugin platform task artifacts  
**Prerequisites**: None (implementation already completed before migration)

## Phase 1: Implementation

- [x] T001 Add plugin directory install and refresh flows with component ingestion helpers.
- [x] T002 Add scoped plugin lifecycle controls (enable/disable, scoped remove, scoped record resolution).
- [x] T003 Add user config and channel config persistence with sensitive value split into secret store.
- [x] T004 Add marketplace registration/list/install/update operations and metadata linkage.
- [x] T005 Add plugin integration aggregation surfaces (MCP/LSP/channels) with runtime substitution.
- [x] T006 Add generic hook event execution support and preserve pre/postflight wrappers.
- [x] T007 Expand `warp-tools plugin` CLI actions for lifecycle/config/marketplace/integration paths.

---

## Phase 2: Validation and Documentation

- [x] T008 Expand orchestrator unit tests for new plugin platform behavior.
- [x] T009 Expand CLI routing tests for new plugin command actions.
- [x] T010 Update orchestrator runtime documentation and decisions log.
- [x] T011 Run orchestrator and CLI unit test suites.
