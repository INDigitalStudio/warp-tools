from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "projects.registry.json"
DEFAULT_GLOBAL_DIR = Path.home() / ".config" / "warp"
ORCHESTRATOR_PROJECT_CANDIDATES = ("orchestrator",)
PLUGIN_REGISTRATION_SCRIPT = """
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import mcp_orchestrator

command_line = os.environ["WARP_TOOLS_PLUGIN_COMMAND_LINE"]
overwrite = os.environ.get("WARP_TOOLS_PLUGIN_OVERWRITE", "1") == "1"

async def run() -> None:
    result = await mcp_orchestrator.add_claude_plugin(
        commandLine=command_line,
        overwrite=overwrite,
    )
    print(json.dumps(result))

asyncio.run(run())
""".strip()
PLUGIN_MANAGEMENT_SCRIPT = """
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import mcp_orchestrator

action = os.environ["WARP_TOOLS_PLUGIN_ACTION"]
plugin_name = os.environ.get("WARP_TOOLS_PLUGIN_NAME", "")
plugin_scope = os.environ.get("WARP_TOOLS_PLUGIN_SCOPE", "")
plugin_dir = os.environ.get("WARP_TOOLS_PLUGIN_DIR", "")
plugin_key = os.environ.get("WARP_TOOLS_PLUGIN_KEY", "")
plugin_value = os.environ.get("WARP_TOOLS_PLUGIN_VALUE", "")
plugin_marketplace = os.environ.get("WARP_TOOLS_PLUGIN_MARKETPLACE", "")
plugin_url = os.environ.get("WARP_TOOLS_PLUGIN_URL", "")
plugin_catalog_path = os.environ.get("WARP_TOOLS_PLUGIN_CATALOG_PATH", "")
raw_metadata = os.environ.get("WARP_TOOLS_PLUGIN_METADATA_JSON", "")
raw_plugins = os.environ.get("WARP_TOOLS_MARKETPLACE_PLUGINS_JSON", "")
raw_overwrite = os.environ.get("WARP_TOOLS_PLUGIN_OVERWRITE", "1")
raw_enabled = os.environ.get("WARP_TOOLS_PLUGIN_ENABLED", "1")
raw_sensitive = os.environ.get("WARP_TOOLS_PLUGIN_SENSITIVE", "")
raw_include_sensitive = os.environ.get("WARP_TOOLS_PLUGIN_INCLUDE_SENSITIVE", "0")
raw_include_disabled = os.environ.get("WARP_TOOLS_PLUGIN_INCLUDE_DISABLED", "0")

def parse_bool(raw: str, default: bool) -> bool:
    lowered = str(raw).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default

def parse_optional_bool(raw: str) -> bool | None:
    lowered = str(raw).strip().lower()
    if not lowered:
        return None
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None

def parse_json(raw: str) -> dict[str, object] | None:
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None

async def run() -> None:
    scope = plugin_scope if plugin_scope else None
    overwrite = parse_bool(raw_overwrite, True)
    enabled = parse_bool(raw_enabled, True)
    sensitive = parse_optional_bool(raw_sensitive)
    include_sensitive = parse_bool(raw_include_sensitive, False)
    include_disabled = parse_bool(raw_include_disabled, False)
    metadata = parse_json(raw_metadata)
    marketplace_plugins = parse_json(raw_plugins)
    if action == "list":
        result = await mcp_orchestrator.list_plugins()
    elif action == "install-dir":
        result = await mcp_orchestrator.install_plugin_directory(
            pluginDir=plugin_dir,
            scope=scope or "user",
            enabled=enabled,
            overwrite=overwrite,
        )
    elif action == "enable":
        result = await mcp_orchestrator.set_plugin_enabled(
            name=plugin_name,
            scope=scope,
            enabled=True,
        )
    elif action == "disable":
        result = await mcp_orchestrator.set_plugin_enabled(
            name=plugin_name,
            scope=scope,
            enabled=False,
        )
    elif action == "refresh":
        result = await mcp_orchestrator.refresh_plugin(
            name=plugin_name,
            scope=scope,
        )
    elif action == "config-set":
        result = await mcp_orchestrator.set_plugin_user_config(
            name=plugin_name,
            scope=scope,
            key=plugin_key,
            value=plugin_value,
            sensitive=sensitive,
        )
    elif action == "config-get":
        result = await mcp_orchestrator.get_plugin_user_config(
            name=plugin_name,
            scope=scope,
            includeSensitive=include_sensitive,
        )
    elif action == "channel-config-set":
        result = await mcp_orchestrator.set_plugin_channel_config(
            name=plugin_name,
            scope=scope,
            key=plugin_key,
            value=plugin_value,
        )
    elif action == "integrations":
        result = await mcp_orchestrator.list_plugin_integrations(
            scope=scope,
            includeDisabled=include_disabled,
        )
    elif action == "marketplace-add":
        result = await mcp_orchestrator.register_marketplace(
            name=plugin_name,
            url=plugin_url,
            catalogPath=plugin_catalog_path or None,
            plugins=marketplace_plugins,
            metadata=metadata,
            overwrite=overwrite,
        )
    elif action == "marketplace-list":
        result = await mcp_orchestrator.list_marketplaces()
    elif action == "marketplace-install":
        result = await mcp_orchestrator.install_marketplace_plugin(
            marketplace=plugin_marketplace,
            plugin=plugin_name,
            scope=scope or "user",
            enabled=enabled,
            overwrite=overwrite,
        )
    elif action == "marketplace-update":
        result = await mcp_orchestrator.update_marketplace_plugin(
            name=plugin_name,
            scope=scope,
        )
    elif action == "remove":
        result = await mcp_orchestrator.remove_plugin_by_name(name=plugin_name, scope=scope)
    elif action == "clear":
        result = await mcp_orchestrator.clear_plugins()
    else:
        result = {"ok": False, "error": f"Unsupported plugin action: {action}"}
    print(json.dumps(result))

asyncio.run(run())
""".strip()


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def load_json(file_path: Path) -> Any | None:
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"Invalid JSON in {file_path}: {error}")


