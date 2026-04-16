from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class WarpToolsUpdateCommandTests(unittest.TestCase):
    def test_update_command_is_available(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="warp-tools-update-"))
        env = os.environ.copy()
        source_path = str(REPO_ROOT)
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{source_path}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else source_path
        )

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    "update",
                    "orchestrator",
                    "--global-dir",
                    str(temp_dir),
                    "--skip-install",
                    "--no-activate",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected update command to succeed.\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}\n"
                ),
            )
            self.assertIn("Installing orchestrator", result.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
