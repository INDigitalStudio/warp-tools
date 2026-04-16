# Feature Specification: Orchestrator Plugin Hook Runtime Expansion

**Feature Branch**: `001-orchestrator-plugin-hook-runtime`  
**Created**: 2026-04-16  
**Status**: Complete (migrated from legacy spec format)  
**Input**: Migrated from legacy plugin hook runtime proposal and requirements artifacts

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Runtime hook controls for plugin execution (Priority: P1)

As a maintainer, I want plugin hooks to support runtime controls such as conditional execution, timeout, one-shot behavior, async execution, and stop signals so automated workflows remain safe and deterministic.

**Why this priority**: This is the core runtime behavior that governs correctness and safety of plugin-driven orchestration.

**Independent Test**: Run hook execution with plugins configured for `if`, `timeout`, `once`, and hook JSON control output, and verify execution reports and store updates.

**Acceptance Scenarios**:

1. **Given** a plugin with an `if` condition command that exits non-zero, **When** hook execution runs, **Then** that plugin hook is skipped and reported as skipped.
2. **Given** a plugin with `once: true`, **When** hook execution completes for that plugin, **Then** the plugin is removed from the store and listed as removed.
3. **Given** a plugin command that emits hook JSON with `{\"continue\": false}`, **When** hook execution processes the output, **Then** the run is marked as stopped with the emitted stop reason.

---

### User Story 2 - Manifest-backed translation for known plugin install targets (Priority: P2)

As a maintainer, I want known install targets to use built-in adapter manifests so translated plugin records contain default hook mappings and metadata without manual setup.

**Why this priority**: This reduces configuration overhead and aligns runtime behavior with known plugin adapters.

**Independent Test**: Translate a known install target and verify the resulting plugin record includes manifest-derived commands and adapter metadata.

**Acceptance Scenarios**:

1. **Given** a known install target such as `github@claude-plugins-official`, **When** translation runs, **Then** mapped hook commands and adapter identity metadata are included in the plugin record.

---

### User Story 3 - CLI plugin store management commands (Priority: P2)

As a user, I want direct `warp-tools plugin` management commands so I can inspect and manage plugin records without editing store files manually.

**Why this priority**: This provides operational usability for installed plugin records.

**Independent Test**: Run `warp-tools plugin list`, `warp-tools plugin remove <name>`, and `warp-tools plugin clear` against a populated store.

**Acceptance Scenarios**:

1. **Given** installed plugin records, **When** `warp-tools plugin list` runs, **Then** structured plugin information is returned from orchestrator.
2. **Given** a plugin name, **When** `warp-tools plugin remove <name>` runs, **Then** the named record is removed and reported.
3. **Given** existing plugin records, **When** `warp-tools plugin clear` runs, **Then** the store is emptied and confirmation is returned.

### Edge Cases

- Condition command failures and timeout expirations must not crash the orchestrator run loop.
- Async hook execution and one-shot removal must not produce duplicate removals.
- Hook JSON control output parsing must tolerate malformed output and preserve reporting.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The translator MUST derive default hook command mappings and adapter metadata from built-in plugin manifests for known install targets.
- **FR-002**: The runtime MUST support conditional hook execution via plugin `if` commands.
- **FR-003**: The runtime MUST support per-hook timeout handling and surface timeout outcomes in execution reports.
- **FR-004**: The runtime MUST support one-shot plugin execution (`once: true`) with post-run plugin removal.
- **FR-005**: The runtime MUST support asynchronous hook command launch when configured.
- **FR-006**: The runtime MUST interpret hook JSON continuation controls and stop execution when `continue` is explicitly false.
- **FR-007**: `warp-tools` MUST expose plugin store management actions for list, remove, and clear.
- **FR-008**: Unit tests MUST cover translation, runtime controls, and CLI routing behavior for this feature surface.

### Key Entities

- **Plugin Record**: Persisted plugin definition containing command mappings, hook settings, and metadata.
- **Adapter Manifest**: Built-in manifest data used to resolve defaults for known install targets.
- **Hook Execution Result**: Per-run structured report containing execution outcomes, skipped steps, and stop/timeout context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Translation of known install targets consistently returns manifest-derived command mappings and adapter metadata in unit tests.
- **SC-002**: Runtime control paths (`if`, `timeout`, `once`, async, JSON continuation) are validated with passing tests.
- **SC-003**: Plugin management CLI actions (`list`, `remove`, `clear`) route successfully through orchestrator in CLI tests.
- **SC-004**: Documentation and decisions are updated to reflect runtime control and translation behavior.

## Assumptions

- Built-in adapter manifests remain the source of truth for known plugin install target defaults.
- Existing orchestrator plugin store and CLI architecture remain stable while adding these controls.
- Validation relies on existing orchestrator and CLI unit test suites.
