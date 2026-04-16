from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PYTHON_STUB_SCRIPT = """#!/usr/bin/env python3
import json
import os

action = os.environ.get("WARP_TOOLS_PLUGIN_ACTION", "")
if action:
    plugin_name = os.environ.get("WARP_TOOLS_PLUGIN_NAME", "test-plugin")
    if action == "list":
        print(
            json.dumps(
                {
                    "ok": True,
                    "storePath": os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE", ""),
                    "count": 1,
                    "plugins": [{"name": "plugin-dev-starter"}],
                }
            )
        )
    elif action == "remove":
        print(
            json.dumps(
                {
                    "ok": True,
                    "storePath": os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE", ""),
                    "removed": os.environ.get("WARP_TOOLS_PLUGIN_NAME", ""),
                }
            )
        )
    elif action == "clear":
        print(
            json.dumps(
                {
                    "ok": True,
                    "storePath": os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE", ""),
                    "cleared": True,
                }
            )
        )
    elif action in {"enable", "disable", "install-dir", "refresh", "config-set", "channel-config-set", "marketplace-install", "marketplace-update"}:
        print(
            json.dumps(
                {
                    "ok": True,
                    "storePath": os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE", ""),
                    "marketplaceStorePath": os.environ.get("WARP_ORCHESTRATOR_MARKETPLACE_STORE", ""),
                    "plugin": {"name": plugin_name},
                }
            )
        )
    elif action == "config-get":
        print(
            json.dumps(
                {
                    "ok": True,
                    "config": {
                        "plugin": plugin_name,
                        "values": {"mode": "safe"},
                    },
                }
            )
        )
    elif action == "integrations":
        print(
            json.dumps(
                {
                    "ok": True,
                    "integrations": {"mcpServers": {}, "lspServers": {}, "channels": []},
                }
            )
        )
    elif action == "marketplace-add":
        print(
            json.dumps(
                {
                    "ok": True,
                    "marketplaceStorePath": os.environ.get("WARP_ORCHESTRATOR_MARKETPLACE_STORE", ""),
                    "marketplace": {"name": plugin_name},
                }
            )
        )
    elif action == "marketplace-list":
        print(
            json.dumps(
                {
                    "ok": True,
                    "marketplaces": [{"name": "demo-market"}],
                }
            )
        )
    else:
        print(json.dumps({"ok": False, "error": f"unknown action: {action}"}))
    raise SystemExit(0)

expected = os.environ.get("EXPECTED_CLAUDE_PLUGIN_COMMAND", "")
actual = os.environ.get("WARP_TOOLS_PLUGIN_COMMAND_LINE", "")

if actual != expected:
    print(json.dumps({"ok": False, "error": f"unexpected command line: {actual}"}))
    raise SystemExit(0)

print(
    json.dumps(
        {
            "ok": True,
            "storePath": os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE", ""),
            "plugin": {"name": os.environ.get("EXPECTED_PLUGIN_NAME", "test-plugin")},
        }
    )
)
"""


class WarpToolsPluginCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="warp-tools-plugin-"))
        install_dir = self.temp_dir / "projects" / "orchestrator"
        python_path = install_dir / ".venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True, exist_ok=True)
        python_path.write_text(PYTHON_STUB_SCRIPT, encoding="utf-8")
        python_path.chmod(
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH
        )

        self.env = os.environ.copy()
        source_path = str(REPO_ROOT)
        existing_pythonpath = self.env.get("PYTHONPATH")
        self.env["PYTHONPATH"] = (
            f"{source_path}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else source_path
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plugin_install_command_registers_in_orchestrator(self) -> None:
        self.env["EXPECTED_CLAUDE_PLUGIN_COMMAND"] = (
            "claude plugin install github@claude-plugins-official --scope user"
        )
        self.env["EXPECTED_PLUGIN_NAME"] = "github"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "install",
                "--auto-install",
                "github@claude-plugins-official",
                "--scope",
                "user",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected plugin install command to succeed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
            ),
        )
        self.assertIn("Registered plugin github in orchestrator", result.stdout)

    def test_plugin_add_command_registers_in_orchestrator(self) -> None:
        self.env["EXPECTED_CLAUDE_PLUGIN_COMMAND"] = (
            "claude plugin add lint-check --cmd true --hooks preflight"
        )
        self.env["EXPECTED_PLUGIN_NAME"] = "lint-check"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "add",
                "lint-check",
                "--cmd",
                "true",
                "--hooks",
                "preflight",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected plugin add command to succeed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
            ),
        )
        self.assertIn("Registered plugin lint-check in orchestrator", result.stdout)

    def test_plugin_missing_orchestrator_recommends_auto_install(self) -> None:
        shutil.rmtree(self.temp_dir / "projects" / "orchestrator", ignore_errors=True)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "add",
                "lint-check",
                "--cmd",
                "true",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--auto-install", result.stderr)
        self.assertIn("warp-tools install orchestrator", result.stderr)
    def test_plugin_list_command_reads_orchestrator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "list",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('"count": 1', result.stdout)

    def test_plugin_remove_command_routes_to_orchestrator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "remove",
                "lint-check",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Removed plugin lint-check from orchestrator", result.stdout)

    def test_plugin_clear_command_routes_to_orchestrator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "clear",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Cleared plugin store in orchestrator", result.stdout)

    def test_plugin_enable_command_routes_to_orchestrator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "enable",
                "lint-check",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Enabled plugin lint-check in orchestrator", result.stdout)

    def test_plugin_install_dir_command_routes_to_orchestrator(self) -> None:
        self.env["WARP_TOOLS_PLUGIN_NAME"] = "dir-plugin"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "install-dir",
                str(self.temp_dir / "dummy-plugin"),
                "--scope",
                "project",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Installed plugin dir-plugin in orchestrator", result.stdout)

    def test_plugin_config_get_command_routes_to_orchestrator(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "config-get",
                "lint-check",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('"plugin": "lint-check"', result.stdout)

    def test_plugin_marketplace_install_command_routes_to_orchestrator(self) -> None:
        self.env["WARP_TOOLS_PLUGIN_NAME"] = "market-plugin"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                "plugin",
                "--global-dir",
                str(self.temp_dir),
                "marketplace-install",
                "demo-market",
                "market-plugin",
                "--scope",
                "user",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            input="",
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "Installed marketplace plugin market-plugin in orchestrator",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
