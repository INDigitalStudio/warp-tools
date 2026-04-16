from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

VALID_HOOK_TARGETS = {"preflight", "postflight"}
GITHUB_PLUGIN_ALIASES = {"github", "github-plugin", "github-integration", "github-starter"}


def plugin_store_path() -> Path:
    configured = os.environ.get(
        "WARP_ORCHESTRATOR_PLUGIN_STORE",
        ".warp-orchestrator.plugins.json",
    )
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def infer_plugin_name_from_target(plugin_target: str) -> str | None:
    cleaned = plugin_target.strip()
    if not cleaned:
        return None
    if cleaned.startswith("@"):
        return None
    if "@" in cleaned:
        return cleaned.split("@", 1)[0].strip() or None
    return cleaned


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


def read_store_payload(path: Path) -> tuple[dict[str, object] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"invalid plugin store JSON: {error}"
    if not isinstance(payload, dict):
        return None, "plugin store root must be an object."
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return None, "plugin store must contain a 'plugins' object."
    return payload, None


def run_command(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_git_remote() -> dict[str, object]:
    rc, stdout, _ = run_command(["git", "rev-parse", "--is-inside-work-tree"])
    if rc != 0 or stdout != "true":
        return {"insideRepo": False, "originRemote": "", "githubRemote": False}

    rc, origin_remote, _ = run_command(["git", "config", "--get", "remote.origin.url"])
    origin = origin_remote if rc == 0 else ""
    github_remote = "github.com" in origin or origin.startswith("git@github.com:")
    return {
        "insideRepo": True,
        "originRemote": origin,
        "githubRemote": github_remote,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--plugin-target", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_name = infer_plugin_name_from_target(args.plugin_target)

    payload, error = read_store_payload(plugin_store_path())
    if error:
        print(f"github-starter: {error}", file=sys.stderr)
        return 1
    if payload is None:
        return 0

    plugins = payload.get("plugins")
    assert isinstance(plugins, dict)

    for plugin_name, plugin_record in plugins.items():
        normalized = str(plugin_name).strip().lower()
        if normalized in GITHUB_PLUGIN_ALIASES:
            problems = validate_plugin_record(str(plugin_name), plugin_record)
            if problems:
                for problem in problems:
                    print(f"github-starter: {problem}", file=sys.stderr)
                return 1

    if target_name and target_name.lower() in GITHUB_PLUGIN_ALIASES:
        git_state = check_git_remote()
        if bool(git_state["insideRepo"]) and not bool(git_state["githubRemote"]):
            print(
                "github-starter: repository is not configured with a GitHub origin remote.",
                file=sys.stderr,
            )

        if not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
            print(
                "github-starter: GH_TOKEN/GITHUB_TOKEN not set; GitHub API features may be limited.",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
