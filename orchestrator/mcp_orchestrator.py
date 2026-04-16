from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP


@dataclass
class TaskRecord:
    id: str
    batchId: str
    name: str
    command: str
    cwd: str
    env: dict[str, str]
    status: str = "queued"
    startedAt: str | None = None
    endedAt: str | None = None
    exitCode: int | None = None
    signal: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


TASKS: dict[str, TaskRecord] = {}
BATCHES: dict[str, list[str]] = {}
BACKGROUND_JOBS: set[asyncio.Task[Any]] = set()
SUPPORTED_PLUGIN_SCOPES = ("user", "project", "local")
SUPPORTED_HOOK_TARGETS = (
    "preflight",
    "postflight",
    "pretooluse",
    "posttooluse",
    "posttoolusefailure",
    "permissiondenied",
    "notification",
    "userpromptsubmit",
    "sessionstart",
    "sessionend",
    "stop",
    "stopfailure",
    "subagentstart",
    "subagentstop",
    "precompact",
    "postcompact",
    "permissionrequest",
    "setup",
    "teammateidle",
    "taskcreated",
    "taskcompleted",
    "elicitation",
    "elicitationresult",
    "configchange",
    "worktreecreate",
    "worktreeremove",
    "instructionsloaded",
    "cwdchanged",
    "filechanged",
)
DEFAULT_HOOK_TARGETS = list(SUPPORTED_HOOK_TARGETS)
HOOK_TARGET_ALIASES = {
    "pre": "preflight",
    "preflight": "preflight",
    "post": "postflight",
    "postflight": "postflight",
}
HOOK_TARGET_ALIASES.update({name: name for name in SUPPORTED_HOOK_TARGETS})
HOOK_TARGET_ALIASES.update(
    {
        "pretooluse": "pretooluse",
        "posttooluse": "posttooluse",
        "posttoolusefailure": "posttoolusefailure",
        "permissiondenied": "permissiondenied",
        "userpromptsubmit": "userpromptsubmit",
        "sessionstart": "sessionstart",
        "sessionend": "sessionend",
        "stopfailure": "stopfailure",
        "subagentstart": "subagentstart",
        "subagentstop": "subagentstop",
        "precompact": "precompact",
        "postcompact": "postcompact",
        "permissionrequest": "permissionrequest",
        "teammateidle": "teammateidle",
        "taskcreated": "taskcreated",
        "taskcompleted": "taskcompleted",
        "elicitationresult": "elicitationresult",
        "configchange": "configchange",
        "worktreecreate": "worktreecreate",
        "worktreeremove": "worktreeremove",
        "instructionsloaded": "instructionsloaded",
        "cwdchanged": "cwdchanged",
        "filechanged": "filechanged",
        "pre_tool_use": "pretooluse",
        "post_tool_use": "posttooluse",
        "post_tool_use_failure": "posttoolusefailure",
        "permission_denied": "permissiondenied",
        "user_prompt_submit": "userpromptsubmit",
        "session_start": "sessionstart",
        "session_end": "sessionend",
        "stop_failure": "stopfailure",
        "subagent_start": "subagentstart",
        "subagent_stop": "subagentstop",
        "pre_compact": "precompact",
        "post_compact": "postcompact",
        "permission_request": "permissionrequest",
        "teammate_idle": "teammateidle",
        "task_created": "taskcreated",
        "task_completed": "taskcompleted",
        "elicitation_result": "elicitationresult",
        "config_change": "configchange",
        "worktree_create": "worktreecreate",
        "worktree_remove": "worktreeremove",
        "instructions_loaded": "instructionsloaded",
        "cwd_changed": "cwdchanged",
        "file_changed": "filechanged",
        "pretooluse": "pretooluse",
        "posttooluse": "posttooluse",
        "posttoolusefailure": "posttoolusefailure",
        "permissiondenied": "permissiondenied",
        "userpromptsubmit": "userpromptsubmit",
        "sessionstart": "sessionstart",
        "sessionend": "sessionend",
        "subagentstart": "subagentstart",
        "subagentstop": "subagentstop",
    }
)
ORCHESTRATOR_ROOT = Path(__file__).resolve().parent
ORCHESTRATOR_DATA_ROOT = ORCHESTRATOR_ROOT / ".warp-orchestrator-data"
PLUGIN_DEV_REFERENCE_URL = (
    "https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev"
)
GITHUB_PLUGIN_REFERENCE_URL = "https://docs.anthropic.com/en/discover-plugins"
PLUGIN_DEV_STARTER_NAME = "plugin-dev-starter"
PLUGIN_DEV_STARTER_HOOK_SCRIPT = (
    ORCHESTRATOR_ROOT / "plugins" / "plugin-dev-starter" / "plugin_dev_starter_hook.py"
)
GITHUB_STARTER_NAME = "github-starter"
GITHUB_STARTER_HOOK_SCRIPT = (
    ORCHESTRATOR_ROOT / "plugins" / "github-starter" / "github_starter_hook.py"
)
PLUGIN_DEV_ALIASES = {
    "plugin-dev",
    "plugin_dev",
    "plugin-dev-toolkit",
    PLUGIN_DEV_STARTER_NAME,
}
GITHUB_PLUGIN_ALIASES = {
    "github",
    "github-plugin",
    "github-integration",
    GITHUB_STARTER_NAME,
}
IGNORED_PLUGIN_OPTIONS_WITH_VALUE = {
    "--marketplace",
    "--plugin-dir",
    "--plugin",
    "--source",
}
IGNORED_PLUGIN_OPTIONS_NO_VALUE = {
    "--yes",
    "-y",
    "--force",
    "--project",
    "--user",
    "--local",
    "--global",
}
HOOK_CONFIG_OPTIONS_WITH_VALUE = {
    "--if",
    "--timeout",
    "--status-message",
    "--matcher",
}
HOOK_CONFIG_OPTIONS_NO_VALUE = {
    "--once",
    "--async",
    "--async-rewake",
}
PLUGIN_VARIABLE_PATTERN = re.compile(r"\$\{CLAUDE_PLUGIN_(ROOT|DATA)\}")
USER_CONFIG_PATTERN = re.compile(r"\$\{user_config\.([^}]+)\}")
CHANNEL_CONFIG_PATTERN = re.compile(r"\$\{channel_config\.([^}]+)\}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_plugin_dev_starter_command(plugin_target: str | None = None) -> str:
    target = plugin_target or "plugin-dev@anthropics/claude-code"
    return shlex.join(
        [
            "python3",
            str(PLUGIN_DEV_STARTER_HOOK_SCRIPT),
            "--plugin-target",
            target,
        ]
    )


def default_github_starter_command(plugin_target: str | None = None) -> str:
    target = plugin_target or "github@claude-plugins-official"
    return shlex.join(
        [
            "python3",
            str(GITHUB_STARTER_HOOK_SCRIPT),
            "--plugin-target",
            target,
        ]
    )


def plugin_reference_url(plugin_name: str) -> str | None:
    normalized = plugin_name.strip().lower()
    if normalized in PLUGIN_DEV_ALIASES:
        return PLUGIN_DEV_REFERENCE_URL
    if normalized in GITHUB_PLUGIN_ALIASES:
        return GITHUB_PLUGIN_REFERENCE_URL
    return None


def adapter_directory_for_plugin(plugin_name: str | None) -> str | None:
    normalized = (plugin_name or "").strip().lower()
    if normalized in PLUGIN_DEV_ALIASES:
        return "plugin-dev-starter"
    if normalized in GITHUB_PLUGIN_ALIASES:
        return "github-starter"
    return None


def resolve_manifest_command(command: str, plugin_root: Path) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return command

    resolved_tokens: list[str] = []
    for token in tokens:
        candidate = plugin_root / token
        if not Path(token).is_absolute() and candidate.exists():
            resolved_tokens.append(str(candidate))
        else:
            resolved_tokens.append(token)
    return shlex.join(resolved_tokens)


def resolve_manifest_hook_commands(
    manifest_payload: dict[str, Any],
    plugin_root: Path,
) -> dict[str, str]:
    raw_hooks = manifest_payload.get("orchestrator_hooks")
    if not isinstance(raw_hooks, dict):
        return {}

    hook_commands: dict[str, str] = {}
    for raw_target, config in raw_hooks.items():
        alias = HOOK_TARGET_ALIASES.get(str(raw_target).strip().lower())
        if not alias:
            continue
        if not isinstance(config, dict):
            continue
        raw_command = config.get("command")
        if not isinstance(raw_command, str) or not raw_command.strip():
            continue
        hook_commands[alias] = resolve_manifest_command(
            raw_command.strip(), plugin_root
        )
    return hook_commands


def order_hook_targets(hook_commands: dict[str, str]) -> list[str]:
    ordered: list[str] = []
    for target in DEFAULT_HOOK_TARGETS:
        if target in hook_commands:
            ordered.append(target)
    for target in hook_commands:
        if target not in ordered:
            ordered.append(target)
    return ordered or list(DEFAULT_HOOK_TARGETS)


def default_hook_commands_for_plugin(
    *,
    plugin_name: str,
    plugin_target: str | None,
) -> dict[str, str]:
    normalized = plugin_name.strip().lower()
    if normalized in PLUGIN_DEV_ALIASES:
        command = default_plugin_dev_starter_command(plugin_target)
    elif normalized in GITHUB_PLUGIN_ALIASES:
        command = default_github_starter_command(plugin_target)
    else:
        return {}

    return {target: command for target in DEFAULT_HOOK_TARGETS}


def load_builtin_plugin_translation(
    *,
    plugin_name: str,
    plugin_target: str | None,
) -> dict[str, Any] | None:
    adapter_dir = adapter_directory_for_plugin(plugin_name)
    if not adapter_dir:
        return None

    plugin_root = ORCHESTRATOR_ROOT / "plugins" / adapter_dir
    manifest_path = plugin_root / "plugin.json"

    manifest_payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                manifest_payload = parsed
        except (OSError, json.JSONDecodeError):
            manifest_payload = {}

    hook_commands = resolve_manifest_hook_commands(manifest_payload, plugin_root)
    if not hook_commands:
        hook_commands = default_hook_commands_for_plugin(
            plugin_name=plugin_name,
            plugin_target=plugin_target,
        )

    if not hook_commands:
        return None

    hook_targets = order_hook_targets(hook_commands)
    command = hook_commands.get(hook_targets[0]) or next(iter(hook_commands.values()))

    reference_url = plugin_reference_url(plugin_name)
    manifest_reference = manifest_payload.get("reference_url")
    if isinstance(manifest_reference, str) and manifest_reference.strip():
        reference_url = manifest_reference.strip()

    metadata: dict[str, Any] = {
        "adapterId": adapter_dir,
        "pluginRoot": str(plugin_root),
        "manifestPath": str(manifest_path),
    }
    if reference_url:
        metadata["referenceUrl"] = reference_url

    return {
        "command": command,
        "hookCommands": hook_commands,
        "hookTargets": hook_targets,
        "metadata": metadata,
    }


def default_plugin_records() -> dict[str, dict[str, Any]]:
    timestamp = now_iso()
    default_translation = load_builtin_plugin_translation(
        plugin_name=PLUGIN_DEV_STARTER_NAME,
        plugin_target="plugin-dev@anthropics/claude-code",
    )

    default_command = default_plugin_dev_starter_command(
        "plugin-dev@anthropics/claude-code",
    )
    hook_commands = (
        default_translation.get("hookCommands", {})
        if isinstance(default_translation, dict)
        else {}
    )
    if not hook_commands:
        hook_commands = {target: default_command for target in DEFAULT_HOOK_TARGETS}
    hook_targets = order_hook_targets(hook_commands)
    command = hook_commands.get(hook_targets[0], default_command)

    metadata: dict[str, Any] = {
        "originPlugin": "plugin-dev",
        "referenceUrl": PLUGIN_DEV_REFERENCE_URL,
        "starter": True,
    }
    if isinstance(default_translation, dict):
        translated_metadata = default_translation.get("metadata")
        if isinstance(translated_metadata, dict):
            metadata.update(translated_metadata)
    default_scope = "user"
    record_key = plugin_record_key(PLUGIN_DEV_STARTER_NAME, default_scope)
    return {
        record_key: {
            "id": record_key,
            "name": PLUGIN_DEV_STARTER_NAME,
            "scope": default_scope,
            "enabled": True,
            "command": command,
            "hookCommands": hook_commands,
            "hookTargets": hook_targets,
            "source": "orchestrator-default",
            "sourceType": "builtin",
            "version": "0.1.0",
            "sourceCommandLine": "builtin:plugin-dev-starter",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "metadata": metadata,
        },
    }


def ensure_default_plugins(payload: dict[str, Any]) -> bool:
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        payload["plugins"] = {}
        plugins = payload["plugins"]

    changed = False
    for key, record in default_plugin_records().items():
        name = str(record.get("name", "")).strip()
        scope = str(record.get("scope", "user")).strip().lower()
        legacy_key = name
        scoped_key = plugin_record_key(name, scope)
        if legacy_key in plugins and scoped_key not in plugins:
            legacy = plugins.pop(legacy_key)
            if isinstance(legacy, dict):
                legacy = dict(legacy)
                legacy["name"] = name or legacy.get("name", "")
                legacy["scope"] = scope
                legacy["id"] = scoped_key
                plugins[scoped_key] = legacy
                changed = True
        if key not in plugins:
            plugins[key] = record
            changed = True
    return changed


def plugin_store_path() -> Path:
    configured = os.environ.get(
        "WARP_ORCHESTRATOR_PLUGIN_STORE",
        ".warp-orchestrator.plugins.json",
    )
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def plugin_secret_store_path() -> Path:
    configured = os.environ.get(
        "WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE",
        ".warp-orchestrator.plugin-secrets.json",
    )
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def marketplace_store_path() -> Path:
    configured = os.environ.get(
        "WARP_ORCHESTRATOR_MARKETPLACE_STORE",
        ".warp-orchestrator.marketplaces.json",
    )
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def load_plugin_store() -> dict[str, Any]:
    path = plugin_store_path()
    if not path.exists():
        payload = {"plugins": {}}
        if ensure_default_plugins(payload):
            save_plugin_store(payload)
        return payload

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"plugins": {}}
        if ensure_default_plugins(payload):
            save_plugin_store(payload)
        return payload

    if not isinstance(payload, dict):
        payload = {"plugins": {}}
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        payload["plugins"] = {}
    if ensure_default_plugins(payload):
        save_plugin_store(payload)
    return payload


