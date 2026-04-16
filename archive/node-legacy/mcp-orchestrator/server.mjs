import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const tasks = new Map();
const batches = new Map();

function nowIso() {
  return new Date().toISOString();
}

function taskView(task) {
  return {
    id: task.id,
    batchId: task.batchId,
    name: task.name,
    status: task.status,
    command: task.command,
    cwd: task.cwd,
    startedAt: task.startedAt,
    endedAt: task.endedAt,
    exitCode: task.exitCode,
    signal: task.signal,
    stdout: task.stdout,
    stderr: task.stderr,
    error: task.error
  };
}

function textResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2)
      }
    ]
  };
}

function spawnShell({ command, cwd, env }) {
  return new Promise((resolve) => {
    const child = spawn("zsh", ["-lc", command], {
      cwd: cwd || process.cwd(),
      env: { ...process.env, ...(env || {}) }
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      resolve({
        ok: false,
        exitCode: null,
        signal: null,
        stdout,
        stderr,
        error: error.message
      });
    });

    child.on("close", (exitCode, signal) => {
      resolve({
        ok: exitCode === 0,
        exitCode,
        signal,
        stdout,
        stderr,
        error: null
      });
    });
  });
}

async function launchTask(task) {
  task.status = "running";
  task.startedAt = nowIso();

  const result = await spawnShell({
    command: task.command,
    cwd: task.cwd,
    env: task.env
  });

  task.stdout = result.stdout;
  task.stderr = result.stderr;
  task.exitCode = result.exitCode;
  task.signal = result.signal;
  task.error = result.error;
  task.endedAt = nowIso();
  task.status = result.ok ? "succeeded" : "failed";
}

async function runCommandSequence({ name, commands, cwd, stopOnError }) {
  const startedAt = nowIso();
  const results = [];
  let succeeded = true;

  for (const command of commands) {
    const result = await spawnShell({ command, cwd });
    results.push({
      command,
      ok: result.ok,
      exitCode: result.exitCode,
      signal: result.signal,
      stdout: result.stdout,
      stderr: result.stderr,
      error: result.error
    });
    if (!result.ok) {
      succeeded = false;
      if (stopOnError) {
        break;
      }
    }
  }

  return {
    hook: name,
    cwd: cwd || process.cwd(),
    startedAt,
    endedAt: nowIso(),
    succeeded,
    results
  };
}

const server = new McpServer(
  {
    name: "warp-orchestrator",
    version: "0.1.0"
  },
  {
    instructions:
      "Use this server to emulate subagent-like fanout and hook-like pre/post checks. Dispatch independent tasks, poll status, and collect batch results."
  }
);

server.registerTool(
  "dispatch_tasks",
  {
    title: "Dispatch tasks",
    description:
      "Dispatch shell tasks as parallel workers (subagent-like fanout) and optionally wait for completion.",
    inputSchema: z.object({
      tasks: z
        .array(
          z.object({
            name: z.string(),
            command: z.string(),
            cwd: z.string().optional(),
            env: z.record(z.string()).optional()
          })
        )
        .min(1),
      parallel: z.boolean().default(true),
      waitForCompletion: z.boolean().default(false)
    })
  },
  async ({ tasks: taskInputs, parallel, waitForCompletion }) => {
    const batchId = randomUUID();
    const created = taskInputs.map((input) => {
      const id = randomUUID();
      const task = {
        id,
        batchId,
        name: input.name,
        command: input.command,
        cwd: input.cwd || process.cwd(),
        env: input.env || {},
        status: "queued",
        startedAt: null,
        endedAt: null,
        exitCode: null,
        signal: null,
        stdout: "",
        stderr: "",
        error: null
      };
      tasks.set(id, task);
      return task;
    });

    batches.set(
      batchId,
      created.map((t) => t.id)
    );

    const launches = created.map((task) => () => launchTask(task));

    if (waitForCompletion) {
      if (parallel) {
        await Promise.all(launches.map((run) => run()));
      } else {
        for (const run of launches) {
          await run();
        }
      }
    } else if (parallel) {
      launches.forEach((run) => {
        run().catch(() => {});
      });
    } else {
      (async () => {
        for (const run of launches) {
          await run();
        }
      })().catch(() => {});
    }

    return textResult({
      batchId,
      waitForCompletion,
      parallel,
      tasks: created.map(taskView)
    });
  }
);

server.registerTool(
  "task_status",
  {
    title: "Task status",
    description:
      "Get status for one task or all tasks in a batch. Provide either taskId or batchId.",
    inputSchema: z.object({
      taskId: z.string().optional(),
      batchId: z.string().optional()
    })
  },
  async ({ taskId, batchId }) => {
    if (!taskId && !batchId) {
      return textResult({
        ok: false,
        error: "Provide taskId or batchId."
      });
    }

    if (taskId) {
      const task = tasks.get(taskId);
      if (!task) {
        return textResult({
          ok: false,
          error: `Task not found: ${taskId}`
        });
      }
      return textResult({
        ok: true,
        task: taskView(task)
      });
    }

    const taskIds = batches.get(batchId) || [];
    return textResult({
      ok: taskIds.length > 0,
      batchId,
      tasks: taskIds.map((id) => taskView(tasks.get(id))).filter(Boolean)
    });
  }
);

server.registerTool(
  "collect_results",
  {
    title: "Collect batch results",
    description:
      "Collect summarized results for all tasks in a batch, with optional filtering for completed tasks only.",
    inputSchema: z.object({
      batchId: z.string(),
      completedOnly: z.boolean().default(false)
    })
  },
  async ({ batchId, completedOnly }) => {
    const taskIds = batches.get(batchId);
    if (!taskIds) {
      return textResult({
        ok: false,
        error: `Batch not found: ${batchId}`
      });
    }

    const allTasks = taskIds
      .map((id) => tasks.get(id))
      .filter(Boolean)
      .map(taskView);

    const filtered = completedOnly
      ? allTasks.filter((t) => t.status === "succeeded" || t.status === "failed")
      : allTasks;

    const statusCounts = filtered.reduce(
      (acc, task) => {
        acc[task.status] = (acc[task.status] || 0) + 1;
        return acc;
      },
      {}
    );

    return textResult({
      ok: true,
      batchId,
      completedOnly,
      total: filtered.length,
      statusCounts,
      tasks: filtered
    });
  }
);

server.registerTool(
  "run_preflight",
  {
    title: "Run preflight",
    description:
      "Run command checks before dispatching work (hook-like pre-step).",
    inputSchema: z.object({
      commands: z.array(z.string()).min(1),
      cwd: z.string().optional(),
      stopOnError: z.boolean().default(true)
    })
  },
  async ({ commands, cwd, stopOnError }) => {
    const report = await runCommandSequence({
      name: "preflight",
      commands,
      cwd,
      stopOnError
    });
    return textResult(report);
  }
);

server.registerTool(
  "run_postflight",
  {
    title: "Run postflight",
    description:
      "Run command checks after task execution (hook-like post-step).",
    inputSchema: z.object({
      commands: z.array(z.string()).min(1),
      cwd: z.string().optional(),
      stopOnError: z.boolean().default(true)
    })
  },
  async ({ commands, cwd, stopOnError }) => {
    const report = await runCommandSequence({
      name: "postflight",
      commands,
      cwd,
      stopOnError
    });
    return textResult(report);
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