def save_json(file_path: Path, value: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"{json.dumps(value, indent=2)}\n", encoding="utf-8")


def load_registry() -> dict[str, Any]:
    registry = load_json(REGISTRY_PATH)
    if not isinstance(registry, dict):
        fail(f"Project registry missing or invalid: {REGISTRY_PATH}")
    projects = registry.get("projects")
    if not isinstance(projects, dict):
        fail(f"Project registry missing or invalid: {REGISTRY_PATH}")
    return registry


def run_command(command: list[str], cwd: Path) -> None:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        display = " ".join(command)
        fail(f"Command failed ({display}) in {cwd}")


def copy_project_directory(source_dir: Path, destination_dir: Path, force: bool) -> None:
    if not source_dir.exists():
        fail(f"Source project directory not found: {source_dir}")
    if destination_dir.exists():
        if not force:
            fail(f"Destination exists: {destination_dir} (use --force to replace)")
        shutil.rmtree(destination_dir)
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_dir,
        destination_dir,
        ignore=shutil.ignore_patterns(
            ".git",
            ".DS_Store",
            "node_modules",
            ".venv",
            "__pycache__",
        ),
    )


def render_template(value: str, global_dir: Path, install_path: Path) -> str:
    return (
        value.replace("${GLOBAL_DIR}", str(global_dir))
        .replace("${INSTALL_PATH}", str(install_path))
    )


