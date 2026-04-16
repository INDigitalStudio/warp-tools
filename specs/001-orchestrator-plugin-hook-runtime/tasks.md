# Tasks: Orchestrator Plugin Hook Runtime Expansion

**Input**: Migrated from legacy plugin hook runtime task artifacts  
**Prerequisites**: None (implementation already completed before migration)

## Phase 1: Implementation

- [x] T001 Extend plugin translation to parse and persist hook option fields.
- [x] T002 Add manifest-backed known-target resolution for install translations.
- [x] T003 Enhance hook execution to support conditional skip, timeout, async launch, one-shot cleanup, and hook JSON control output.
- [x] T004 Add plugin management actions (`list`, `remove`, `clear`) to `warp-tools plugin`.

---

## Phase 2: Testing and Documentation

- [x] T005 Update unit tests for orchestrator translation and execution behavior.
- [x] T006 Update CLI tests for plugin management command routing.
- [x] T007 Update runtime documentation and decisions log.
- [x] T008 Run root and orchestrator test suites.
