from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import cli.main as cli_main


class WarpToolsPluginReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.global_dir = Path(tempfile.mkdtemp(prefix="warp-tools-readiness-"))
        self.registry = {
            "projects": {
                "orchestrator": {
                    "install_path": "projects/orchestrator",
                }
            }
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.global_dir, ignore_errors=True)

    def _stub_install_creates_python(self, *_args: object, **_kwargs: object) -> None:
        python_binary = self.global_dir / "projects" / "orchestrator" / ".venv" / "bin" / "python"
        python_binary.parent.mkdir(parents=True, exist_ok=True)
        python_binary.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    def test_auto_install_triggers_install_when_orchestrator_missing(self) -> None:
        with mock.patch(
            "cli.main.install_projects",
            side_effect=self._stub_install_creates_python,
        ) as install_mock:
            project_name, install_dir, python_binary = cli_main.ensure_orchestrator_ready(
                self.registry,
                global_dir=self.global_dir,
                auto_install=True,
            )
        self.assertEqual(project_name, "orchestrator")
        self.assertEqual(install_dir, self.global_dir / "projects" / "orchestrator")
        self.assertTrue(python_binary.exists())
        install_mock.assert_called_once_with(
            self.registry,
            "orchestrator",
            force=False,
            skip_install=False,
            activate=False,
            global_dir=self.global_dir,
        )

    def test_prompt_yes_triggers_install_when_orchestrator_missing(self) -> None:
        with (
            mock.patch("cli.main.is_interactive_stdin", return_value=True),
            mock.patch("cli.main.confirm_action", return_value=True),
            mock.patch(
                "cli.main.install_projects",
                side_effect=self._stub_install_creates_python,
            ) as install_mock,
        ):
            cli_main.ensure_orchestrator_ready(
                self.registry,
                global_dir=self.global_dir,
                auto_install=False,
            )
        install_mock.assert_called_once_with(
            self.registry,
            "orchestrator",
            force=False,
            skip_install=False,
            activate=False,
            global_dir=self.global_dir,
        )

    def test_prompt_no_aborts_when_orchestrator_missing(self) -> None:
        with (
            mock.patch("cli.main.is_interactive_stdin", return_value=True),
            mock.patch("cli.main.confirm_action", return_value=False),
        ):
            with self.assertRaises(SystemExit):
                cli_main.ensure_orchestrator_ready(
                    self.registry,
                    global_dir=self.global_dir,
                    auto_install=False,
                )

    def test_auto_install_repairs_missing_virtualenv(self) -> None:
        install_dir = self.global_dir / "projects" / "orchestrator"
        install_dir.mkdir(parents=True, exist_ok=True)
        with mock.patch(
            "cli.main.install_projects",
            side_effect=self._stub_install_creates_python,
        ) as install_mock:
            cli_main.ensure_orchestrator_ready(
                self.registry,
                global_dir=self.global_dir,
                auto_install=True,
            )
        install_mock.assert_called_once_with(
            self.registry,
            "orchestrator",
            force=True,
            skip_install=False,
            activate=False,
            global_dir=self.global_dir,
        )

    def test_non_interactive_missing_orchestrator_mentions_auto_install(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch("cli.main.is_interactive_stdin", return_value=False),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit):
                cli_main.ensure_orchestrator_ready(
                    self.registry,
                    global_dir=self.global_dir,
                    auto_install=False,
                )
        self.assertIn("--auto-install", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
