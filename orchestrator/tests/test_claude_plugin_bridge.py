from __future__ import annotations
import json

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import mcp_orchestrator


class ClaudePluginBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="warp-plugin-store-"))
        self.plugin_store = self.temp_dir / "plugins.json"
        self.plugin_secret_store = self.temp_dir / "plugin-secrets.json"
        self.marketplace_store = self.temp_dir / "marketplaces.json"
        self.previous_store = os.environ.get("WARP_ORCHESTRATOR_PLUGIN_STORE")
        self.previous_secret_store = os.environ.get("WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE")
        self.previous_marketplace_store = os.environ.get("WARP_ORCHESTRATOR_MARKETPLACE_STORE")
        os.environ["WARP_ORCHESTRATOR_PLUGIN_STORE"] = str(self.plugin_store)
        os.environ["WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE"] = str(self.plugin_secret_store)
        os.environ["WARP_ORCHESTRATOR_MARKETPLACE_STORE"] = str(self.marketplace_store)
        mcp_orchestrator.save_plugin_store({"plugins": {}})
        mcp_orchestrator.save_plugin_secret_store({"plugins": {}})
        mcp_orchestrator.save_marketplace_store({"marketplaces": {}})

    def tearDown(self) -> None:
        if self.previous_store is None:
            os.environ.pop("WARP_ORCHESTRATOR_PLUGIN_STORE", None)
        else:
            os.environ["WARP_ORCHESTRATOR_PLUGIN_STORE"] = self.previous_store
        if self.previous_secret_store is None:
            os.environ.pop("WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE", None)
        else:
            os.environ["WARP_ORCHESTRATOR_PLUGIN_SECRET_STORE"] = self.previous_secret_store
        if self.previous_marketplace_store is None:
            os.environ.pop("WARP_ORCHESTRATOR_MARKETPLACE_STORE", None)
        else:
            os.environ["WARP_ORCHESTRATOR_MARKETPLACE_STORE"] = self.previous_marketplace_store
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    def create_plugin_directory(
        self,
        *,
        directory_name: str,
        plugin_name: str,
        hook_command: str = "true",
        version: str = "0.1.0",
        user_config: dict[str, object] | None = None,
        mcp_servers: dict[str, object] | None = None,
        lsp_servers: dict[str, object] | None = None,
        channels: list[dict[str, object]] | None = None,
    ) -> Path:
        plugin_dir = self.temp_dir / directory_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, object] = {
            "name": plugin_name,
            "version": version,
            "orchestrator_hooks": {
                "preflight": {"command": hook_command},
            },
        }
        if user_config is not None:
            manifest["userConfig"] = user_config
        if mcp_servers is not None:
            manifest["mcpServers"] = mcp_servers
        if lsp_servers is not None:
            manifest["lspServers"] = lsp_servers
        if channels is not None:
            manifest["channels"] = channels
        (plugin_dir / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return plugin_dir
    def test_translate_claude_plugin_add_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin add lint-check --cmd true --hooks preflight"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "lint-check")
        self.assertEqual(translated["command"], "true")
        self.assertEqual(translated["hookTargets"], ["preflight"])
    def test_translate_claude_plugin_add_command_with_hook_options(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin add lint-check --cmd true --hooks preflight "
            "--if false --timeout 5 --once --async --status-message running --matcher pre*"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["if"], "false")
        self.assertEqual(translated["timeoutSeconds"], 5.0)
        self.assertTrue(translated["once"])
        self.assertTrue(translated["async"])
        self.assertEqual(translated["statusMessage"], "running")
        self.assertEqual(translated["matcher"], "pre*")

    def test_translate_claude_slash_plugins_add_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude /plugins add lint-check --command true --hooks pre,post"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "lint-check")
        self.assertEqual(translated["command"], "true")
        self.assertEqual(translated["hookTargets"], ["preflight", "postflight"])
    def test_translate_claude_plugin_install_plugin_dev_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin install plugin-dev@anthropics-claude-code --scope user"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "plugin-dev")
        self.assertEqual(translated["source"], "claude-plugin-install")
        self.assertIn("plugin_dev_starter_hook.py", translated["command"])
        self.assertEqual(translated["hookTargets"], ["preflight", "postflight"])
    def test_translate_claude_plugin_install_github_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin install github@claude-plugins-official --scope user"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "github")
        self.assertIn("github_starter_hook.py", translated["command"])
        self.assertEqual(translated["metadata"]["pluginTarget"], "github@claude-plugins-official")
        self.assertEqual(translated["metadata"]["adapterId"], "github-starter")
        self.assertIn("hookCommands", translated)
        self.assertIn("preflight", translated["hookCommands"])

    def test_translate_claude_plugin_install_github_marketplace_first(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin install --source @claude-plugins-official github --scope user"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "github")
        self.assertIn("github_starter_hook.py", translated["command"])
        self.assertEqual(translated["metadata"]["pluginTarget"], "github@claude-plugins-official")

    def test_translate_claude_plugin_install_unknown_requires_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin install my-custom-plugin@private-marketplace"
        )
        self.assertIsNone(translated)
        assert error is not None
        self.assertIn("Unsupported plugin install target", error)

    def test_translate_claude_plugin_install_unknown_with_command(self) -> None:
        translated, error = mcp_orchestrator.translate_claude_plugin_command(
            "claude plugin install my-custom-plugin@private-marketplace --cmd true"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(translated)
        assert translated is not None
        self.assertEqual(translated["name"], "my-custom-plugin")
        self.assertEqual(translated["command"], "true")

    async def test_default_plugin_is_bootstrapped(self) -> None:
        listed = await mcp_orchestrator.list_plugins()
        self.assertTrue(listed["ok"])
        names = {item["name"] for item in listed["plugins"]}
        self.assertIn("plugin-dev-starter", names)

    async def test_add_claude_plugin_persists_plugin_state(self) -> None:
        result = await mcp_orchestrator.add_claude_plugin(
            commandLine="claude plugin add post-check --cmd true --hook postflight"
        )
        self.assertTrue(result["ok"])
        listed = await mcp_orchestrator.list_plugins()
        self.assertTrue(listed["ok"])
        plugins_by_name = {item["name"]: item for item in listed["plugins"]}
        self.assertIn("post-check", plugins_by_name)
        self.assertIn("plugin-dev-starter", plugins_by_name)
        self.assertEqual(plugins_by_name["post-check"]["hookTargets"], ["postflight"])

    async def test_run_preflight_includes_registered_plugin_hook_commands(self) -> None:
        add_result = await mcp_orchestrator.add_claude_plugin(
            commandLine="claude plugin add hook-plugin --cmd true --hooks preflight"
        )
        self.assertTrue(add_result["ok"])

        report = await mcp_orchestrator.run_preflight(commands=["true"])
        self.assertTrue(report["succeeded"])
        self.assertGreaterEqual(report["pluginCommandsIncluded"], 2)
        self.assertGreaterEqual(len(report["results"]), 3)
        plugin_results = [item for item in report["results"] if item["source"] == "plugin"]
        names = {item["pluginName"] for item in plugin_results}
        self.assertIn("hook-plugin", names)
        self.assertIn("plugin-dev-starter", names)
    async def test_add_install_github_plugin_registers_adapter_command(self) -> None:
        result = await mcp_orchestrator.add_claude_plugin(
            commandLine="claude plugin install github@claude-plugins-official --scope user"
        )
        self.assertTrue(result["ok"])
        plugin = result["plugin"]
        self.assertEqual(plugin["name"], "github")
        self.assertIn("github_starter_hook.py", plugin["command"])
        self.assertEqual(
            plugin["metadata"]["referenceUrl"],
            "https://docs.anthropic.com/en/discover-plugins",
        )
    async def test_preflight_skips_plugin_when_condition_fails(self) -> None:
        record, error = mcp_orchestrator.upsert_plugin(
            {
                "name": "conditional-skip",
                "command": "true",
                "hookTargets": ["preflight"],
                "if": "false",
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(record)
        report = await mcp_orchestrator.run_preflight(commands=["true"])
        self.assertTrue(report["succeeded"])
        skipped = [
            item
            for item in report["results"]
            if item.get("pluginName") == "conditional-skip" and item.get("skipped")
        ]
        self.assertEqual(len(skipped), 1)

    async def test_preflight_removes_once_plugin_after_execution(self) -> None:
        record, error = mcp_orchestrator.upsert_plugin(
            {
                "name": "run-once",
                "command": "true",
                "hookTargets": ["preflight"],
                "once": True,
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(record)
        report = await mcp_orchestrator.run_preflight(commands=["true"])
        self.assertIn("run-once", report["removedOncePlugins"])
        listed = await mcp_orchestrator.list_plugins()
        names = {item["name"] for item in listed["plugins"]}
        self.assertNotIn("run-once", names)

    async def test_preflight_honors_hook_json_continue_false(self) -> None:
        record, error = mcp_orchestrator.upsert_plugin(
            {
                "name": "json-blocker",
                "command": (
                    "python3 -c \"import json; "
                    "print(json.dumps({'continue': False, 'stopReason': 'blocked'}))\""
                ),
                "hookTargets": ["preflight"],
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(record)
        report = await mcp_orchestrator.run_preflight(commands=["true"])
        self.assertFalse(report["succeeded"])
        blocker_results = [
            item for item in report["results"] if item.get("pluginName") == "json-blocker"
        ]
        self.assertEqual(len(blocker_results), 1)
        self.assertFalse(blocker_results[0]["ok"])
        self.assertEqual(blocker_results[0]["stopReason"], "blocked")

    async def test_preflight_async_plugin_is_launched(self) -> None:
        record, error = mcp_orchestrator.upsert_plugin(
            {
                "name": "async-plugin",
                "command": "true",
                "hookTargets": ["preflight"],
                "async": True,
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(record)
        report = await mcp_orchestrator.run_preflight(commands=["true"])
        async_results = [
            item for item in report["results"] if item.get("pluginName") == "async-plugin"
        ]
        self.assertEqual(len(async_results), 1)
        self.assertTrue(async_results[0]["ok"])
        self.assertTrue(async_results[0]["asyncLaunched"])

    async def test_install_plugin_directory_loads_components_and_scope(self) -> None:
        plugin_dir = self.create_plugin_directory(
            directory_name="local-plugin",
            plugin_name="local-plugin",
            hook_command="true",
            user_config={"mode": {"type": "string", "default": "safe"}},
        )
        result = await mcp_orchestrator.install_plugin_directory(
            pluginDir=str(plugin_dir),
            scope="project",
        )
        self.assertTrue(result["ok"])
        plugin = result["plugin"]
        self.assertEqual(plugin["name"], "local-plugin")
        self.assertEqual(plugin["scope"], "project")
        self.assertEqual(plugin["sourceType"], "directory")
        self.assertIn("components", plugin)
        self.assertIn("userConfig", plugin["components"])
        self.assertEqual(plugin["userConfigValues"]["mode"], "safe")

    async def test_scope_aware_enable_disable_and_remove(self) -> None:
        user_record, user_error = mcp_orchestrator.upsert_plugin(
            {
                "name": "scoped-plugin",
                "scope": "user",
                "command": "true",
                "hookTargets": ["preflight"],
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(user_error)
        self.assertIsNotNone(user_record)
        project_record, project_error = mcp_orchestrator.upsert_plugin(
            {
                "name": "scoped-plugin",
                "scope": "project",
                "command": "true",
                "hookTargets": ["preflight"],
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(project_error)
        self.assertIsNotNone(project_record)

        disable_result = await mcp_orchestrator.set_plugin_enabled(
            name="scoped-plugin",
            scope="project",
            enabled=False,
        )
        self.assertTrue(disable_result["ok"])
        self.assertFalse(disable_result["plugin"]["enabled"])

        listed = await mcp_orchestrator.list_plugins()
        scoped = [item for item in listed["plugins"] if item["name"] == "scoped-plugin"]
        self.assertEqual(len(scoped), 2)

        remove_project = await mcp_orchestrator.remove_plugin_by_name(
            name="scoped-plugin",
            scope="project",
        )
        self.assertTrue(remove_project["ok"])
        listed_after = await mcp_orchestrator.list_plugins()
        scoped_after = [item for item in listed_after["plugins"] if item["name"] == "scoped-plugin"]
        self.assertEqual(len(scoped_after), 1)
        self.assertEqual(scoped_after[0]["scope"], "user")

    async def test_user_config_sensitive_values_are_redacted_and_persisted_in_secret_store(self) -> None:
        plugin_dir = self.create_plugin_directory(
            directory_name="sensitive-plugin",
            plugin_name="sensitive-plugin",
            hook_command="echo ${user_config.apiToken}",
            user_config={"apiToken": {"type": "string", "sensitive": True}},
        )
        install_result = await mcp_orchestrator.install_plugin_directory(
            pluginDir=str(plugin_dir),
            scope="user",
        )
        self.assertTrue(install_result["ok"])

        set_result = await mcp_orchestrator.set_plugin_user_config(
            name="sensitive-plugin",
            key="apiToken",
            value="secret-value",
            sensitive=True,
        )
        self.assertTrue(set_result["ok"])

        redacted = await mcp_orchestrator.get_plugin_user_config(
            name="sensitive-plugin",
            includeSensitive=False,
        )
        self.assertTrue(redacted["ok"])
        self.assertEqual(redacted["config"]["values"]["apiToken"], "[redacted]")

        revealed = await mcp_orchestrator.get_plugin_user_config(
            name="sensitive-plugin",
            includeSensitive=True,
        )
        self.assertTrue(revealed["ok"])
        self.assertEqual(revealed["config"]["values"]["apiToken"], "secret-value")

        record_info = mcp_orchestrator.find_plugin_record("sensitive-plugin", "user")
        self.assertIsNotNone(record_info)
        assert record_info is not None
        record_key, _ = record_info
        secret_values = mcp_orchestrator.load_secret_values_for_record(record_key)
        self.assertEqual(secret_values.get("apiToken"), "secret-value")

    async def test_marketplace_install_and_update(self) -> None:
        plugin_dir = self.create_plugin_directory(
            directory_name="marketplace-plugin-v1",
            plugin_name="marketplace-plugin",
            hook_command="true",
            version="1.0.0",
        )
        register_result = await mcp_orchestrator.register_marketplace(
            name="local-market",
            url="file:///tmp/local-market",
            plugins={
                "marketplace-plugin": {
                    "path": str(plugin_dir),
                    "version": "1.0.0",
                }
            },
        )
        self.assertTrue(register_result["ok"])

        install_result = await mcp_orchestrator.install_marketplace_plugin(
            marketplace="local-market",
            plugin="marketplace-plugin",
            scope="user",
        )
        self.assertTrue(install_result["ok"])
        installed_plugin = install_result["plugin"]
        self.assertEqual(installed_plugin["sourceType"], "marketplace")
        self.assertEqual(installed_plugin["version"], "1.0.0")
        self.assertEqual(installed_plugin["metadata"]["marketplace"], "local-market")

        plugin_dir_v2 = self.create_plugin_directory(
            directory_name="marketplace-plugin-v2",
            plugin_name="marketplace-plugin",
            hook_command="true",
            version="1.1.0",
        )
        register_update = await mcp_orchestrator.register_marketplace(
            name="local-market",
            url="file:///tmp/local-market",
            plugins={
                "marketplace-plugin": {
                    "path": str(plugin_dir_v2),
                    "version": "1.1.0",
                }
            },
            overwrite=True,
        )
        self.assertTrue(register_update["ok"])
        update_result = await mcp_orchestrator.update_marketplace_plugin(
            name="marketplace-plugin",
            scope="user",
        )
        self.assertTrue(update_result["ok"])
        self.assertEqual(update_result["plugin"]["version"], "1.1.0")

    async def test_integration_surfaces_apply_channel_substitution(self) -> None:
        plugin_dir = self.create_plugin_directory(
            directory_name="integration-plugin",
            plugin_name="integration-plugin",
            hook_command="true",
            mcp_servers={
                "demo-mcp": {
                    "command": "echo ${channel_config.mode}",
                }
            },
            lsp_servers={
                "demo-lsp": {
                    "command": "echo lsp",
                }
            },
            channels=[
                {
                    "id": "default",
                    "description": "${channel_config.mode}",
                }
            ],
        )
        install_result = await mcp_orchestrator.install_plugin_directory(
            pluginDir=str(plugin_dir),
            scope="user",
        )
        self.assertTrue(install_result["ok"])
        channel_result = await mcp_orchestrator.set_plugin_channel_config(
            name="integration-plugin",
            key="mode",
            value="fast",
            scope="user",
        )
        self.assertTrue(channel_result["ok"])

        integrations = await mcp_orchestrator.list_plugin_integrations()
        self.assertTrue(integrations["ok"])
        payload = integrations["integrations"]
        self.assertIn("integration-plugin:demo-mcp", payload["mcpServers"])
        self.assertIn("integration-plugin:demo-lsp", payload["lspServers"])
        self.assertEqual(
            payload["mcpServers"]["integration-plugin:demo-mcp"]["command"],
            "echo fast",
        )
        channel_entries = [
            item
            for item in payload["channels"]
            if item.get("pluginName") == "integration-plugin"
        ]
        self.assertEqual(len(channel_entries), 1)
        self.assertEqual(channel_entries[0]["description"], "fast")

    async def test_run_hook_event_executes_non_preflight_targets(self) -> None:
        record, error = mcp_orchestrator.upsert_plugin(
            {
                "name": "session-plugin",
                "scope": "user",
                "command": "true",
                "hookTargets": ["sessionstart"],
                "source": "test",
                "sourceCommandLine": "test",
            },
            overwrite=True,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(record)

        result = await mcp_orchestrator.run_hook_event(
            eventName="session_start",
            commands=["true"],
        )
        self.assertTrue(result["succeeded"])
        plugin_results = [
            item for item in result["results"] if item.get("pluginName") == "session-plugin"
        ]
        self.assertEqual(len(plugin_results), 1)


if __name__ == "__main__":
    unittest.main()