def resolve_mcp_server_entries(
    project: dict[str, Any],
    global_dir: Path,
    install_absolute_path: Path,
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    raw = project.get("mcp_servers", {})
    if not isinstance(raw, dict):
        return entries

    for server_name, server_config in raw.items():
        if not isinstance(server_config, dict):
            continue

        command = render_template(
            str(server_config.get("command", "")), global_dir, install_absolute_path
        )
        args = [
            render_template(str(value), global_dir, install_absolute_path)
            for value in server_config.get("args", [])
        ]
        working_directory = render_template(
            str(server_config.get("working_directory", global_dir)),
            global_dir,
            install_absolute_path,
        )
        entries[str(server_name)] = {
            "command": command,
            "args": args,
            "working_directory": working_directory,
        }
    return entries


def get_server_map(config: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    if isinstance(config.get("mcpServers"), dict):
        return config, "mcpServers"
    if isinstance(config.get("mcp_servers"), dict):
        return config, "mcp_servers"
    if isinstance(config.get("servers"), dict):
        return config, "servers"
    mcp = config.get("mcp")
    if isinstance(mcp, dict) and isinstance(mcp.get("servers"), dict):
        return mcp, "servers"
    return None


def merge_mcp_servers(file_path: Path, server_entries: dict[str, dict[str, Any]]) -> None:
    existing = load_json(file_path)
    if not isinstance(existing, dict):
        existing = {}

    server_map_info = get_server_map(existing)
    if server_map_info:
        container, key = server_map_info
        merged = dict(container[key])
        merged.update(server_entries)
        container[key] = merged
        save_json(file_path, existing)
        return

    save_json(file_path, {"mcpServers": server_entries})


def resolve_command_template(
    command_template: list[str], global_dir: Path, install_path: Path
) -> list[str]:
    return [render_template(str(token), global_dir, install_path) for token in command_template]


def install_projects(
    registry: dict[str, Any],
    project_target: str,
    *,
    force: bool,
    skip_install: bool,
    activate: bool,
    global_dir: Path,
) -> None:
    all_names = sorted(registry["projects"].keys())
    selected_names = all_names if project_target == "all" else [project_target]

    for name in selected_names:
        if name not in registry["projects"]:
            fail(f"Unknown project: {name}")

    global_mcp_config = global_dir / ".mcp.json"
    installed_server_entries: dict[str, dict[str, Any]] = {}

    for name in selected_names:
        project = registry["projects"][name]
        source_dir = REPO_ROOT / str(project["source"])
        destination_dir = global_dir / str(project["install_path"])

        print(f"Installing {name} -> {destination_dir}")
        copy_project_directory(source_dir, destination_dir, force)

        install_dependencies = bool(project.get("install_dependencies", False))
        if install_dependencies and not skip_install:
            install_command = project.get("install_command")
            if isinstance(install_command, list) and install_command:
                resolved_install = resolve_command_template(
                    install_command, global_dir, destination_dir
                )
            else:
                resolved_install = ["uv", "sync", "--no-dev"]
            run_command(resolved_install, destination_dir)

            audit_command = project.get("audit_command")
            if isinstance(audit_command, list) and audit_command:
                resolved_audit = resolve_command_template(
                    audit_command, global_dir, destination_dir
                )
                run_command(resolved_audit, destination_dir)

        project_server_entries = resolve_mcp_server_entries(
            project, global_dir, destination_dir
        )
        installed_server_entries.update(project_server_entries)

    merge_mcp_servers(global_mcp_config, installed_server_entries)
    print(f"Updated global config: {global_mcp_config}")

    if activate:
        warp_mcp_config = Path.home() / ".warp" / ".mcp.json"
        merge_mcp_servers(warp_mcp_config, installed_server_entries)
        print(f"Updated Warp config: {warp_mcp_config}")


def list_projects(registry: dict[str, Any]) -> None:
    names = sorted(registry["projects"].keys())
    if not names:
        print("No projects found.")
        return
    for name in names:
        source = registry["projects"][name].get("source", "")
        print(f"- {name} -> {source}")

def resolve_orchestrator_project(registry: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    projects = registry.get("projects")
    if not isinstance(projects, dict):
        fail(f"Project registry missing or invalid: {REGISTRY_PATH}")
    for candidate in ORCHESTRATOR_PROJECT_CANDIDATES:
        project = projects.get(candidate)
        if isinstance(project, dict):
            return candidate, project
    fail(
        "Could not find orchestrator project in registry. "
        "Expected project key: orchestrator."
    )

def confirm_action(prompt: str) -> bool:
    try:
        response = input(prompt)
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}
def is_interactive_stdin() -> bool:
    return sys.stdin.isatty()


def ensure_orchestrator_ready(
    registry: dict[str, Any],
    *,
    global_dir: Path,
    auto_install: bool,
) -> tuple[str, Path, Path]:
    project_name, project = resolve_orchestrator_project(registry)
    install_dir = global_dir / str(project["install_path"])
    python_binary = install_dir / ".venv" / "bin" / "python"

    if not install_dir.exists():
        if auto_install:
            print(f"Orchestrator not found at {install_dir}. Installing now...")
            install_projects(
                registry,
                project_name,
                force=False,
                skip_install=False,
                activate=False,
                global_dir=global_dir,
            )
        elif is_interactive_stdin():
            should_install = confirm_action(
                f"Orchestrator is not installed at {install_dir}. Install now? [y/N]: "
            )
            if should_install:
                install_projects(
                    registry,
                    project_name,
                    force=False,
                    skip_install=False,
                    activate=False,
                    global_dir=global_dir,
                )
            else:
                fail(
                    f"Orchestrator install skipped. Run: warp-tools install {project_name}"
                )
        else:
            fail(
                f"Orchestrator project is not installed at {install_dir}. "
                f"Run: warp-tools install {project_name} "
                "or re-run with --auto-install."
            )

    if not python_binary.exists():
        if auto_install:
            print(
                f"Orchestrator virtualenv missing at {python_binary}. Repairing with update..."
            )
            install_projects(
                registry,
                project_name,
                force=True,
                skip_install=False,
                activate=False,
                global_dir=global_dir,
            )
        elif is_interactive_stdin():
            should_repair = confirm_action(
                "Orchestrator virtualenv is missing. Repair now with update? [y/N]: "
            )
            if should_repair:
                install_projects(
                    registry,
                    project_name,
                    force=True,
                    skip_install=False,
                    activate=False,
                    global_dir=global_dir,
                )
            else:
                fail("Orchestrator repair skipped. Run: warp-tools update orchestrator")
        else:
            fail(
                f"Orchestrator virtualenv not found at {python_binary}. "
                "Run: warp-tools update orchestrator "
                "or re-run with --auto-install."
            )

    if not python_binary.exists():
        fail(
            f"Orchestrator virtualenv not found at {python_binary}. "
            "Run: warp-tools update orchestrator"
        )
    return project_name, install_dir, python_binary
def run_orchestrator_plugin_script(
    *,
    install_dir: Path,
    python_binary: Path,
    script: str,
    env: dict[str, str],
) -> dict[str, Any]:
    result = subprocess.run(
        [str(python_binary), "-c", script],
        cwd=install_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        fail(
            "Plugin command failed.\\n"
            f"stdout:\\n{result.stdout}\\n"
            f"stderr:\\n{result.stderr}"
        )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        fail("Plugin command returned no output.")

    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        fail(
            f"Plugin command returned invalid JSON: {error}\\n"
            f"stdout:\\n{result.stdout}\\n"
            f"stderr:\\n{result.stderr}"
        )

    if not isinstance(payload, dict):
        fail("Plugin command returned an unexpected payload.")
    return payload


def register_plugin_command(
    registry: dict[str, Any],
    *,
    action: str,
    plugin_args: list[str],
    global_dir: Path,
    overwrite: bool,
    auto_install: bool,
) -> None:
    normalized_args = list(plugin_args)
    if normalized_args and normalized_args[0] == "--":
        normalized_args = normalized_args[1:]
    if not normalized_args:
        fail("Provide plugin arguments after 'warp-tools plugin add|install'.")
    project_name, install_dir, python_binary = ensure_orchestrator_ready(
        registry,
        global_dir=global_dir,
        auto_install=auto_install,
    )

    command_line = shlex.join(["claude", "plugin", action, *normalized_args])
    plugin_store = install_dir / ".warp-orchestrator.plugins.json"

    env = dict(os.environ)
    env["WARP_TOOLS_PLUGIN_COMMAND_LINE"] = command_line
    env["WARP_TOOLS_PLUGIN_OVERWRITE"] = "1" if overwrite else "0"
    env["WARP_ORCHESTRATOR_PLUGIN_STORE"] = str(plugin_store)
    payload = run_orchestrator_plugin_script(
        install_dir=install_dir,
        python_binary=python_binary,
        script=PLUGIN_REGISTRATION_SCRIPT,
        env=env,
    )
    if not payload.get("ok"):
        error_message = payload.get("error", "Plugin registration failed.")
        fail(str(error_message))

    plugin = payload.get("plugin")
    plugin_name = "unknown"
    if isinstance(plugin, dict):
        plugin_name = str(plugin.get("name", "unknown"))
    print(f"Registered plugin {plugin_name} in {project_name}")
    print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
def manage_plugin_store_command(
    registry: dict[str, Any],
    *,
    action: str,
    plugin_name: str | None,
    global_dir: Path,
    auto_install: bool,
    options: dict[str, Any] | None = None,
) -> None:
    project_name, install_dir, python_binary = ensure_orchestrator_ready(
        registry,
        global_dir=global_dir,
        auto_install=auto_install,
    )
    plugin_store = install_dir / ".warp-orchestrator.plugins.json"

    env = dict(os.environ)
    env["WARP_TOOLS_PLUGIN_ACTION"] = action
    env["WARP_ORCHESTRATOR_PLUGIN_STORE"] = str(plugin_store)
    if plugin_name:
        env["WARP_TOOLS_PLUGIN_NAME"] = plugin_name
    for key, value in dict(options or {}).items():
        if value is None:
            continue
        env[str(key)] = str(value)

    payload = run_orchestrator_plugin_script(
        install_dir=install_dir,
        python_binary=python_binary,
        script=PLUGIN_MANAGEMENT_SCRIPT,
        env=env,
    )
    if not payload.get("ok"):
        error_message = payload.get("error", "Plugin management command failed.")
        fail(str(error_message))

    if action in {"list", "integrations", "config-get", "marketplace-list"}:
        print(json.dumps(payload, indent=2))
        return
    if action == "remove":
        print(
            f"Removed plugin {payload.get('removed', plugin_name or 'unknown')} "
            f"from {project_name}"
        )
        print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
        return
    if action == "clear":
        print(f"Cleared plugin store in {project_name}")
        print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
        return
    if action in {"enable", "disable"}:
        state = "Enabled" if action == "enable" else "Disabled"
        print(f"{state} plugin {plugin_name or 'unknown'} in {project_name}")
        print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
        return
    if action in {"install-dir", "refresh", "config-set", "channel-config-set"}:
        plugin = payload.get("plugin")
        installed_name = plugin_name or "unknown"
        if isinstance(plugin, dict):
            installed_name = str(plugin.get("name", installed_name))
        if action == "install-dir":
            print(f"Installed plugin {installed_name} in {project_name}")
        elif action == "refresh":
            print(f"Refreshed plugin {installed_name} in {project_name}")
        elif action == "config-set":
            print(f"Updated user config for plugin {installed_name} in {project_name}")
        else:
            print(f"Updated channel config for plugin {installed_name} in {project_name}")
        print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
        return
    if action == "marketplace-add":
        marketplace = payload.get("marketplace")
        marketplace_name = plugin_name or "unknown"
        if isinstance(marketplace, dict):
            marketplace_name = str(marketplace.get("name", marketplace_name))
        print(f"Registered marketplace {marketplace_name} in {project_name}")
        print(
            "Marketplace store: "
            f"{payload.get('marketplaceStorePath', str(install_dir / '.warp-orchestrator.marketplaces.json'))}"
        )
        return
    if action in {"marketplace-install", "marketplace-update"}:
        plugin = payload.get("plugin")
        managed_name = plugin_name or "unknown"
        if isinstance(plugin, dict):
            managed_name = str(plugin.get("name", managed_name))
        verb = "Installed" if action == "marketplace-install" else "Updated"
        print(f"{verb} marketplace plugin {managed_name} in {project_name}")
        print(f"Plugin store: {payload.get('storePath', str(plugin_store))}")
        print(
            "Marketplace store: "
            f"{payload.get('marketplaceStorePath', str(install_dir / '.warp-orchestrator.marketplaces.json'))}"
        )
        return

    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="warp-tools")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list")

    def add_install_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("project_target")
        command_parser.add_argument(
            "--global-dir",
            default=str(DEFAULT_GLOBAL_DIR),
        )
        command_parser.add_argument("--force", action="store_true")
        command_parser.add_argument("--skip-install", action="store_true")
        activate_group = command_parser.add_mutually_exclusive_group()
        activate_group.add_argument("--activate", dest="activate", action="store_true")
        activate_group.add_argument(
            "--no-activate", dest="activate", action="store_false"
        )
        command_parser.set_defaults(activate=True)

    add_install_options(subparsers.add_parser("install"))
    add_install_options(subparsers.add_parser("update"))

    plugin_parser = subparsers.add_parser("plugin")
    plugin_parser.add_argument(
        "--global-dir",
        default=str(DEFAULT_GLOBAL_DIR),
    )
    overwrite_group = plugin_parser.add_mutually_exclusive_group()
    overwrite_group.add_argument("--overwrite", dest="overwrite", action="store_true")
    overwrite_group.add_argument(
        "--no-overwrite", dest="overwrite", action="store_false"
    )
    plugin_parser.set_defaults(overwrite=True)

    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_action")
    add_plugin_parser = plugin_subparsers.add_parser("add")
    add_plugin_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    add_plugin_parser.add_argument(
        "plugin_args",
        nargs=argparse.REMAINDER,
    )
    install_plugin_parser = plugin_subparsers.add_parser("install")
    install_plugin_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    install_plugin_parser.add_argument(
        "plugin_args",
        nargs=argparse.REMAINDER,
    )
    list_plugin_parser = plugin_subparsers.add_parser("list")
    list_plugin_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    remove_plugin_parser = plugin_subparsers.add_parser("remove")
    remove_plugin_parser.add_argument("name")
    remove_plugin_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    clear_plugin_parser = plugin_subparsers.add_parser("clear")
    clear_plugin_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    install_dir_parser = plugin_subparsers.add_parser("install-dir")
    install_dir_parser.add_argument("path")
    install_dir_parser.add_argument("--scope", default="user")
    install_dir_parser.add_argument("--disabled", action="store_true")
    install_dir_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    refresh_parser = plugin_subparsers.add_parser("refresh")
    refresh_parser.add_argument("name")
    refresh_parser.add_argument("--scope")
    refresh_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    enable_parser = plugin_subparsers.add_parser("enable")
    enable_parser.add_argument("name")
    enable_parser.add_argument("--scope")
    enable_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    disable_parser = plugin_subparsers.add_parser("disable")
    disable_parser.add_argument("name")
    disable_parser.add_argument("--scope")
    disable_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    config_set_parser = plugin_subparsers.add_parser("config-set")
    config_set_parser.add_argument("name")
    config_set_parser.add_argument("key")
    config_set_parser.add_argument("value")
    config_set_parser.add_argument("--scope")
    config_set_parser.add_argument("--sensitive", action="store_true")
    config_set_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    config_get_parser = plugin_subparsers.add_parser("config-get")
    config_get_parser.add_argument("name")
    config_get_parser.add_argument("--scope")
    config_get_parser.add_argument("--include-sensitive", action="store_true")
    config_get_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    channel_config_set_parser = plugin_subparsers.add_parser("channel-config-set")
    channel_config_set_parser.add_argument("name")
    channel_config_set_parser.add_argument("key")
    channel_config_set_parser.add_argument("value")
    channel_config_set_parser.add_argument("--scope")
    channel_config_set_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    integrations_parser = plugin_subparsers.add_parser("integrations")
    integrations_parser.add_argument("--scope")
    integrations_parser.add_argument("--include-disabled", action="store_true")
    integrations_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    marketplace_add_parser = plugin_subparsers.add_parser("marketplace-add")
    marketplace_add_parser.add_argument("name")
    marketplace_add_parser.add_argument("url")
    marketplace_add_parser.add_argument("--catalog-path")
    marketplace_add_parser.add_argument("--metadata-json")
    marketplace_add_parser.add_argument("--plugins-json")
    marketplace_add_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    marketplace_list_parser = plugin_subparsers.add_parser("marketplace-list")
    marketplace_list_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    marketplace_install_parser = plugin_subparsers.add_parser("marketplace-install")
    marketplace_install_parser.add_argument("marketplace")
    marketplace_install_parser.add_argument("name")
    marketplace_install_parser.add_argument("--scope", default="user")
    marketplace_install_parser.add_argument("--disabled", action="store_true")
    marketplace_install_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    marketplace_update_parser = plugin_subparsers.add_parser("marketplace-update")
    marketplace_update_parser.add_argument("name")
    marketplace_update_parser.add_argument("--scope")
    marketplace_update_parser.add_argument(
        "--auto-install",
        action="store_true",
    )
    remove_plugin_parser.add_argument("--scope")
    list_plugin_parser.add_argument("--scope")
    list_plugin_parser.add_argument("--include-disabled", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = load_registry()

    if args.command == "list":
        list_projects(registry)
        return

    if args.command in {"install", "update"}:
        global_dir = Path(args.global_dir).expanduser().resolve()
        force = bool(args.force)
        if args.command == "update":
            force = True
        install_projects(
            registry,
            args.project_target,
            force=force,
            skip_install=bool(args.skip_install),
            activate=bool(args.activate),
            global_dir=global_dir,
        )
        return

    if args.command == "plugin":
        global_dir = Path(args.global_dir).expanduser().resolve()
        auto_install = bool(getattr(args, "auto_install", False))
        if args.plugin_action in {"add", "install"}:
            register_plugin_command(
                registry,
                action=args.plugin_action,
                plugin_args=list(args.plugin_args),
                global_dir=global_dir,
                overwrite=bool(args.overwrite),
                auto_install=auto_install,
            )
            return
        if args.plugin_action == "list":
            manage_plugin_store_command(
                registry,
                action="list",
                plugin_name=None,
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                    "WARP_TOOLS_PLUGIN_INCLUDE_DISABLED": "1"
                    if bool(getattr(args, "include_disabled", False))
                    else "0",
                },
            )
            return
        if args.plugin_action == "remove":
            manage_plugin_store_command(
                registry,
                action="remove",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                },
            )
            return
        if args.plugin_action == "clear":
            manage_plugin_store_command(
                registry,
                action="clear",
                plugin_name=None,
                global_dir=global_dir,
                auto_install=auto_install,
            )
            return
        if args.plugin_action == "install-dir":
            manage_plugin_store_command(
                registry,
                action="install-dir",
                plugin_name=None,
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_DIR": str(getattr(args, "path", "")),
                    "WARP_TOOLS_PLUGIN_SCOPE": str(getattr(args, "scope", "user")),
                    "WARP_TOOLS_PLUGIN_ENABLED": "0"
                    if bool(getattr(args, "disabled", False))
                    else "1",
                    "WARP_TOOLS_PLUGIN_OVERWRITE": "1" if bool(args.overwrite) else "0",
                },
            )
            return
        if args.plugin_action == "refresh":
            manage_plugin_store_command(
                registry,
                action="refresh",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={"WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None)},
            )
            return
        if args.plugin_action in {"enable", "disable"}:
            manage_plugin_store_command(
                registry,
                action=args.plugin_action,
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={"WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None)},
            )
            return
        if args.plugin_action == "config-set":
            manage_plugin_store_command(
                registry,
                action="config-set",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                    "WARP_TOOLS_PLUGIN_KEY": str(getattr(args, "key", "")),
                    "WARP_TOOLS_PLUGIN_VALUE": str(getattr(args, "value", "")),
                    "WARP_TOOLS_PLUGIN_SENSITIVE": "1"
                    if bool(getattr(args, "sensitive", False))
                    else "",
                },
            )
            return
        if args.plugin_action == "config-get":
            manage_plugin_store_command(
                registry,
                action="config-get",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                    "WARP_TOOLS_PLUGIN_INCLUDE_SENSITIVE": "1"
                    if bool(getattr(args, "include_sensitive", False))
                    else "0",
                },
            )
            return
        if args.plugin_action == "channel-config-set":
            manage_plugin_store_command(
                registry,
                action="channel-config-set",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                    "WARP_TOOLS_PLUGIN_KEY": str(getattr(args, "key", "")),
                    "WARP_TOOLS_PLUGIN_VALUE": str(getattr(args, "value", "")),
                },
            )
            return
        if args.plugin_action == "integrations":
            manage_plugin_store_command(
                registry,
                action="integrations",
                plugin_name=None,
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None),
                    "WARP_TOOLS_PLUGIN_INCLUDE_DISABLED": "1"
                    if bool(getattr(args, "include_disabled", False))
                    else "0",
                },
            )
            return
        if args.plugin_action == "marketplace-add":
            manage_plugin_store_command(
                registry,
                action="marketplace-add",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_URL": str(getattr(args, "url", "")),
                    "WARP_TOOLS_PLUGIN_CATALOG_PATH": getattr(args, "catalog_path", None),
                    "WARP_TOOLS_PLUGIN_METADATA_JSON": getattr(args, "metadata_json", None),
                    "WARP_TOOLS_MARKETPLACE_PLUGINS_JSON": getattr(args, "plugins_json", None),
                    "WARP_TOOLS_PLUGIN_OVERWRITE": "1" if bool(args.overwrite) else "0",
                },
            )
            return
        if args.plugin_action == "marketplace-list":
            manage_plugin_store_command(
                registry,
                action="marketplace-list",
                plugin_name=None,
                global_dir=global_dir,
                auto_install=auto_install,
            )
            return
        if args.plugin_action == "marketplace-install":
            manage_plugin_store_command(
                registry,
                action="marketplace-install",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={
                    "WARP_TOOLS_PLUGIN_MARKETPLACE": str(getattr(args, "marketplace", "")),
                    "WARP_TOOLS_PLUGIN_SCOPE": str(getattr(args, "scope", "user")),
                    "WARP_TOOLS_PLUGIN_ENABLED": "0"
                    if bool(getattr(args, "disabled", False))
                    else "1",
                    "WARP_TOOLS_PLUGIN_OVERWRITE": "1" if bool(args.overwrite) else "0",
                },
            )
            return
        if args.plugin_action == "marketplace-update":
            manage_plugin_store_command(
                registry,
                action="marketplace-update",
                plugin_name=str(getattr(args, "name", "")),
                global_dir=global_dir,
                auto_install=auto_install,
                options={"WARP_TOOLS_PLUGIN_SCOPE": getattr(args, "scope", None)},
            )
            return
        fail(
            (
                "Use 'warp-tools plugin add|install|list|remove|clear|install-dir|refresh|"
                "enable|disable|config-set|config-get|channel-config-set|integrations|"
                "marketplace-add|marketplace-list|marketplace-install|marketplace-update ...'."
            )
        )
        return
    parser.print_help()


if __name__ == "__main__":
    main()
