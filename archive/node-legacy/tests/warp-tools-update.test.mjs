import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const cliPath = "/Users/ima/ws/warp/cli/warp-tools.mjs";

test("warp-tools update command is available", () => {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "warp-tools-update-"));

  try {
    const result = spawnSync(
      "node",
      [
        cliPath,
        "update",
        "mcp-orchestrator",
        "--global-dir",
        tempDir,
        "--skip-install",
        "--no-activate"
      ],
      { encoding: "utf8" }
    );

    assert.equal(
      result.status,
      0,
      `Expected update command to succeed.\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`
    );
    assert.match(result.stdout, /Installing mcp-orchestrator/);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});