def save_plugin_store(payload: dict[str, Any]) -> None:
    path = plugin_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def load_plugin_secret_store() -> dict[str, Any]:
    path = plugin_secret_store_path()
    if not path.exists():
        return {"plugins": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"plugins": {}}
    if not isinstance(payload, dict):
        return {"plugins": {}}
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        payload["plugins"] = {}
    return payload


def save_plugin_secret_store(payload: dict[str, Any]) -> None:
    path = plugin_secret_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def load_marketplace_store() -> dict[str, Any]:
    path = marketplace_store_path()
    if not path.exists():
        return {"marketplaces": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"marketplaces": {}}
    if not isinstance(payload, dict):
        return {"marketplaces": {}}
    marketplaces = payload.get("marketplaces")
    if not isinstance(marketplaces, dict):
        payload["marketplaces"] = {}
    return payload


def save_marketplace_store(payload: dict[str, Any]) -> None:
    path = marketplace_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def list_marketplaces_state() -> list[dict[str, Any]]:
    payload = load_marketplace_store()
    marketplaces = payload.get("marketplaces", {})
    if not isinstance(marketplaces, dict):
        return []
    records: list[dict[str, Any]] = []
    for name, value in marketplaces.items():
        if not isinstance(value, dict):
            continue
        record = dict(value)
        record_name = str(record.get("name", name)).strip()
        if not record_name:
            continue
        record["name"] = record_name
        if not isinstance(record.get("plugins"), dict):
            record["plugins"] = {}
        if not isinstance(record.get("metadata"), dict):
            record["metadata"] = {}
        records.append(record)
    records.sort(key=lambda item: str(item.get("name", "")))
    return records


