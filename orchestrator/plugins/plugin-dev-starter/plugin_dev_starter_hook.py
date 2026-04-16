from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VALID_HOOK_TARGETS = {"preflight", "postflight"}


def plugin_store_path() -> Path:
    configured = os.environ.get(
        "WARP_ORCHESTRATOR_PLUGIN_STORE",
        ".warp-orchestrator.plugins.json",
    )
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def validate_plugin_record(name: str, record: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, dict):
        return [f"Plugin '{name}' must be an object."]

    command = record.get("command")
    if not isinstance(command, str) or not command.strip():
        problems.append(f"Plugin '{name}' must define a non-empty 'command' string.")

    targets = record.get("hookTargets")
    if not isinstance(targets, list) or len(targets) == 0:
        problems.append(f"Plugin '{name}' must define a non-empty 'hookTargets' array.")
    else:
        invalid = [target for target in targets if str(target).lower() not in VALID_HOOK_TARGETS]
        if invalid:
            problems.append(
                f"Plugin '{name}' has unsupported hook targets: {', '.join(map(str, invalid))}."
            )

    return problems


def validate_store(payload: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["Plugin store root must be a JSON object."]

    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return ["Plugin store must contain a 'plugins' object."]

    for name, record in plugins.items():
        problems.extend(validate_plugin_record(str(name), record))

    return problems


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--plugin-target", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _ = parse_args(argv)

    store_path = plugin_store_path()
    if not store_path.exists():
        return 0

    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"plugin-dev-starter: invalid plugin store JSON: {error}", file=sys.stderr)
        return 1

    problems = validate_store(payload)
    if problems:
        for problem in problems:
            print(f"plugin-dev-starter: {problem}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
