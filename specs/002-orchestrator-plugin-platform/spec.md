# Feature Specification: Orchestrator Plugin Platform Full Lifecycle Expansion

**Feature Branch**: `002-orchestrator-plugin-platform`  
**Created**: 2026-04-16  
**Status**: Complete (migrated from legacy spec format)  
**Input**: Migrated from legacy plugin platform proposal and requirements artifacts

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and manage directory-backed plugins with scoped lifecycle (Priority: P1)

As a maintainer, I want plugin directory install/refresh and scoped lifecycle controls so plugins can be managed safely across user, project, and local scopes.

**Why this priority**: Lifecycle and scoping are foundational for reliable plugin operation.

**Independent Test**: Install plugins from local directories, refresh them, and verify scoped enable/disable and scoped remove behavior.

**Acceptance Scenarios**:

1. **Given** a plugin directory containing `plugin.json`, **When** install runs, **Then** a normalized plugin record with install path, components, and hooks is persisted.
2. **Given** an installed directory-backed plugin, **When** refresh runs, **Then** hooks/integrations are rediscovered and persisted runtime state is preserved.
3. **Given** the same plugin name across multiple scopes, **When** scope-targeted enable/disable or remove runs, **Then** only the targeted scope record is affected.

---

### User Story 2 - Persist user/channel configuration and secrets with runtime substitutions (Priority: P1)

As a maintainer, I want user/channel config persistence with secret handling and runtime substitutions so plugins can safely consume configured values.

**Why this priority**: Secure configuration handling is required for production-safe plugin execution.

**Independent Test**: Set sensitive/non-sensitive config values and verify storage behavior plus `${user_config.KEY}` and `${channel_config.KEY}` substitution.

**Acceptance Scenarios**:

1. **Given** a sensitive user config key, **When** it is set, **Then** the value is stored in the secret store and redacted in normal reads.
2. **Given** configured user/channel values, **When** runtime commands or integrations include substitution tokens, **Then** resolved values are applied according to visibility rules.

---

### User Story 3 - Marketplace, integrations, and generic event execution surfaces (Priority: P2)

As a user, I want marketplace-driven install/update, plugin integration aggregation, and generic event hook execution so plugin ecosystems can be operated from CLI/runtime APIs.

**Why this priority**: These surfaces make plugins operationally useful beyond core hook translation.

**Independent Test**: Register marketplace entries, install/update marketplace plugins, list integrations, and run generic hook events.

**Acceptance Scenarios**:

1. **Given** marketplace catalog entries with plugin paths, **When** marketplace install runs, **Then** plugin records are installed with marketplace linkage metadata.
2. **Given** linked marketplace plugins, **When** update runs, **Then** current marketplace entries are resolved and metadata is refreshed.
3. **Given** enabled plugins declaring MCP/LSP/channel integrations, **When** integrations are requested, **Then** merged payloads with runtime substitutions are returned.
4. **Given** a supported event alias, **When** generic event execution runs, **Then** matching plugin hook commands execute alongside inline commands.

### Edge Cases

- Scope collisions must not overwrite records from other scopes.
- Secret and non-secret config stores must stay consistent across set/get and refresh flows.
- Marketplace update flows must tolerate missing or changed catalog entries with clear error reporting.
- Integration aggregation must not include disabled plugins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The orchestrator MUST install and refresh plugins from local directories by ingesting manifest metadata, hooks, components, and integration declarations.
- **FR-002**: The orchestrator MUST support scoped plugin lifecycle operations across `user`, `project`, and `local`.
- **FR-003**: The orchestrator MUST support plugin enabled/disabled state management per scope.
- **FR-004**: The orchestrator MUST persist plugin user/channel configuration and separate sensitive values into a dedicated secret store.
- **FR-005**: The orchestrator MUST apply `${user_config.KEY}` and `${channel_config.KEY}` substitutions at runtime.
- **FR-006**: The orchestrator MUST persist marketplace definitions and support marketplace install/update plugin flows.
- **FR-007**: The orchestrator MUST expose merged plugin integration payloads for MCP, LSP, and channels.
- **FR-008**: The orchestrator MUST support generic hook event execution for supported canonical events.
- **FR-009**: `warp-tools plugin` MUST expose lifecycle, config, marketplace, and integration actions while preserving backward-compatible legacy actions.
- **FR-010**: Unit tests MUST cover directory ingestion, scope handling, config/secrets, marketplace flows, integration aggregation, generic event execution, and CLI routing.

### Key Entities

- **Scoped Plugin Record**: Plugin state keyed by name and scope (`user|project|local`) with runtime and metadata fields.
- **Plugin Config Stores**: Split storage for non-sensitive config values and sensitive secrets.
- **Marketplace Definition**: Catalog source metadata used for install and update resolution.
- **Integration Payload**: Aggregated MCP/LSP/channel declarations derived from enabled plugin records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Directory install/refresh and scope-aware lifecycle paths are validated by passing orchestrator tests.
- **SC-002**: Sensitive config storage and runtime substitution behavior are covered by passing tests.
- **SC-003**: Marketplace install/update and integration aggregation surfaces are validated by passing tests.
- **SC-004**: CLI routing tests pass for expanded plugin lifecycle/config/marketplace/integration actions.
- **SC-005**: Runtime documentation and decision records reflect the expanded plugin platform capabilities.

## Assumptions

- Plugin directories provide valid `plugin.json` metadata and hook declarations.
- Existing plugin runtime and CLI architecture remain the integration surface for the expanded operations.
- Validation continues to rely on orchestrator and CLI unit test suites.