def upsert_marketplace_state(
    *,
    name: str,
    url: str,
    catalog_path: str | None,
    plugins: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    overwrite: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    marketplace_name = str(name).strip()
    if not marketplace_name:
        return None, "Marketplace name is required."
    marketplace_url = str(url).strip()
    if not marketplace_url:
        return None, "Marketplace url is required."

    payload = load_marketplace_store()
    marketplaces = payload.get("marketplaces")
    if not isinstance(marketplaces, dict):
        marketplaces = {}
        payload["marketplaces"] = marketplaces

    existing = marketplaces.get(marketplace_name)
    if existing is not None and not overwrite:
        return None, f"Marketplace '{marketplace_name}' already exists."

    now = now_iso()
    created_at = now
    if isinstance(existing, dict):
        created_at = str(existing.get("createdAt", now))
    normalized_plugins = dict(plugins) if isinstance(plugins, dict) else {}
    normalized_metadata = dict(metadata) if isinstance(metadata, dict) else {}

    record: dict[str, Any] = {
        "name": marketplace_name,
        "url": marketplace_url,
        "plugins": normalized_plugins,
        "metadata": normalized_metadata,
        "createdAt": created_at,
        "updatedAt": now,
    }
    if catalog_path:
        record["catalogPath"] = str(Path(catalog_path).expanduser())
    marketplaces[marketplace_name] = record
    save_marketplace_store(payload)
    return record, None


def read_marketplace_catalog_plugins(record: dict[str, Any]) -> dict[str, Any]:
    direct_plugins = record.get("plugins")
    if isinstance(direct_plugins, dict) and direct_plugins:
        return dict(direct_plugins)

    catalog_path = record.get("catalogPath")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        return {}
    catalog = read_json_file(Path(catalog_path).expanduser())
    if not isinstance(catalog, dict):
        return {}
    plugins = catalog.get("plugins")
    if not isinstance(plugins, dict):
        return {}
    return dict(plugins)


def resolve_marketplace_plugin(
    *,
    marketplace_name: str,
    plugin_name: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    marketplaces = {item["name"]: item for item in list_marketplaces_state()}
    marketplace = marketplaces.get(marketplace_name)
    if not marketplace:
        return None, None, f"Marketplace '{marketplace_name}' not found."
    catalog_plugins = read_marketplace_catalog_plugins(marketplace)
    entry = catalog_plugins.get(plugin_name)
    if not isinstance(entry, dict):
        return (
            marketplace,
            None,
            (
                f"Plugin '{plugin_name}' is not registered in marketplace '{marketplace_name}'."
            ),
        )
    return marketplace, entry, None


def install_plugin_from_marketplace_state(
    *,
    marketplace_name: str,
    plugin_name: str,
    scope: str,
    overwrite: bool,
    enabled: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    marketplace, entry, resolve_error = resolve_marketplace_plugin(
        marketplace_name=marketplace_name,
        plugin_name=plugin_name,
    )
    if resolve_error or marketplace is None or entry is None:
        return None, resolve_error or "Marketplace entry not found."
    plugin_path = entry.get("path")
    if not isinstance(plugin_path, str) or not plugin_path.strip():
        return None, (
            f"Marketplace entry for '{plugin_name}' in '{marketplace_name}' has no plugin path."
        )
    source = f"marketplace:{marketplace_name}"
    record, install_error = install_plugin_from_directory_state(
        plugin_dir=plugin_path,
        scope=scope,
        enabled=enabled,
        overwrite=overwrite,
        source=source,
    )
    if install_error or record is None:
        return None, install_error or "Failed to install plugin from marketplace."
    store = load_plugin_store()
    plugins = store.get("plugins")
    if not isinstance(plugins, dict):
        return None, "Plugin store is invalid."
    record_key = str(record.get("id", ""))
    stored_record = plugins.get(record_key)
    if not isinstance(stored_record, dict):
        return None, "Installed plugin record was not persisted."
    metadata = stored_record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata["marketplace"] = marketplace_name
    metadata["marketplacePlugin"] = plugin_name
    metadata["marketplaceUrl"] = str(marketplace.get("url", ""))
    stored_record["metadata"] = metadata
    entry_version = entry.get("version")
    if entry_version is not None:
        stored_record["version"] = entry_version
    stored_record["sourceType"] = "marketplace"
    stored_record["updatedAt"] = now_iso()
    normalized, normalize_error = normalize_plugin_record(
        str(stored_record.get("name", plugin_name)),
        stored_record,
    )
    if normalize_error or normalized is None:
        return None, normalize_error or "Marketplace plugin payload became invalid."
    plugins[record_key] = normalized
    save_plugin_store(store)
    return normalized, None


def update_plugin_from_marketplace_state(
    *,
    name: str,
    scope: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, record, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or record is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None, f"Plugin '{name}' is not linked to a marketplace."
    marketplace_name = metadata.get("marketplace")
    marketplace_plugin_name = metadata.get("marketplacePlugin") or name
    if not isinstance(marketplace_name, str) or not marketplace_name.strip():
        return None, f"Plugin '{name}' is not linked to a marketplace."
    updated_record, install_error = install_plugin_from_marketplace_state(
        marketplace_name=marketplace_name,
        plugin_name=str(marketplace_plugin_name),
        scope=str(record.get("scope", "user")),
        overwrite=True,
        enabled=bool(record.get("enabled", True)),
    )
    if install_error or updated_record is None:
        return None, install_error or "Failed to update plugin from marketplace."
    return updated_record, None


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return slug or "plugin"


def canonical_scope(scope: str | None) -> tuple[str | None, str | None]:
    raw = (scope or "user").strip().lower()
    if raw in {"default", "global"}:
        raw = "user"
    if raw not in SUPPORTED_PLUGIN_SCOPES:
        return None, (
            f"Unsupported scope '{scope}'. Expected one of: "
            f"{', '.join(SUPPORTED_PLUGIN_SCOPES)}."
        )
    return raw, None


def plugin_record_key(name: str, scope: str) -> str:
    return f"{name.strip()}@{scope.strip().lower()}"


def split_plugin_record_key(record_key: str) -> tuple[str, str]:
    if "@" not in record_key:
        return record_key, "user"
    name, scope = record_key.rsplit("@", 1)
    return name, scope


def canonical_hook_target(target: str | None) -> str | None:
    if target is None:
        return None
    normalized = str(target).strip().lower().replace("-", "").replace("_", "")
    if not normalized:
        return None
    return HOOK_TARGET_ALIASES.get(normalized)


def plugin_data_directory(record: dict[str, Any]) -> Path:
    scope = str(record.get("scope", "user"))
    name = str(record.get("name", "plugin"))
    record_id = str(record.get("id", plugin_record_key(name, scope)))
    path = ORCHESTRATOR_DATA_ROOT / safe_slug(record_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def plugin_root_from_record(record: dict[str, Any]) -> Path | None:
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        root = metadata.get("pluginRoot")
        if isinstance(root, str) and root.strip():
            candidate = Path(root).expanduser()
            if candidate.exists():
                return candidate
    install_path = record.get("installPath")
    if isinstance(install_path, str) and install_path.strip():
        candidate = Path(install_path).expanduser()
        if candidate.exists():
            return candidate
    return None


def list_plugin_records() -> list[tuple[str, dict[str, Any]]]:
    store = load_plugin_store()
    plugins = store.get("plugins", {})
    if not isinstance(plugins, dict):
        return []
    records: list[tuple[str, dict[str, Any]]] = []
    for raw_key, raw_value in plugins.items():
        key = str(raw_key)
        if not isinstance(raw_value, dict):
            continue
        value = dict(raw_value)
        name = str(value.get("name", "")).strip()
        scope, _ = canonical_scope(str(value.get("scope", "user")))
        if not name:
            name, key_scope = split_plugin_record_key(key)
            scope = scope or key_scope
            value["name"] = name
        if not scope:
            scope = "user"
        value["scope"] = scope
        normalized_key = plugin_record_key(name, scope)
        value["id"] = normalized_key
        records.append((normalized_key, value))
    return records


def find_plugin_record(
    name: str,
    scope: str | None = None,
) -> tuple[str, dict[str, Any]] | None:
    canonical_requested_scope: str | None = None
    if scope is not None:
        canonical_requested_scope, _ = canonical_scope(scope)
    matches: list[tuple[str, dict[str, Any]]] = []
    for key, value in list_plugin_records():
        if str(value.get("name", "")).strip() != name:
            continue
        if (
            canonical_requested_scope
            and str(value.get("scope")) != canonical_requested_scope
        ):
            continue
        matches.append((key, value))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0]


def matching_plugin_records(name: str) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for key, value in list_plugin_records():
        if str(value.get("name", "")).strip() == name:
            matches.append((key, value))
    matches.sort(key=lambda item: item[0])
    return matches


def resolve_plugin_record(
    *,
    name: str,
    scope: str | None = None,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    if scope is not None:
        canonical, scope_error = canonical_scope(scope)
        if scope_error or canonical is None:
            return None, None, scope_error or "Invalid scope."
        found = find_plugin_record(name, canonical)
        if not found:
            return None, None, f"Plugin '{name}' not found for scope '{canonical}'."
        return found[0], found[1], None

    matches = matching_plugin_records(name)
    if not matches:
        return None, None, f"Plugin '{name}' not found."
    if len(matches) > 1:
        available_scopes = sorted(
            {str(record.get("scope", "user")) for _, record in matches}
        )
        return (
            None,
            None,
            (
                f"Plugin '{name}' exists in multiple scopes "
                f"({', '.join(available_scopes)}). Specify scope explicitly."
            ),
        )
    return matches[0][0], matches[0][1], None


def load_secret_values_for_record(record_key: str) -> dict[str, str]:
    payload = load_plugin_secret_store()
    plugins = payload.get("plugins", {})
    if not isinstance(plugins, dict):
        return {}
    values = plugins.get(record_key, {})
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in values.items():
        normalized[str(key)] = str(value)
    return normalized


def save_secret_values_for_record(record_key: str, values: dict[str, str]) -> None:
    payload = load_plugin_secret_store()
    plugins = payload.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        payload["plugins"] = plugins
    if values:
        plugins[record_key] = {str(key): str(value) for key, value in values.items()}
    else:
        plugins.pop(record_key, None)
    save_plugin_secret_store(payload)


def read_json_file(file_path: Path) -> dict[str, Any] | None:
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    marker = "\n---\n"
    end = content.find(marker, 4)
    if end == -1:
        return {}, content
    frontmatter_raw = content[4:end]
    body = content[end + len(marker) :]
    frontmatter: dict[str, str] = {}
    for line in frontmatter_raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip("'").strip('"')
        if clean_key:
            frontmatter[clean_key] = clean_value
    return frontmatter, body


def markdown_description(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        return stripped
    return fallback


def unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen:
            continue
        if not path.exists():
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def manifest_component_paths(
    plugin_root: Path,
    manifest: dict[str, Any],
    key: str,
) -> list[Path]:
    raw = manifest.get(key)
    if raw is None:
        return []
    values: list[str] = []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = [str(item) for item in raw]
    else:
        return []
    resolved: list[Path] = []
    for value in values:
        if not value.strip():
            continue
        candidate = (plugin_root / value).resolve()
        try:
            candidate.relative_to(plugin_root.resolve())
        except ValueError:
            continue
        resolved.append(candidate)
    return unique_existing_paths(resolved)


def collect_markdown_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".md":
        return [root]
    if not root.is_dir():
        return []
    results: list[Path] = []
    for candidate in root.rglob("*.md"):
        if candidate.is_file():
            results.append(candidate)
    return sorted(results)


def collect_skill_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.name.lower() == "skill.md":
        return [root]
    if root.is_dir():
        direct = root / "SKILL.md"
        if direct.exists():
            return [direct]
        skill_files: list[Path] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            skill = child / "SKILL.md"
            if skill.exists():
                skill_files.append(skill)
        return skill_files
    return []


def namespaced_component_name(
    plugin_name: str,
    component_file: Path,
    base_dir: Path,
    *,
    skill_mode: bool = False,
) -> str:
    if skill_mode and component_file.name.lower() == "skill.md":
        base_name = component_file.parent.name
        namespace_root = component_file.parent.parent
    else:
        base_name = component_file.stem
        namespace_root = component_file.parent
    try:
        relative_namespace = namespace_root.relative_to(base_dir)
    except ValueError:
        relative_namespace = Path()
    namespace_parts = [
        part for part in relative_namespace.parts if part and part != "."
    ]
    if namespace_parts:
        return ":".join([plugin_name, *namespace_parts, base_name])
    return f"{plugin_name}:{base_name}"


def load_markdown_components(
    *,
    plugin_name: str,
    component_paths: list[Path],
    component_type: str,
    skill_mode: bool = False,
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for root in component_paths:
        files = (
            collect_skill_files(root) if skill_mode else collect_markdown_files(root)
        )
        for file_path in files:
            try:
                raw_content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            frontmatter, markdown_content = parse_frontmatter(raw_content)
            description = frontmatter.get("description") or markdown_description(
                markdown_content,
                f"{component_type} from {plugin_name}",
            )
            loaded.append(
                {
                    "type": component_type,
                    "name": namespaced_component_name(
                        plugin_name,
                        file_path,
                        root if root.is_dir() else root.parent,
                        skill_mode=skill_mode,
                    ),
                    "path": str(file_path),
                    "description": description,
                    "frontmatter": frontmatter,
                    "content": markdown_content.strip(),
                }
            )
    return loaded


def normalize_event_name(value: str) -> str | None:
    return canonical_hook_target(value)


def load_event_hooks_from_payload(
    payload: dict[str, Any],
    plugin_root: Path,
) -> list[dict[str, Any]]:
    event_hooks: list[dict[str, Any]] = []
    hooks_payload = payload.get("hooks")
    if not isinstance(hooks_payload, dict):
        return event_hooks
    for raw_event, matcher_items in hooks_payload.items():
        event_name = normalize_event_name(str(raw_event))
        if not event_name:
            continue
        if not isinstance(matcher_items, list):
            continue
        for matcher_item in matcher_items:
            if not isinstance(matcher_item, dict):
                continue
            matcher = str(matcher_item.get("matcher", "*")).strip() or "*"
            hooks = matcher_item.get("hooks")
            if not isinstance(hooks, list):
                continue
            for hook in hooks:
                if not isinstance(hook, dict):
                    continue
                if str(hook.get("type", "")).strip().lower() != "command":
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or not command.strip():
                    continue
                event_hooks.append(
                    {
                        "event": event_name,
                        "matcher": matcher,
                        "command": resolve_manifest_command(
                            command.strip(), plugin_root
                        ),
                        "timeoutSeconds": hook.get("timeoutSeconds"),
                    }
                )
    return event_hooks


def load_hook_components(
    plugin_root: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    hook_commands = resolve_manifest_hook_commands(manifest, plugin_root)
    event_hooks: list[dict[str, Any]] = []

    hooks_path = plugin_root / "hooks" / "hooks.json"
    hooks_payload = read_json_file(hooks_path)
    if hooks_payload:
        event_hooks.extend(load_event_hooks_from_payload(hooks_payload, plugin_root))

    extra_hooks = manifest.get("hooks")
    extra_hook_values: list[str] = []
    if isinstance(extra_hooks, str):
        extra_hook_values = [extra_hooks]
    elif isinstance(extra_hooks, list):
        extra_hook_values = [
            str(item) for item in extra_hooks if isinstance(item, (str, Path))
        ]
    for extra_hook in extra_hook_values:
        hook_file = (plugin_root / extra_hook).resolve()
        try:
            hook_file.relative_to(plugin_root.resolve())
        except ValueError:
            continue
        payload = read_json_file(hook_file)
        if payload:
            event_hooks.extend(load_event_hooks_from_payload(payload, plugin_root))

    for event_hook in event_hooks:
        event = str(event_hook.get("event", "")).strip()
        command = event_hook.get("command")
        if (
            event
            and isinstance(command, str)
            and command.strip()
            and event not in hook_commands
        ):
            hook_commands[event] = command.strip()

    return hook_commands, event_hooks


def load_json_server_spec(spec: Any, plugin_root: Path) -> dict[str, Any]:
    if isinstance(spec, dict):
        return dict(spec)
    if isinstance(spec, str):
        path = (plugin_root / spec).resolve()
        try:
            path.relative_to(plugin_root.resolve())
        except ValueError:
            return {}
        payload = read_json_file(path)
        if not isinstance(payload, dict):
            return {}
        return payload
    return {}


def load_mcp_servers(manifest: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    raw = manifest.get("mcpServers")
    if raw is None:
        return {}
    merged: dict[str, Any] = {}
    values: list[Any]
    if isinstance(raw, list):
        values = raw
    else:
        values = [raw]
    for value in values:
        payload = load_json_server_spec(value, plugin_root)
        servers = (
            payload.get("mcpServers")
            if isinstance(payload.get("mcpServers"), dict)
            else payload
        )
        if isinstance(servers, dict):
            merged.update(servers)
    return merged


def load_lsp_servers(manifest: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    raw = manifest.get("lspServers")
    if raw is None:
        return {}
    merged: dict[str, Any] = {}
    values: list[Any]
    if isinstance(raw, list):
        values = raw
    else:
        values = [raw]
    for value in values:
        payload = load_json_server_spec(value, plugin_root)
        if isinstance(payload, dict):
            merged.update(payload)
    return merged


def discover_plugin_components(
    *,
    plugin_name: str,
    plugin_root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    command_paths = unique_existing_paths(
        [plugin_root / "commands"]
        + manifest_component_paths(plugin_root, manifest, "commands"),
    )
    skill_paths = unique_existing_paths(
        [plugin_root / "skills"]
        + manifest_component_paths(plugin_root, manifest, "skills"),
    )
    agent_paths = unique_existing_paths(
        [plugin_root / "agents"]
        + manifest_component_paths(plugin_root, manifest, "agents"),
    )
    output_style_paths = unique_existing_paths(
        [plugin_root / "output-styles"]
        + manifest_component_paths(plugin_root, manifest, "outputStyles"),
    )
    hook_commands, event_hooks = load_hook_components(plugin_root, manifest)

    return {
        "commands": load_markdown_components(
            plugin_name=plugin_name,
            component_paths=command_paths,
            component_type="command",
        ),
        "skills": load_markdown_components(
            plugin_name=plugin_name,
            component_paths=skill_paths,
            component_type="skill",
            skill_mode=True,
        ),
        "agents": load_markdown_components(
            plugin_name=plugin_name,
            component_paths=agent_paths,
            component_type="agent",
        ),
        "outputStyles": load_markdown_components(
            plugin_name=plugin_name,
            component_paths=output_style_paths,
            component_type="output-style",
        ),
        "eventHooks": event_hooks,
        "hookCommands": hook_commands,
        "mcpServers": load_mcp_servers(manifest, plugin_root),
        "lspServers": load_lsp_servers(manifest, plugin_root),
        "channels": manifest.get("channels", []),
        "userConfig": manifest.get("userConfig", {}),
    }


def default_user_config_values_from_schema(
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    values: dict[str, Any] = {}
    secrets: dict[str, str] = {}
    for key, config in schema.items():
        if not isinstance(config, dict):
            continue
        if "default" not in config:
            continue
        default_value = config.get("default")
        if default_value is None:
            continue
        if bool(config.get("sensitive")):
            secrets[str(key)] = str(default_value)
            continue
        values[str(key)] = default_value
    return values, secrets


def plugin_translation_from_directory(
    *,
    plugin_dir: str,
    scope: str,
    enabled: bool,
    source: str,
) -> tuple[dict[str, Any] | None, dict[str, str], str | None]:
    plugin_root = Path(plugin_dir).expanduser().resolve()
    if plugin_root.is_file():
        plugin_root = plugin_root.parent
    if not plugin_root.exists() or not plugin_root.is_dir():
        return None, {}, f"Plugin directory not found: {plugin_dir}"

    manifest_path = plugin_root / "plugin.json"
    manifest = read_json_file(manifest_path) or {}
    name = str(manifest.get("name", "")).strip() or plugin_root.name
    version_value = manifest.get("version")
    version = str(version_value).strip() if isinstance(version_value, str) else None

    components = discover_plugin_components(
        plugin_name=name,
        plugin_root=plugin_root,
        manifest=manifest,
    )
    hook_commands = components.get("hookCommands")
    if not isinstance(hook_commands, dict):
        hook_commands = {}
    event_hooks = components.get("eventHooks")
    if not isinstance(event_hooks, list):
        event_hooks = []

    command = first_available_hook_command(hook_commands)
    if command is None:
        manifest_command = manifest.get("command")
        if isinstance(manifest_command, str) and manifest_command.strip():
            command = resolve_manifest_command(manifest_command.strip(), plugin_root)
    if command is None:
        for event_hook in event_hooks:
            if not isinstance(event_hook, dict):
                continue
            event_command = event_hook.get("command")
            if isinstance(event_command, str) and event_command.strip():
                command = event_command.strip()
                break
    if command is None:
        return (
            None,
            {},
            (
                f"Plugin '{name}' does not define an executable hook command. "
                "Expected orchestrator_hooks in plugin.json, hooks/hooks.json entries, "
                "or a top-level command."
            ),
        )

    if hook_commands:
        hook_targets = order_hook_targets(hook_commands)
    else:
        hook_targets = []
        for event_hook in event_hooks:
            event_name = canonical_hook_target(str(event_hook.get("event", "")))
            if event_name and event_name not in hook_targets:
                hook_targets.append(event_name)
        if not hook_targets:
            hook_targets = list(DEFAULT_HOOK_TARGETS)

    metadata: dict[str, Any] = {
        "pluginRoot": str(plugin_root),
        "manifestPath": str(manifest_path),
    }
    if (
        isinstance(manifest.get("displayName"), str)
        and str(manifest.get("displayName")).strip()
    ):
        metadata["displayName"] = str(manifest.get("displayName")).strip()
    if (
        isinstance(manifest.get("reference_url"), str)
        and str(manifest.get("reference_url")).strip()
    ):
        metadata["referenceUrl"] = str(manifest.get("reference_url")).strip()

    user_config_schema = components.get("userConfig")
    if not isinstance(user_config_schema, dict):
        user_config_schema = {}
    user_config_values, secret_defaults = default_user_config_values_from_schema(
        user_config_schema,
    )

    translation: dict[str, Any] = {
        "name": name,
        "scope": scope,
        "enabled": enabled,
        "command": command,
        "hookCommands": hook_commands,
        "hookTargets": hook_targets,
        "source": source,
        "sourceType": "directory",
        "sourceCommandLine": f"plugin-dir:{plugin_root}",
        "installPath": str(plugin_root),
        "eventHooks": event_hooks,
        "components": components,
        "userConfigValues": user_config_values,
        "metadata": metadata,
    }
    if version:
        translation["version"] = version
    return translation, secret_defaults, None


def install_plugin_from_directory_state(
    *,
    plugin_dir: str,
    scope: str,
    enabled: bool,
    overwrite: bool,
    source: str = "plugin-directory-install",
) -> tuple[dict[str, Any] | None, str | None]:
    canonical, scope_error = canonical_scope(scope)
    if scope_error or canonical is None:
        return None, scope_error or "Invalid scope."
    translation, secret_defaults, translation_error = plugin_translation_from_directory(
        plugin_dir=plugin_dir,
        scope=canonical,
        enabled=enabled,
        source=source,
    )
    if translation_error or translation is None:
        return None, translation_error or "Could not translate plugin directory."
    record, upsert_error = upsert_plugin(
        translation,
        overwrite=overwrite,
    )
    if upsert_error or record is None:
        return None, upsert_error or "Failed to install plugin."
    record_key = str(
        record.get("id", plugin_record_key(str(record.get("name", "")), canonical))
    )
    existing_secret_values = load_secret_values_for_record(record_key)
    merged_secret_values = dict(secret_defaults)
    merged_secret_values.update(existing_secret_values)
    if merged_secret_values:
        save_secret_values_for_record(record_key, merged_secret_values)
    return record, None


def refresh_plugin_state(
    *,
    name: str,
    scope: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, existing, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or existing is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    install_path = existing.get("installPath")
    if not isinstance(install_path, str) or not install_path.strip():
        root = plugin_root_from_record(existing)
        if root is None:
            return None, f"Plugin '{name}' has no install path to refresh."
        install_path = str(root)
    scope_value = str(existing.get("scope", "user"))
    translation, secret_defaults, translation_error = plugin_translation_from_directory(
        plugin_dir=install_path,
        scope=scope_value,
        enabled=bool(existing.get("enabled", True)),
        source=str(existing.get("source", "plugin-directory-install")),
    )
    if translation_error or translation is None:
        return None, translation_error or "Failed to refresh plugin."
    translation["name"] = str(existing.get("name", name))
    translation["scope"] = scope_value
    translation["enabled"] = bool(existing.get("enabled", True))
    translation["sourceType"] = str(existing.get("sourceType", "directory"))
    translation["userConfigValues"] = dict(existing.get("userConfigValues", {}))
    translation["channelConfigValues"] = dict(existing.get("channelConfigValues", {}))
    current_secrets = load_secret_values_for_record(record_key)
    record, upsert_error = upsert_plugin(
        translation,
        overwrite=True,
    )
    if upsert_error or record is None:
        return None, upsert_error or "Failed to refresh plugin."
    new_record_key = str(record.get("id", record_key))
    merged_secret_values = dict(secret_defaults)
    merged_secret_values.update(current_secrets)
    if merged_secret_values:
        save_secret_values_for_record(new_record_key, merged_secret_values)
    return record, None


def update_plugin_enabled_state(
    *,
    name: str,
    scope: str | None,
    enabled: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, record, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or record is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    store = load_plugin_store()
    plugins = store.get("plugins")
    if not isinstance(plugins, dict):
        return None, "Plugin store is invalid."
    payload = dict(record)
    payload["enabled"] = bool(enabled)
    payload["updatedAt"] = now_iso()
    normalized, normalize_error = normalize_plugin_record(
        str(payload.get("name", name)),
        payload,
    )
    if normalize_error or normalized is None:
        return None, normalize_error or "Plugin payload is invalid."
    plugins[record_key] = normalized
    save_plugin_store(store)
    return normalized, None


def set_plugin_user_config_value(
    *,
    name: str,
    key: str,
    value: str,
    scope: str | None,
    sensitive: bool | None,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, record, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or record is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    schema = user_config_schema_for_record(record)
    field_schema = schema.get(key)
    inferred_sensitive = (
        bool(field_schema.get("sensitive")) if isinstance(field_schema, dict) else False
    )
    store_as_secret = inferred_sensitive if sensitive is None else bool(sensitive)

    store = load_plugin_store()
    plugins = store.get("plugins")
    if not isinstance(plugins, dict):
        return None, "Plugin store is invalid."
    payload = dict(record)
    user_values = payload.get("userConfigValues")
    if not isinstance(user_values, dict):
        user_values = {}
    user_values = dict(user_values)
    secret_values = load_secret_values_for_record(record_key)
    if store_as_secret:
        secret_values[str(key)] = str(value)
        user_values.pop(str(key), None)
    else:
        user_values[str(key)] = value
        secret_values.pop(str(key), None)
    payload["userConfigValues"] = user_values
    payload["updatedAt"] = now_iso()
    normalized, normalize_error = normalize_plugin_record(
        str(payload.get("name", name)),
        payload,
    )
    if normalize_error or normalized is None:
        return None, normalize_error or "Plugin payload is invalid."
    plugins[record_key] = normalized
    save_plugin_store(store)
    save_secret_values_for_record(record_key, secret_values)
    return normalized, None


def read_plugin_user_config_values(
    *,
    name: str,
    scope: str | None,
    include_sensitive: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, record, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or record is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    schema = user_config_schema_for_record(record)
    values = merged_user_config(
        record_key,
        record,
        include_sensitive=True,
    )
    visible: dict[str, Any] = {}
    for key, value in values.items():
        field_schema = schema.get(key)
        is_sensitive = isinstance(field_schema, dict) and bool(
            field_schema.get("sensitive")
        )
        if is_sensitive and not include_sensitive:
            visible[str(key)] = "[redacted]"
            continue
        visible[str(key)] = value
    return {
        "plugin": str(record.get("name", name)),
        "scope": str(record.get("scope", "user")),
        "values": visible,
        "schema": schema,
    }, None


def set_plugin_channel_config_value(
    *,
    name: str,
    key: str,
    value: str,
    scope: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    record_key, record, resolve_error = resolve_plugin_record(name=name, scope=scope)
    if resolve_error or record_key is None or record is None:
        return None, resolve_error or f"Plugin '{name}' not found."
    store = load_plugin_store()
    plugins = store.get("plugins")
    if not isinstance(plugins, dict):
        return None, "Plugin store is invalid."
    payload = dict(record)
    channel_values = payload.get("channelConfigValues")
    if not isinstance(channel_values, dict):
        channel_values = {}
    channel_values = dict(channel_values)
    channel_values[str(key)] = value
    payload["channelConfigValues"] = channel_values
    payload["updatedAt"] = now_iso()
    normalized, normalize_error = normalize_plugin_record(
        str(payload.get("name", name)),
        payload,
    )
    if normalize_error or normalized is None:
        return None, normalize_error or "Plugin payload is invalid."
    plugins[record_key] = normalized
    save_plugin_store(store)
    return normalized, None


def collect_plugin_integrations_state(
    *,
    scope: str | None = None,
    include_disabled: bool = False,
) -> dict[str, Any]:
    scope_filter: str | None = None
    if scope is not None:
        scope_filter, _ = canonical_scope(scope)
    mcp_servers: dict[str, Any] = {}
    lsp_servers: dict[str, Any] = {}
    channels: list[dict[str, Any]] = []
    for record_key, raw_plugin in list_plugin_records():
        plugin_name = str(raw_plugin.get("name", "")).strip()
        normalized, error = normalize_plugin_record(plugin_name, raw_plugin)
        if error or normalized is None:
            continue
        plugin = normalized
        plugin_scope = str(plugin.get("scope", "user"))
        if scope_filter and plugin_scope != scope_filter:
            continue
        if not include_disabled and not bool(plugin.get("enabled", True)):
            continue
        components = plugin.get("components")
        if not isinstance(components, dict):
            continue
        for server_name, server_payload in dict(
            components.get("mcpServers", {})
        ).items():
            key = f"{plugin_name}:{server_name}"
            mcp_servers[key] = substitute_in_structure(
                server_payload,
                record_key=record_key,
                record=plugin,
                include_sensitive=False,
            )
        for server_name, server_payload in dict(
            components.get("lspServers", {})
        ).items():
            key = f"{plugin_name}:{server_name}"
            lsp_servers[key] = substitute_in_structure(
                server_payload,
                record_key=record_key,
                record=plugin,
                include_sensitive=False,
            )
        for channel in list(components.get("channels", [])):
            channel_payload = substitute_in_structure(
                channel,
                record_key=record_key,
                record=plugin,
                include_sensitive=False,
            )
            if isinstance(channel_payload, dict):
                entry = dict(channel_payload)
                entry["pluginName"] = plugin_name
                entry["pluginScope"] = plugin_scope
                channels.append(entry)
    return {
        "mcpServers": mcp_servers,
        "lspServers": lsp_servers,
        "channels": channels,
    }


def user_config_schema_for_record(record: dict[str, Any]) -> dict[str, Any]:
    components = record.get("components")
    if not isinstance(components, dict):
        return {}
    schema = components.get("userConfig")
    if not isinstance(schema, dict):
        return {}
    return schema


def merged_user_config(
    record_key: str,
    record: dict[str, Any],
    *,
    include_sensitive: bool,
) -> dict[str, Any]:
    values = record.get("userConfigValues")
    merged: dict[str, Any] = {}
    if isinstance(values, dict):
        merged.update(values)
    if include_sensitive:
        merged.update(load_secret_values_for_record(record_key))
    return merged


def merged_channel_config(record: dict[str, Any]) -> dict[str, Any]:
    values = record.get("channelConfigValues")
    if not isinstance(values, dict):
        return {}
    return dict(values)


def substitute_plugin_variables(value: str, record: dict[str, Any]) -> str:
    root = plugin_root_from_record(record)
    if root:
        root_value = str(root)
        value = value.replace("${CLAUDE_PLUGIN_ROOT}", root_value)
    data_path = str(plugin_data_directory(record))
    value = value.replace("${CLAUDE_PLUGIN_DATA}", data_path)
    return value


def substitute_channel_config_variables(
    value: str,
    *,
    record: dict[str, Any],
) -> str:
    merged = merged_channel_config(record)

    def replace(match: re.Match[str]) -> str:
        key = str(match.group(1)).strip()
        if not key:
            return match.group(0)
        if key not in merged:
            return match.group(0)
        return str(merged[key])

    return CHANNEL_CONFIG_PATTERN.sub(replace, value)


def substitute_user_config_variables(
    value: str,
    *,
    record_key: str,
    record: dict[str, Any],
    include_sensitive: bool,
) -> str:
    schema = user_config_schema_for_record(record)
    merged = merged_user_config(record_key, record, include_sensitive=include_sensitive)

    def replace(match: re.Match[str]) -> str:
        key = str(match.group(1)).strip()
        if not key:
            return match.group(0)
        if key not in merged:
            return match.group(0)
        field_schema = schema.get(key)
        sensitive = isinstance(field_schema, dict) and bool(
            field_schema.get("sensitive")
        )
        if sensitive and not include_sensitive:
            return f"[sensitive option '{key}' not available]"
        return str(merged[key])

    return USER_CONFIG_PATTERN.sub(replace, value)


def substitute_runtime_variables(
    value: str,
    *,
    record_key: str,
    record: dict[str, Any],
    include_sensitive: bool,
) -> str:
    substituted = substitute_plugin_variables(value, record)
    substituted = substitute_channel_config_variables(
        substituted,
        record=record,
    )
    return substitute_user_config_variables(
        substituted,
        record_key=record_key,
        record=record,
        include_sensitive=include_sensitive,
    )


def substitute_in_structure(
    value: Any,
    *,
    record_key: str,
    record: dict[str, Any],
    include_sensitive: bool,
) -> Any:
    if isinstance(value, str):
        return substitute_runtime_variables(
            value,
            record_key=record_key,
            record=record,
            include_sensitive=include_sensitive,
        )
    if isinstance(value, list):
        return [
            substitute_in_structure(
                item,
                record_key=record_key,
                record=record,
                include_sensitive=include_sensitive,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): substitute_in_structure(
                item,
                record_key=record_key,
                record=record,
                include_sensitive=include_sensitive,
            )
            for key, item in value.items()
        }
    return value


def normalize_hook_targets(
    raw_targets: list[str] | None,
) -> tuple[list[str] | None, str | None]:
    if raw_targets is None or len(raw_targets) == 0:
        return list(DEFAULT_HOOK_TARGETS), None

    normalized: list[str] = []
    for value in raw_targets:
        chunks = str(value).split(",")
        for chunk in chunks:
            target = chunk.strip().lower()
            if not target:
                continue
            alias = canonical_hook_target(target)
            if not alias:
                return None, f"Unsupported hook target: {chunk}"
            if alias not in normalized:
                normalized.append(alias)

    if not normalized:
        return list(DEFAULT_HOOK_TARGETS), None
    return normalized, None


def parse_timeout_seconds(raw_timeout: object) -> tuple[float | None, str | None]:
    if raw_timeout is None:
        return None, None
    try:
        timeout = float(str(raw_timeout).strip())
    except (TypeError, ValueError):
        return None, "Timeout must be a positive number."
    if timeout <= 0:
        return None, "Timeout must be a positive number."
    return timeout, None


def first_available_hook_command(
    hook_commands: dict[str, str],
    fallback_command: str | None = None,
) -> str | None:
    for target in DEFAULT_HOOK_TARGETS:
        command = hook_commands.get(target)
        if command:
            return command
    for command in hook_commands.values():
        if command:
            return command
    return fallback_command


def normalize_plugin_record(
    plugin_name: str,
    raw_record: object,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_record, dict):
        return None, f"Plugin '{plugin_name}' must be an object."

    command = raw_record.get("command")
    command_value: str | None = None
    if isinstance(command, str) and command.strip():
        command_value = command.strip()
    scope, scope_error = canonical_scope(str(raw_record.get("scope", "user")))
    if scope_error or scope is None:
        return None, scope_error or "Invalid scope."
    record_key = plugin_record_key(plugin_name, scope)

    hook_commands_raw = raw_record.get("hookCommands")
    hook_commands: dict[str, str] = {}
    if isinstance(hook_commands_raw, dict):
        for target, hook_command in hook_commands_raw.items():
            alias = canonical_hook_target(str(target))
            if not alias:
                continue
            if not isinstance(hook_command, str) or not hook_command.strip():
                continue
            hook_commands[alias] = hook_command.strip()

    if not hook_commands and command_value:
        hook_commands = {
            target: command_value for target in ["preflight", "postflight"]
        }

    resolved_command = first_available_hook_command(hook_commands, command_value)
    if not resolved_command:
        return (
            None,
            f"Plugin '{plugin_name}' must define at least one executable command.",
        )

    hook_targets_raw = raw_record.get("hookTargets")
    hook_targets: list[str] | None = None
    if isinstance(hook_targets_raw, list):
        normalized_targets, hook_error = normalize_hook_targets(
            [str(value) for value in hook_targets_raw],
        )
        if hook_error:
            return None, hook_error
        hook_targets = normalized_targets
    elif hook_commands:
        hook_targets = order_hook_targets(hook_commands)
    else:
        hook_targets = list(DEFAULT_HOOK_TARGETS)

    if hook_targets is None:
        hook_targets = list(DEFAULT_HOOK_TARGETS)

    timeout_seconds, timeout_error = parse_timeout_seconds(
        raw_record.get("timeoutSeconds"),
    )
    if timeout_error:
        return None, timeout_error

    metadata = raw_record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)

    condition = raw_record.get("if")
    matcher = raw_record.get("matcher")
    status_message = raw_record.get("statusMessage")
    source_type = str(raw_record.get("sourceType", "")).strip() or "claude-bridge"
    event_hooks_raw = raw_record.get("eventHooks")
    event_hooks: list[dict[str, Any]] = []
    if isinstance(event_hooks_raw, list):
        for item in event_hooks_raw:
            if not isinstance(item, dict):
                continue
            event_name = canonical_hook_target(str(item.get("event", "")))
            command_raw = item.get("command")
            if not event_name:
                continue
            if not isinstance(command_raw, str) or not command_raw.strip():
                continue
            parsed_timeout, parsed_timeout_error = parse_timeout_seconds(
                item.get("timeoutSeconds")
            )
            if parsed_timeout_error:
                parsed_timeout = None
            normalized_hook: dict[str, Any] = {
                "event": event_name,
                "command": command_raw.strip(),
                "matcher": str(item.get("matcher", "*") or "*"),
            }
            if isinstance(item.get("if"), str) and str(item.get("if")).strip():
                normalized_hook["if"] = str(item.get("if")).strip()
            if parsed_timeout is not None:
                normalized_hook["timeoutSeconds"] = parsed_timeout
            if (
                isinstance(item.get("statusMessage"), str)
                and str(item.get("statusMessage")).strip()
            ):
                normalized_hook["statusMessage"] = str(
                    item.get("statusMessage")
                ).strip()
            if bool(item.get("once", False)):
                normalized_hook["once"] = True
            if bool(item.get("async", False)):
                normalized_hook["async"] = True
            if bool(item.get("asyncRewake", False)):
                normalized_hook["asyncRewake"] = True
            event_hooks.append(normalized_hook)

    components = raw_record.get("components")
    if not isinstance(components, dict):
        components = {}
    components = dict(components)
    for key in (
        "commands",
        "skills",
        "agents",
        "outputStyles",
        "channels",
        "eventHooks",
    ):
        if key in components and not isinstance(components.get(key), list):
            components[key] = []
    for key in ("mcpServers", "lspServers", "userConfig"):
        if key in components and not isinstance(components.get(key), dict):
            components[key] = {}
    if event_hooks and not components.get("eventHooks"):
        components["eventHooks"] = event_hooks
    if hook_commands and not isinstance(components.get("hookCommands"), dict):
        components["hookCommands"] = dict(hook_commands)

    user_config_values = raw_record.get("userConfigValues")
    if not isinstance(user_config_values, dict):
        user_config_values = {}
    channel_config_values = raw_record.get("channelConfigValues")
    if not isinstance(channel_config_values, dict):
        channel_config_values = {}
    install_path = raw_record.get("installPath")
    if isinstance(install_path, str) and install_path.strip():
        install_path = str(Path(install_path).expanduser())
    else:
        install_path = None

    normalized: dict[str, Any] = {
        "id": record_key,
        "name": plugin_name,
        "scope": scope,
        "enabled": bool(raw_record.get("enabled", True)),
        "command": resolved_command,
        "hookCommands": hook_commands,
        "hookTargets": hook_targets,
        "source": str(raw_record.get("source", "claude-plugin-add")),
        "sourceType": source_type,
        "sourceCommandLine": str(raw_record.get("sourceCommandLine", "")),
        "installPath": install_path,
        "version": raw_record.get("version"),
        "eventHooks": event_hooks,
        "components": components,
        "userConfigValues": user_config_values,
        "channelConfigValues": channel_config_values,
        "metadata": metadata,
        "createdAt": str(raw_record.get("createdAt", now_iso())),
        "updatedAt": str(raw_record.get("updatedAt", now_iso())),
        "once": bool(raw_record.get("once", False)),
        "async": bool(raw_record.get("async", False)),
        "asyncRewake": bool(raw_record.get("asyncRewake", False)),
    }

    if isinstance(condition, str) and condition.strip():
        normalized["if"] = condition.strip()
    if isinstance(matcher, str) and matcher.strip():
        normalized["matcher"] = matcher.strip()
    if isinstance(status_message, str) and status_message.strip():
        normalized["statusMessage"] = status_message.strip()
    if timeout_seconds is not None:
        normalized["timeoutSeconds"] = timeout_seconds
    if install_path is None:
        normalized.pop("installPath", None)
    if normalized.get("version") is None:
        normalized.pop("version", None)

    return normalized, None


def infer_plugin_name_from_target(plugin_target: str | None) -> str | None:
    if not plugin_target:
        return None
    cleaned = plugin_target.strip()
    if not cleaned:
        return None
    if cleaned.startswith("@"):
        return None
    if "@" in cleaned:
        return cleaned.split("@", 1)[0].strip() or None
    return cleaned


def parse_plugin_command_action(tokens: list[str]) -> tuple[str | None, int | None]:
    normalized_tokens = [
        token[1:] if token.startswith("/") else token for token in tokens
    ]

    for index in range(len(normalized_tokens) - 1):
        if normalized_tokens[index] in {"plugin", "plugins"} and normalized_tokens[
            index + 1
        ] in {"add", "install"}:
            return normalized_tokens[index + 1], index + 1

    if normalized_tokens and normalized_tokens[0] in {"add", "install"}:
        return normalized_tokens[0], 0
    return None, None


def translate_claude_plugin_command(
    command_line: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        tokens = shlex.split(command_line)
    except ValueError as error:
        return None, f"Invalid command line: {error}"

    if not tokens:
        return None, "Command line cannot be empty."

    action, action_index = parse_plugin_command_action(tokens)
    if action is None or action_index is None:
        return None, (
            "Expected a Claude plugin command using 'plugin add' or 'plugin install' "
            "(for example: 'claude plugin install plugin-dev@marketplace')."
        )

    tail = tokens[action_index + 1 :]
    if not tail:
        return None, "Plugin command is missing plugin details."

    plugin_name: str | None = None
    explicit_command: str | None = None
    plugin_target: str | None = None
    free_tokens: list[str] = []
    install_tokens: list[str] = []
    hook_targets_raw: list[str] = []
    hook_condition: str | None = None
    matcher: str | None = None
    timeout_seconds: float | None = None
    status_message: str | None = None
    plugin_scope = "user"
    once = False
    async_hook = False
    async_rewake = False

    i = 0
    while i < len(tail):
        token = tail[i]

        if token == "--":
            if action == "install":
                install_tokens.extend(tail[i + 1 :])
            else:
                free_tokens.extend(tail[i + 1 :])
            break

        if token in {"--name", "-n"}:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            plugin_name = tail[i + 1]
            i += 2
            continue

        if token in {"--command", "--cmd", "-c"}:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            explicit_command = tail[i + 1]
            i += 2
            continue
        if token == "--scope":
            if i + 1 >= len(tail):
                return None, "Missing value for option --scope"
            parsed_scope, parsed_scope_error = canonical_scope(tail[i + 1])
            if parsed_scope_error or parsed_scope is None:
                return None, parsed_scope_error
            plugin_scope = parsed_scope
            i += 2
            continue
        if token.startswith("--scope="):
            parsed_scope, parsed_scope_error = canonical_scope(token.split("=", 1)[1])
            if parsed_scope_error or parsed_scope is None:
                return None, parsed_scope_error
            plugin_scope = parsed_scope
            i += 1
            continue
        if token == "--project":
            plugin_scope = "project"
            i += 1
            continue
        if token == "--local":
            plugin_scope = "local"
            i += 1
            continue
        if token in {"--user", "--global"}:
            plugin_scope = "user"
            i += 1
            continue

        if token.startswith("--command=") or token.startswith("--cmd="):
            explicit_command = token.split("=", 1)[1]
            i += 1
            continue

        if token in {"--hook", "--hooks"}:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            hook_targets_raw.append(tail[i + 1])
            i += 2
            continue

        if token.startswith("--hook=") or token.startswith("--hooks="):
            hook_targets_raw.append(token.split("=", 1)[1])
            i += 1
            continue

        if token == "--preflight":
            hook_targets_raw.append("preflight")
            i += 1
            continue

        if token == "--postflight":
            hook_targets_raw.append("postflight")
            i += 1
            continue

        if token in {"--statusMessage"}:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            status_message = tail[i + 1]
            i += 2
            continue

        if token.startswith("--statusMessage="):
            status_message = token.split("=", 1)[1]
            i += 1
            continue

        if token in HOOK_CONFIG_OPTIONS_WITH_VALUE:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            value = tail[i + 1]
            if token == "--if":
                hook_condition = value
            elif token == "--timeout":
                timeout_seconds, timeout_error = parse_timeout_seconds(value)
                if timeout_error:
                    return None, timeout_error
            elif token == "--status-message":
                status_message = value
            elif token == "--matcher":
                matcher = value
            i += 2
            continue

        if any(
            token.startswith(f"{option}=") for option in HOOK_CONFIG_OPTIONS_WITH_VALUE
        ):
            option_name, option_value = token.split("=", 1)
            if option_name == "--if":
                hook_condition = option_value
            elif option_name == "--timeout":
                timeout_seconds, timeout_error = parse_timeout_seconds(option_value)
                if timeout_error:
                    return None, timeout_error
            elif option_name == "--status-message":
                status_message = option_value
            elif option_name == "--matcher":
                matcher = option_value
            i += 1
            continue

        if token in HOOK_CONFIG_OPTIONS_NO_VALUE:
            if token == "--once":
                once = True
            elif token == "--async":
                async_hook = True
            elif token == "--async-rewake":
                async_hook = True
                async_rewake = True
            i += 1
            continue
        if token in {"--plugin", "--source"}:
            if i + 1 >= len(tail):
                return None, f"Missing value for option {token}"
            if action == "install":
                install_tokens.append(tail[i + 1])
            else:
                free_tokens.append(tail[i + 1])
            i += 2
            continue

        if token.startswith("--plugin=") or token.startswith("--source="):
            value = token.split("=", 1)[1]
            if action == "install":
                install_tokens.append(value)
            else:
                free_tokens.append(value)
            i += 1
            continue

        if token in IGNORED_PLUGIN_OPTIONS_WITH_VALUE:
            if i + 1 < len(tail):
                i += 2
            else:
                i += 1
            continue

        if any(
            token.startswith(f"{prefix}=")
            for prefix in IGNORED_PLUGIN_OPTIONS_WITH_VALUE
        ):
            i += 1
            continue

        if token in IGNORED_PLUGIN_OPTIONS_NO_VALUE:
            i += 1
            continue

        if token.startswith("--"):
            if action == "install":
                install_tokens.append(token)
            else:
                free_tokens.append(token)
            i += 1
            continue
        if action == "install":
            install_tokens.append(token)
            i += 1
            continue

        if plugin_name is None and action == "add":
            plugin_name = token
        else:
            free_tokens.append(token)
        i += 1

    builtin_translation: dict[str, Any] | None = None

    if action == "install":
        if plugin_target is None and install_tokens:
            plugin_target = install_tokens[0]

        if plugin_name is None:
            plugin_name = infer_plugin_name_from_target(plugin_target)

        if plugin_name is None and len(install_tokens) > 1:
            fallback_name = infer_plugin_name_from_target(install_tokens[1])
            if fallback_name:
                plugin_name = fallback_name
                if plugin_target and plugin_target.startswith("@"):
                    plugin_target = f"{fallback_name}{plugin_target}"
                elif plugin_target is None or plugin_target.startswith("-"):
                    plugin_target = install_tokens[1]

        if explicit_command is not None:
            translated_command = explicit_command
        else:
            builtin_translation = load_builtin_plugin_translation(
                plugin_name=plugin_name or "",
                plugin_target=plugin_target,
            )
            if not builtin_translation:
                return None, (
                    "Unsupported plugin install target. Provide --cmd/--command or use a known "
                    "target such as plugin-dev or github."
                )
            translated_command = str(builtin_translation.get("command", "")).strip()
    elif explicit_command is None and free_tokens:
        translated_command = shlex.join(free_tokens)
    elif explicit_command is not None and free_tokens:
        translated_command = f"{explicit_command} {shlex.join(free_tokens)}"
    else:
        translated_command = explicit_command

    if not plugin_name and plugin_target:
        plugin_name = infer_plugin_name_from_target(plugin_target)

    if not plugin_name:
        if translated_command and translated_command.strip():
            inferred_name = translated_command.strip().split(" ", 1)[0]
            plugin_name = inferred_name.split("/")[-1]
        if not plugin_name:
            plugin_name = f"plugin-{uuid4().hex[:8]}"

    if not translated_command or not translated_command.strip():
        return None, (
            "Could not determine plugin command to execute. Provide --cmd/--command, or use "
            "a supported plugin target such as plugin-dev."
        )
    if hook_targets_raw:
        raw_hook_target_input: list[str] | None = hook_targets_raw
    elif isinstance(builtin_translation, dict):
        candidate_targets = builtin_translation.get("hookTargets")
        if isinstance(candidate_targets, list):
            raw_hook_target_input = [str(value) for value in candidate_targets]
        else:
            raw_hook_target_input = None
    else:
        raw_hook_target_input = None

    hook_targets, hook_error = normalize_hook_targets(raw_hook_target_input)
    if hook_error:
        return None, hook_error

    metadata: dict[str, Any] = {
        "action": action,
        "pluginTarget": plugin_target,
        "referenceUrl": plugin_reference_url(plugin_name.strip()),
    }
    hook_commands: dict[str, str] | None = None
    if isinstance(builtin_translation, dict):
        candidate_metadata = builtin_translation.get("metadata")
        if isinstance(candidate_metadata, dict):
            metadata.update(candidate_metadata)

        candidate_hook_commands = builtin_translation.get("hookCommands")
        if isinstance(candidate_hook_commands, dict):
            resolved_commands: dict[str, str] = {}
            for target, command in candidate_hook_commands.items():
                alias = HOOK_TARGET_ALIASES.get(str(target).strip().lower())
                if not alias:
                    continue
                if isinstance(command, str) and command.strip():
                    resolved_commands[alias] = command.strip()
            if resolved_commands:
                hook_commands = resolved_commands

    translated = {
        "name": plugin_name.strip(),
        "scope": plugin_scope,
        "command": translated_command.strip(),
        "hookTargets": hook_targets,
        "source": f"claude-plugin-{action}",
        "sourceCommandLine": command_line,
        "metadata": metadata,
    }
    if hook_commands:
        translated["hookCommands"] = hook_commands
    if hook_condition and hook_condition.strip():
        translated["if"] = hook_condition.strip()
    if matcher and matcher.strip():
        translated["matcher"] = matcher.strip()
    if timeout_seconds is not None:
        translated["timeoutSeconds"] = timeout_seconds
    if status_message and status_message.strip():
        translated["statusMessage"] = status_message.strip()
    if once:
        translated["once"] = True
    if async_hook:
        translated["async"] = True
    if async_rewake:
        translated["asyncRewake"] = True
    return translated, None


def list_plugins_state() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record_key, raw_record in list_plugin_records():
        plugin_name = str(raw_record.get("name", "")).strip()
        normalized, _ = normalize_plugin_record(plugin_name, raw_record)
        if normalized is not None:
            records.append(normalized)
    records.sort(
        key=lambda item: (str(item.get("name", "")), str(item.get("scope", "")))
    )
    return records


def upsert_plugin(
    translated_plugin: dict[str, Any],
    *,
    overwrite: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    name = str(translated_plugin.get("name", "")).strip()
    if not name:
        return None, "Plugin name is required."
    scope, scope_error = canonical_scope(str(translated_plugin.get("scope", "user")))
    if scope_error or scope is None:
        return None, scope_error or "Invalid scope."
    record_key = plugin_record_key(name, scope)

    store = load_plugin_store()
    plugins = store.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        store["plugins"] = plugins
    existing = plugins.get(record_key)
    legacy_existing = plugins.get(name)
    if not isinstance(existing, dict) and isinstance(legacy_existing, dict):
        existing = legacy_existing
    if existing is not None and not overwrite:
        return (
            None,
            f"Plugin '{name}' already exists for scope '{scope}'. Set overwrite=true to replace it.",
        )

    now = now_iso()
    created_at = now
    if isinstance(existing, dict):
        created_at = str(existing.get("createdAt", now))
    existing_metadata: dict[str, Any] = {}
    if isinstance(existing, dict):
        maybe_existing_metadata = existing.get("metadata")
        if isinstance(maybe_existing_metadata, dict):
            existing_metadata = dict(maybe_existing_metadata)

    incoming_metadata = translated_plugin.get("metadata", {})
    if not isinstance(incoming_metadata, dict):
        incoming_metadata = {}
    merged_metadata = dict(existing_metadata)
    merged_metadata.update(incoming_metadata)
    existing_components = (
        existing.get("components", {}) if isinstance(existing, dict) else {}
    )
    if not isinstance(existing_components, dict):
        existing_components = {}
    incoming_components = translated_plugin.get("components", {})
    if not isinstance(incoming_components, dict):
        incoming_components = {}
    merged_components = dict(existing_components)
    merged_components.update(incoming_components)

    record_payload: dict[str, Any] = {
        "name": name,
        "scope": scope,
        "enabled": bool(
            translated_plugin.get(
                "enabled",
                existing.get("enabled", True) if isinstance(existing, dict) else True,
            )
        ),
        "command": str(translated_plugin.get("command", "")),
        "hookTargets": translated_plugin.get("hookTargets", list(DEFAULT_HOOK_TARGETS)),
        "hookCommands": translated_plugin.get("hookCommands", {}),
        "source": str(translated_plugin.get("source", "claude-plugin-add")),
        "sourceType": str(
            translated_plugin.get(
                "sourceType",
                existing.get("sourceType", "claude-bridge")
                if isinstance(existing, dict)
                else "claude-bridge",
            )
        ),
        "sourceCommandLine": str(translated_plugin.get("sourceCommandLine", "")),
        "installPath": translated_plugin.get(
            "installPath",
            existing.get("installPath") if isinstance(existing, dict) else None,
        ),
        "version": translated_plugin.get(
            "version",
            existing.get("version") if isinstance(existing, dict) else None,
        ),
        "eventHooks": translated_plugin.get(
            "eventHooks",
            existing.get("eventHooks", []) if isinstance(existing, dict) else [],
        ),
        "components": merged_components,
        "userConfigValues": translated_plugin.get(
            "userConfigValues",
            existing.get("userConfigValues", {}) if isinstance(existing, dict) else {},
        ),
        "channelConfigValues": translated_plugin.get(
            "channelConfigValues",
            existing.get("channelConfigValues", {})
            if isinstance(existing, dict)
            else {},
        ),
        "metadata": merged_metadata,
        "createdAt": created_at,
        "updatedAt": now,
    }

    for optional_key in (
        "if",
        "matcher",
        "timeoutSeconds",
        "statusMessage",
        "once",
        "async",
        "asyncRewake",
    ):
        if optional_key in translated_plugin:
            record_payload[optional_key] = translated_plugin[optional_key]

    normalized_record, error = normalize_plugin_record(name, record_payload)
    if error:
        return None, error
    if normalized_record is None:
        return None, "Plugin payload is invalid."
    plugins.pop(name, None)
    plugins[record_key] = normalized_record
    save_plugin_store(store)
    return normalized_record, None


def remove_plugin(name: str, scope: str | None = None) -> bool:
    store = load_plugin_store()
    plugins = store.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        return False
    scope_filter: str | None = None
    if scope is not None:
        scope_filter, scope_error = canonical_scope(scope)
        if scope_error or scope_filter is None:
            return False
    to_remove: list[str] = []
    for key, value in plugins.items():
        if not isinstance(value, dict):
            continue
        plugin_name = str(value.get("name", "")).strip()
        plugin_scope = (
            str(value.get("scope", split_plugin_record_key(str(key))[1]))
            .strip()
            .lower()
        )
        if plugin_name != name:
            continue
        if scope_filter and plugin_scope != scope_filter:
            continue
        to_remove.append(str(key))
    if not to_remove:
        return False
    for key in to_remove:
        plugins.pop(key, None)
        save_secret_values_for_record(key, {})
    save_plugin_store(store)
    return True


def remove_plugins_by_name(names: list[str]) -> list[str]:
    if not names:
        return []
    store = load_plugin_store()
    plugins = store.get("plugins")
    if not isinstance(plugins, dict):
        return []

    removed: list[str] = []
    to_remove: list[str] = []
    name_set = {name for name in names if name}
    for key, value in plugins.items():
        if not isinstance(value, dict):
            continue
        plugin_name = str(value.get("name", "")).strip()
        if plugin_name in name_set:
            to_remove.append(str(key))
            if plugin_name not in removed:
                removed.append(plugin_name)
    for key in to_remove:
        plugins.pop(key, None)
        save_secret_values_for_record(key, {})
    if removed:
        save_plugin_store(store)
    return removed


def plugin_matches_hook(plugin: dict[str, Any], hook_name: str) -> bool:
    normalized_hook_name = canonical_hook_target(hook_name)
    if not normalized_hook_name:
        return False
    targets = plugin.get("hookTargets", [])
    if not isinstance(targets, list):
        return False

    normalized_targets, _ = normalize_hook_targets([str(item) for item in targets])
    if not normalized_targets or normalized_hook_name not in normalized_targets:
        return False

    matcher = plugin.get("matcher")
    if isinstance(matcher, str) and matcher.strip():
        return fnmatch.fnmatch(normalized_hook_name, matcher.strip())
    return True


def command_for_hook(plugin: dict[str, Any], hook_name: str) -> str | None:
    hook_commands = plugin.get("hookCommands")
    if isinstance(hook_commands, dict):
        hook_command = hook_commands.get(hook_name)
        if isinstance(hook_command, str) and hook_command.strip():
            return hook_command.strip()

    command = plugin.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()
    return None


def build_plugin_option_env(
    *,
    record_key: str,
    plugin: dict[str, Any],
    hook_name: str,
) -> dict[str, str]:
    merged_options = merged_user_config(
        record_key,
        plugin,
        include_sensitive=True,
    )
    env: dict[str, str] = {
        f"CLAUDE_PLUGIN_OPTION_{str(key).upper()}": str(value)
        for key, value in merged_options.items()
    }
    env["CLAUDE_PLUGIN_SCOPE"] = str(plugin.get("scope", "user"))
    env["CLAUDE_PLUGIN_ID"] = str(plugin.get("id", record_key))
    env["CLAUDE_PLUGIN_NAME"] = str(plugin.get("name", ""))
    env["CLAUDE_PLUGIN_HOOK"] = hook_name
    env["CLAUDE_PLUGIN_DATA"] = str(plugin_data_directory(plugin))
    root = plugin_root_from_record(plugin)
    if root:
        env["CLAUDE_PLUGIN_ROOT"] = str(root)
    return env


def collect_plugin_commands(hook_name: str) -> list[dict[str, Any]]:
    normalized_hook_name = canonical_hook_target(hook_name)
    if not normalized_hook_name:
        return []
    plugin_commands: list[dict[str, Any]] = []
    for record_key, raw_plugin in list_plugin_records():
        plugin_name = str(raw_plugin.get("name", "")).strip()
        plugin_normalized, error = normalize_plugin_record(plugin_name, raw_plugin)
        if error or plugin_normalized is None:
            continue
        plugin = plugin_normalized
        if not bool(plugin.get("enabled", True)):
            continue
        name = str(plugin.get("name", "")).strip()
        fallback_command = command_for_hook(plugin, normalized_hook_name)
        if not name or not fallback_command:
            continue
        if not plugin_matches_hook(plugin, normalized_hook_name):
            continue
        event_hooks: list[dict[str, Any]] = []
        for item in plugin.get("eventHooks", []):
            if not isinstance(item, dict):
                continue
            item_event = canonical_hook_target(str(item.get("event", "")))
            if item_event != normalized_hook_name:
                continue
            item_matcher = str(item.get("matcher", "*") or "*")
            if not fnmatch.fnmatch(normalized_hook_name, item_matcher):
                continue
            event_hooks.append(item)
        if not event_hooks:
            event_hooks = [
                {
                    "event": normalized_hook_name,
                    "command": fallback_command,
                    "matcher": str(plugin.get("matcher", "*") or "*"),
                    "if": plugin.get("if"),
                    "timeoutSeconds": plugin.get("timeoutSeconds"),
                    "statusMessage": plugin.get("statusMessage"),
                    "once": bool(plugin.get("once", False)),
                    "async": bool(plugin.get("async", False)),
                    "asyncRewake": bool(plugin.get("asyncRewake", False)),
                }
            ]
        option_env = build_plugin_option_env(
            record_key=record_key,
            plugin=plugin,
            hook_name=normalized_hook_name,
        )
        for event_hook in event_hooks:
            command_value = str(event_hook.get("command", "")).strip()
            if not command_value:
                continue
            command_value = substitute_runtime_variables(
                command_value,
                record_key=record_key,
                record=plugin,
                include_sensitive=True,
            )
            condition_value = event_hook.get("if")
            if isinstance(condition_value, str) and condition_value.strip():
                condition_value = substitute_runtime_variables(
                    condition_value.strip(),
                    record_key=record_key,
                    record=plugin,
                    include_sensitive=True,
                )
            status_message = event_hook.get("statusMessage")
            if isinstance(status_message, str):
                status_message = substitute_runtime_variables(
                    status_message,
                    record_key=record_key,
                    record=plugin,
                    include_sensitive=False,
                )
            plugin_commands.append(
                {
                    "pluginKey": record_key,
                    "pluginName": name,
                    "scope": str(plugin.get("scope", "user")),
                    "command": command_value,
                    "if": condition_value,
                    "timeoutSeconds": event_hook.get("timeoutSeconds"),
                    "statusMessage": status_message,
                    "once": bool(event_hook.get("once", False)),
                    "async": bool(event_hook.get("async", False)),
                    "asyncRewake": bool(event_hook.get("asyncRewake", False)),
                    "env": option_env,
                }
            )
    return plugin_commands


def task_view(task: TaskRecord) -> dict[str, Any]:
    return {
        "id": task.id,
        "batchId": task.batchId,
        "name": task.name,
        "status": task.status,
        "command": task.command,
        "cwd": task.cwd,
        "startedAt": task.startedAt,
        "endedAt": task.endedAt,
        "exitCode": task.exitCode,
        "signal": task.signal,
        "stdout": task.stdout,
        "stderr": task.stderr,
        "error": task.error,
    }


def track_background(job: asyncio.Task[Any]) -> None:
    BACKGROUND_JOBS.add(job)
    job.add_done_callback(BACKGROUND_JOBS.discard)


async def spawn_shell(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    process = await asyncio.create_subprocess_exec(
        "zsh",
        "-lc",
        command,
        cwd=cwd or os.getcwd(),
        env=run_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        if timeout_seconds is not None:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        else:
            stdout_bytes, stderr_bytes = await process.communicate()
    except asyncio.TimeoutError:
        timed_out = True
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    returncode = process.returncode
    if returncode is None:
        returncode = 1

    exit_code: int | None = returncode if returncode >= 0 else None
    signal: int | None = -returncode if returncode < 0 else None
    error_message = None
    if timed_out:
        error_message = f"Command timed out after {timeout_seconds} seconds."
    return {
        "ok": (returncode == 0) and not timed_out,
        "timedOut": timed_out,
        "exitCode": exit_code,
        "signal": signal,
        "stdout": stdout,
        "stderr": stderr,
        "error": error_message,
    }


async def launch_task(task: TaskRecord) -> None:
    task.status = "running"
    task.startedAt = now_iso()
    result = await spawn_shell(task.command, task.cwd, task.env)
    task.stdout = result["stdout"]
    task.stderr = result["stderr"]
    task.exitCode = result["exitCode"]
    task.signal = result["signal"]
    task.error = result["error"]
    task.endedAt = now_iso()
    task.status = "succeeded" if result["ok"] else "failed"


def parse_hook_json_output(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)

    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if lines:
        last_line = lines[-1]
        if last_line not in candidates:
            candidates.append(last_line)

    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


async def run_command_sequence(
    *,
    name: str,
    commands: list[str],
    cwd: str | None,
    stop_on_error: bool,
) -> dict[str, Any]:
    started_at = now_iso()
    results: list[dict[str, Any]] = []
    succeeded = True
    plugin_commands = collect_plugin_commands(name)
    once_candidates: set[str] = set()
    launched_async_jobs: list[asyncio.Task[dict[str, Any]]] = []

    execution_plan: list[dict[str, Any]] = []
    for command in commands:
        execution_plan.append(
            {
                "command": command,
                "source": "inline",
                "pluginName": None,
                "env": None,
                "timeoutSeconds": None,
                "if": None,
                "statusMessage": None,
                "once": False,
                "async": False,
                "asyncRewake": False,
            }
        )
    for plugin in plugin_commands:
        plugin_env: dict[str, str] = {
            "WARP_ORCHESTRATOR_HOOK": name,
            "WARP_ORCHESTRATOR_PLUGIN_NAME": plugin["pluginName"],
        }
        plugin_env.update(
            {str(key): str(value) for key, value in dict(plugin.get("env", {})).items()}
        )
        execution_plan.append(
            {
                "command": plugin["command"],
                "source": "plugin",
                "pluginName": plugin["pluginName"],
                "env": plugin_env,
                "timeoutSeconds": plugin.get("timeoutSeconds"),
                "if": plugin.get("if"),
                "statusMessage": plugin.get("statusMessage"),
                "once": bool(plugin.get("once", False)),
                "async": bool(plugin.get("async", False)),
                "asyncRewake": bool(plugin.get("asyncRewake", False)),
            }
        )

    for item in execution_plan:
        timeout_seconds: float | None = None
        timeout_error: str | None = None
        if item.get("timeoutSeconds") is not None:
            timeout_seconds, timeout_error = parse_timeout_seconds(
                item.get("timeoutSeconds"),
            )
            if timeout_error:
                results.append(
                    {
                        "command": item["command"],
                        "source": item["source"],
                        "pluginName": item["pluginName"],
                        "ok": False,
                        "exitCode": None,
                        "signal": None,
                        "stdout": "",
                        "stderr": "",
                        "error": timeout_error,
                    }
                )
                succeeded = False
                if stop_on_error:
                    break
                continue

        condition = item.get("if")
        if (
            item["source"] == "plugin"
            and isinstance(condition, str)
            and condition.strip()
        ):
            condition_result = await spawn_shell(
                condition.strip(),
                cwd,
                item.get("env"),
                timeout_seconds=10.0,
            )
            if not condition_result["ok"]:
                results.append(
                    {
                        "command": item["command"],
                        "source": item["source"],
                        "pluginName": item["pluginName"],
                        "ok": True,
                        "skipped": True,
                        "skipReason": "condition-not-met",
                        "conditionCommand": condition.strip(),
                        "conditionExitCode": condition_result["exitCode"],
                        "conditionSignal": condition_result["signal"],
                        "conditionStdout": condition_result["stdout"],
                        "conditionStderr": condition_result["stderr"],
                        "conditionError": condition_result["error"],
                    }
                )
                continue

        if item["source"] == "plugin" and bool(item.get("async", False)):
            async_job = asyncio.create_task(
                spawn_shell(
                    str(item["command"]),
                    cwd,
                    item.get("env"),
                    timeout_seconds=timeout_seconds,
                ),
            )
            launched_async_jobs.append(async_job)
            track_background(
                async_job,
            )
            results.append(
                {
                    "command": item["command"],
                    "source": item["source"],
                    "pluginName": item["pluginName"],
                    "ok": True,
                    "asyncLaunched": True,
                    "statusMessage": item.get("statusMessage"),
                    "asyncRewake": bool(item.get("asyncRewake", False)),
                    "exitCode": None,
                    "signal": None,
                    "stdout": "",
                    "stderr": "",
                    "error": None,
                }
            )
            if (
                item["source"] == "plugin"
                and item.get("once")
                and item.get("pluginName")
            ):
                once_candidates.add(str(item["pluginName"]))
            continue
        result = await spawn_shell(
            str(item["command"]),
            cwd,
            item.get("env"),
            timeout_seconds=timeout_seconds,
        )
        stdout = result["stdout"]
        stderr = result["stderr"]
        hook_control: dict[str, Any] | None = None
        if item["source"] == "plugin":
            hook_control = parse_hook_json_output(stdout)

        continue_after_hook = True
        if hook_control is not None:
            continue_value = hook_control.get("continue")
            if isinstance(continue_value, bool):
                continue_after_hook = continue_value

            suppress_output = hook_control.get("suppressOutput")
            if isinstance(suppress_output, bool) and suppress_output:
                stdout = ""
                stderr = ""

        ok = bool(result["ok"]) and continue_after_hook
        if item["source"] == "plugin" and item.get("once") and item.get("pluginName"):
            once_candidates.add(str(item["pluginName"]))

        stop_reason = None
        if not continue_after_hook:
            reason_value = None
            if hook_control is not None:
                reason_value = hook_control.get("stopReason")
            if isinstance(reason_value, str) and reason_value.strip():
                stop_reason = reason_value.strip()
            else:
                stop_reason = "Plugin hook requested to stop."

        system_message = None
        if hook_control is not None:
            message_value = hook_control.get("systemMessage")
            if isinstance(message_value, str) and message_value.strip():
                system_message = message_value.strip()
        results.append(
            {
                "command": item["command"],
                "source": item["source"],
                "pluginName": item["pluginName"],
                "ok": ok,
                "exitCode": result["exitCode"],
                "signal": result["signal"],
                "stdout": stdout,
                "stderr": stderr,
                "error": result["error"],
                "timedOut": bool(result.get("timedOut", False)),
                "statusMessage": item.get("statusMessage"),
                "hookControl": hook_control,
                "stopReason": stop_reason,
                "systemMessage": system_message,
            }
        )
        if not ok:
            succeeded = False
            if stop_on_error:
                break
    if launched_async_jobs:
        await asyncio.gather(*launched_async_jobs, return_exceptions=True)
    removed_once_plugins = remove_plugins_by_name(sorted(once_candidates))

    return {
        "hook": name,
        "cwd": cwd or os.getcwd(),
        "startedAt": started_at,
        "endedAt": now_iso(),
        "succeeded": succeeded,
        "pluginCommandsIncluded": len(plugin_commands),
        "registeredPlugins": sorted(
            [plugin["pluginName"] for plugin in plugin_commands],
        ),
        "removedOncePlugins": removed_once_plugins,
        "results": results,
    }


def normalize_task_input(
    task_input: dict[str, Any], index: int
) -> tuple[TaskRecord | None, str | None]:
    name = task_input.get("name")
    command = task_input.get("command")
    cwd = task_input.get("cwd")
    env = task_input.get("env")

    if not isinstance(name, str) or not name.strip():
        return None, f"Task at index {index} is missing a valid 'name'."
    if not isinstance(command, str) or not command.strip():
        return None, f"Task at index {index} is missing a valid 'command'."
    if cwd is not None and not isinstance(cwd, str):
        return None, f"Task at index {index} has invalid 'cwd'."
    if env is not None and not isinstance(env, dict):
        return None, f"Task at index {index} has invalid 'env'."

    normalized_env: dict[str, str] = {}
    if isinstance(env, dict):
        for key, value in env.items():
            normalized_env[str(key)] = str(value)

    task = TaskRecord(
        id=str(uuid4()),
        batchId="",
        name=name,
        command=command,
        cwd=cwd or os.getcwd(),
        env=normalized_env,
    )
    return task, None


mcp = FastMCP(
    name="warp-orchestrator",
    instructions=(
        "Use this server to emulate subagent-like fanout, hook-like pre/post checks, and "
        "Claude-style plugin registration for orchestrator hook execution. Dispatch independent "
        "tasks, register plugins, poll status, and collect batch results."
    ),
)


@mcp.tool()
async def dispatch_tasks(
    tasks: list[dict[str, Any]],
    parallel: bool = True,
    waitForCompletion: bool = False,
) -> dict[str, Any]:
    """Dispatch shell tasks as parallel workers (subagent-like fanout)."""
    if not tasks:
        return {"ok": False, "error": "Provide at least one task."}

    batch_id = str(uuid4())
    created: list[TaskRecord] = []

    for index, raw_task in enumerate(tasks):
        if not isinstance(raw_task, dict):
            return {"ok": False, "error": f"Task at index {index} must be an object."}
        normalized, error = normalize_task_input(raw_task, index)
        if error:
            return {"ok": False, "error": error}
        if normalized is None:
            return {"ok": False, "error": f"Task at index {index} is invalid."}
        normalized.batchId = batch_id
        TASKS[normalized.id] = normalized
        created.append(normalized)

    BATCHES[batch_id] = [task.id for task in created]

    if waitForCompletion:
        if parallel:
            await asyncio.gather(*(launch_task(task) for task in created))
        else:
            for task in created:
                await launch_task(task)
    else:
        if parallel:
            for task in created:
                track_background(asyncio.create_task(launch_task(task)))
        else:

            async def run_sequential() -> None:
                for task in created:
                    await launch_task(task)

            track_background(asyncio.create_task(run_sequential()))

    return {
        "batchId": batch_id,
        "waitForCompletion": waitForCompletion,
        "parallel": parallel,
        "tasks": [task_view(task) for task in created],
    }


@mcp.tool()
async def task_status(
    taskId: str | None = None,
    batchId: str | None = None,
) -> dict[str, Any]:
    """Get status for one task or all tasks in a batch."""
    if not taskId and not batchId:
        return {"ok": False, "error": "Provide taskId or batchId."}

    if taskId:
        task = TASKS.get(taskId)
        if not task:
            return {"ok": False, "error": f"Task not found: {taskId}"}
        return {"ok": True, "task": task_view(task)}

    task_ids = BATCHES.get(batchId or "", [])
    return {
        "ok": len(task_ids) > 0,
        "batchId": batchId,
        "tasks": [
            task_view(TASKS[task_id]) for task_id in task_ids if task_id in TASKS
        ],
    }


@mcp.tool()
async def collect_results(
    batchId: str,
    completedOnly: bool = False,
) -> dict[str, Any]:
    """Collect summarized results for all tasks in a batch."""
    task_ids = BATCHES.get(batchId)
    if not task_ids:
        return {"ok": False, "error": f"Batch not found: {batchId}"}

    all_tasks = [task_view(TASKS[task_id]) for task_id in task_ids if task_id in TASKS]
    if completedOnly:
        filtered = [
            task for task in all_tasks if task["status"] in {"succeeded", "failed"}
        ]
    else:
        filtered = all_tasks

    status_counts: dict[str, int] = {}
    for task in filtered:
        status = str(task["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "ok": True,
        "batchId": batchId,
        "completedOnly": completedOnly,
        "total": len(filtered),
        "statusCounts": status_counts,
        "tasks": filtered,
    }


@mcp.tool()
async def run_preflight(
    commands: list[str] | None = None,
    cwd: str | None = None,
    stopOnError: bool = True,
) -> dict[str, Any]:
    """Run command checks before dispatching work."""
    prepared_commands = [
        command for command in (commands or []) if str(command).strip()
    ]
    report = await run_command_sequence(
        name="preflight",
        commands=prepared_commands,
        cwd=cwd,
        stop_on_error=stopOnError,
    )
    if not report["results"]:
        return {
            "ok": False,
            "error": "No preflight commands to run. Provide commands or register plugins for preflight.",
        }
    return report


@mcp.tool()
async def translate_claude_plugin(
    commandLine: str,
    hookTargets: list[str] | None = None,
) -> dict[str, Any]:
    """Translate a Claude plugin command line into orchestrator plugin configuration."""
    translated, error = translate_claude_plugin_command(commandLine)
    if error:
        return {"ok": False, "error": error}

    if hookTargets:
        normalized, hook_error = normalize_hook_targets(hookTargets)
        if hook_error:
            return {"ok": False, "error": hook_error}
        translated["hookTargets"] = normalized

    return {
        "ok": True,
        "translatedPlugin": translated,
    }


@mcp.tool()
async def add_claude_plugin(
    commandLine: str,
    hookTargets: list[str] | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Register a Claude plugin command as an orchestrator plugin and hook configuration."""
    translated, error = translate_claude_plugin_command(commandLine)
    if error:
        return {"ok": False, "error": error}

    if hookTargets:
        normalized, hook_error = normalize_hook_targets(hookTargets)
        if hook_error:
            return {"ok": False, "error": hook_error}
        translated["hookTargets"] = normalized

    record, write_error = upsert_plugin(translated, overwrite=overwrite)
    if write_error:
        return {"ok": False, "error": write_error}

    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def list_plugins() -> dict[str, Any]:
    """List registered orchestrator plugins translated from Claude plugin commands."""
    plugins = list_plugins_state()
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "count": len(plugins),
        "plugins": plugins,
    }


@mcp.tool()
async def install_plugin_directory(
    pluginDir: str,
    scope: str = "user",
    enabled: bool = True,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Install or register a plugin from a local plugin directory."""
    record, error = install_plugin_from_directory_state(
        plugin_dir=pluginDir,
        scope=scope,
        enabled=enabled,
        overwrite=overwrite,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def refresh_plugin(name: str, scope: str | None = None) -> dict[str, Any]:
    """Refresh a plugin's discovered components from its install path."""
    record, error = refresh_plugin_state(name=name, scope=scope)
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def set_plugin_enabled(
    name: str,
    enabled: bool,
    scope: str | None = None,
) -> dict[str, Any]:
    """Enable or disable a plugin in a given scope."""
    record, error = update_plugin_enabled_state(
        name=name,
        scope=scope,
        enabled=enabled,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def set_plugin_user_config(
    name: str,
    key: str,
    value: str,
    scope: str | None = None,
    sensitive: bool | None = None,
) -> dict[str, Any]:
    """Set one userConfig value for a plugin, storing sensitive values in the secret store."""
    record, error = set_plugin_user_config_value(
        name=name,
        key=key,
        value=value,
        scope=scope,
        sensitive=sensitive,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "secretStorePath": str(plugin_secret_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def get_plugin_user_config(
    name: str,
    scope: str | None = None,
    includeSensitive: bool = False,
) -> dict[str, Any]:
    """Read resolved userConfig values for a plugin."""
    values, error = read_plugin_user_config_values(
        name=name,
        scope=scope,
        include_sensitive=includeSensitive,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "secretStorePath": str(plugin_secret_store_path()),
        "config": values,
    }


@mcp.tool()
async def set_plugin_channel_config(
    name: str,
    key: str,
    value: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """Set one channel config value for a plugin."""
    record, error = set_plugin_channel_config_value(
        name=name,
        key=key,
        value=value,
        scope=scope,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def list_plugin_integrations(
    scope: str | None = None,
    includeDisabled: bool = False,
) -> dict[str, Any]:
    """List aggregated MCP/LSP/channel integration surfaces declared by plugins."""
    integrations = collect_plugin_integrations_state(
        scope=scope,
        include_disabled=includeDisabled,
    )
    return {
        "ok": True,
        "integrations": integrations,
    }


@mcp.tool()
async def register_marketplace(
    name: str,
    url: str,
    catalogPath: str | None = None,
    plugins: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Register or update a plugin marketplace definition."""
    record, error = upsert_marketplace_state(
        name=name,
        url=url,
        catalog_path=catalogPath,
        plugins=plugins,
        metadata=metadata,
        overwrite=overwrite,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "marketplaceStorePath": str(marketplace_store_path()),
        "marketplace": record,
    }


@mcp.tool()
async def list_marketplaces() -> dict[str, Any]:
    """List configured plugin marketplaces."""
    marketplaces = list_marketplaces_state()
    return {
        "ok": True,
        "marketplaceStorePath": str(marketplace_store_path()),
        "count": len(marketplaces),
        "marketplaces": marketplaces,
    }


@mcp.tool()
async def install_marketplace_plugin(
    marketplace: str,
    plugin: str,
    scope: str = "user",
    enabled: bool = True,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Install a plugin from a registered marketplace catalog."""
    record, error = install_plugin_from_marketplace_state(
        marketplace_name=marketplace,
        plugin_name=plugin,
        scope=scope,
        enabled=enabled,
        overwrite=overwrite,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "marketplaceStorePath": str(marketplace_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def update_marketplace_plugin(
    name: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """Update an installed marketplace plugin using its linked marketplace metadata."""
    record, error = update_plugin_from_marketplace_state(
        name=name,
        scope=scope,
    )
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "marketplaceStorePath": str(marketplace_store_path()),
        "plugin": record,
    }


@mcp.tool()
async def remove_plugin_by_name(name: str, scope: str | None = None) -> dict[str, Any]:
    """Remove a registered plugin by name."""
    removed = remove_plugin(name, scope=scope)
    if not removed:
        scope_suffix = f" (scope={scope})" if scope else ""
        return {"ok": False, "error": f"Plugin not found: {name}{scope_suffix}"}
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "removed": name,
    }


@mcp.tool()
async def clear_plugins() -> dict[str, Any]:
    """Remove all registered plugins."""
    save_plugin_store({"plugins": {}})
    return {
        "ok": True,
        "storePath": str(plugin_store_path()),
        "cleared": True,
    }


@mcp.tool()
async def run_postflight(
    commands: list[str] | None = None,
    cwd: str | None = None,
    stopOnError: bool = True,
) -> dict[str, Any]:
    """Run command checks after task execution."""
    prepared_commands = [
        command for command in (commands or []) if str(command).strip()
    ]
    report = await run_command_sequence(
        name="postflight",
        commands=prepared_commands,
        cwd=cwd,
        stop_on_error=stopOnError,
    )
    if not report["results"]:
        return {
            "ok": False,
            "error": "No postflight commands to run. Provide commands or register plugins for postflight.",
        }
    return report


@mcp.tool()
async def run_hook_event(
    eventName: str,
    commands: list[str] | None = None,
    cwd: str | None = None,
    stopOnError: bool = True,
) -> dict[str, Any]:
    """Run commands and matching plugin hooks for any supported orchestrator event."""
    normalized = canonical_hook_target(eventName)
    if not normalized:
        return {
            "ok": False,
            "error": (
                f"Unsupported hook event: {eventName}. "
                f"Expected one of: {', '.join(SUPPORTED_HOOK_TARGETS)}."
            ),
        }
    prepared_commands = [
        command for command in (commands or []) if str(command).strip()
    ]
    report = await run_command_sequence(
        name=normalized,
        commands=prepared_commands,
        cwd=cwd,
        stop_on_error=stopOnError,
    )
    if not report["results"]:
        return {
            "ok": False,
            "error": (
                f"No commands to run for event '{normalized}'. "
                "Provide commands or register plugins for this event."
            ),
        }
    return report


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
