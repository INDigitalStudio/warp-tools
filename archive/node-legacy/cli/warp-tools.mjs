#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
const __filename = realpathSync(fileURLToPath(import.meta.url));
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const registryPath = path.join(repoRoot, "projects.registry.json");

function fail(message, code = 1) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

function updateProjects(registry, projectTarget, options) {
  const updateOptions = { ...options, force: true };
  installProjects(registry, projectTarget, updateOptions);
}

function loadJson(filePath) {
  if (!existsSync(filePath)) {
    return null;
  }

  try {
    return JSON.parse(readFileSync(filePath, "utf8"));
  } catch (error) {
    fail(`Invalid JSON in ${filePath}: ${error.message}`);
  }
}

function saveJson(filePath, value) {
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function loadRegistry() {
  const registry = loadJson(registryPath);
  if (!registry || !registry.projects || typeof registry.projects !== "object") {
    fail(`Project registry missing or invalid: ${registryPath}`);
  }
  return registry;
}

function parseOptions(args) {
  const options = {
    force: false,
    skipInstall: false,
    activate: true,
    globalDir: path.join(os.homedir(), ".config", "warp")
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--force") {
      options.force = true;
    } else if (arg === "--skip-install") {
      options.skipInstall = true;
    } else if (arg === "--no-activate") {
      options.activate = false;
    } else if (arg === "--activate") {
      options.activate = true;
    } else if (arg === "--global-dir") {
      const value = args[i + 1];
      if (!value) {
        fail("--global-dir requires a path value");
      }
      options.globalDir = path.resolve(value);
      i += 1;
    } else {
      fail(`Unknown option: ${arg}`);
    }
  }

  return options;
}

function printHelp() {
  const message = [
    "warp-tools",
    "",
    "Commands:",
    "  warp-tools list",
    "  warp-tools install <project|all> [--global-dir <path>] [--force] [--skip-install] [--activate|--no-activate]",
    "  warp-tools update <project|all> [--global-dir <path>] [--skip-install] [--activate|--no-activate]",
    "",
    "Notes:",
    "  - default global tools directory: ~/.config/warp",
    "  - install copies project sources from this CLI app into <global-dir>/projects",
    "  - activate updates ~/.warp/.mcp.json with installed MCP servers"
  ].join("\n");
  process.stdout.write(`${message}\n`);
}

function listProjects(registry) {
  const names = Object.keys(registry.projects).sort();
  if (names.length === 0) {
    process.stdout.write("No projects found.\n");
    return;
  }

  for (const name of names) {
    const project = registry.projects[name];
    process.stdout.write(`- ${name} -> ${project.source}\n`);
  }
}

function runCommand(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell: false
  });

  if (result.status !== 0) {
    const display = [command, ...args].join(" ");
    fail(`Command failed (${display}) in ${cwd}`);
  }
}

function copyProjectDirectory(sourceDir, destinationDir, force) {
  if (!existsSync(sourceDir)) {
    fail(`Source project directory not found: ${sourceDir}`);
  }

  if (existsSync(destinationDir)) {
    if (!force) {
      fail(`Destination exists: ${destinationDir} (use --force to replace)`);
    }
    rmSync(destinationDir, { recursive: true, force: true });
  }

  mkdirSync(path.dirname(destinationDir), { recursive: true });
  cpSync(sourceDir, destinationDir, {
    recursive: true,
    filter: (sourcePath) => {
      const basename = path.basename(sourcePath);
      if (basename === "node_modules" || basename === ".git" || basename === ".DS_Store") {
        return false;
      }
      return true;
    }
  });
}

function resolveMcpServerEntries(project, globalDir, installAbsolutePath) {
  const entries = {};
  const raw = project.mcp_servers || {};

  for (const [serverName, serverConfig] of Object.entries(raw)) {
    const args = (serverConfig.args || []).map((value) =>
      String(value).replaceAll("${GLOBAL_DIR}", globalDir).replaceAll("${INSTALL_PATH}", installAbsolutePath)
    );
    const workingDirectory = String(serverConfig.working_directory || globalDir)
      .replaceAll("${GLOBAL_DIR}", globalDir)
      .replaceAll("${INSTALL_PATH}", installAbsolutePath);

    entries[serverName] = {
      command: serverConfig.command,
      args,
      working_directory: workingDirectory
    };
  }

  return entries;
}

function getServerMap(config) {
  if (config && typeof config === "object") {
    if (config.mcpServers && typeof config.mcpServers === "object") {
      return { container: config.mcpServers, setter: (map) => (config.mcpServers = map) };
    }
    if (config.mcp_servers && typeof config.mcp_servers === "object") {
      return { container: config.mcp_servers, setter: (map) => (config.mcp_servers = map) };
    }
    if (config.servers && typeof config.servers === "object") {
      return { container: config.servers, setter: (map) => (config.servers = map) };
    }
    if (
      config.mcp &&
      typeof config.mcp === "object" &&
      config.mcp.servers &&
      typeof config.mcp.servers === "object"
    ) {
      return { container: config.mcp.servers, setter: (map) => (config.mcp.servers = map) };
    }
  }
  return null;
}

function mergeMcpServers(filePath, serverEntries) {
  const existing = loadJson(filePath) || {};
  const serverMapInfo = getServerMap(existing);

  if (serverMapInfo) {
    const merged = { ...serverMapInfo.container, ...serverEntries };
    serverMapInfo.setter(merged);
    saveJson(filePath, existing);
    return;
  }

  saveJson(filePath, { mcpServers: serverEntries });
}

function installProjects(registry, projectTarget, options) {
  const allNames = Object.keys(registry.projects).sort();
  const selectedNames = projectTarget === "all" ? allNames : [projectTarget];

  for (const name of selectedNames) {
    if (!registry.projects[name]) {
      fail(`Unknown project: ${name}`);
    }
  }

  const globalDir = path.resolve(options.globalDir);
  const globalMcpConfig = path.join(globalDir, ".mcp.json");
  const installedServerEntries = {};

  for (const name of selectedNames) {
    const project = registry.projects[name];
    const sourceDir = path.join(repoRoot, project.source);
    const installRelativePath = project.install_path;
    const destinationDir = path.join(globalDir, installRelativePath);

    process.stdout.write(`Installing ${name} -> ${destinationDir}\n`);
    copyProjectDirectory(sourceDir, destinationDir, options.force);

    if (project.install_dependencies && !options.skipInstall) {
      runCommand("npm", ["install", "--omit=dev"], destinationDir);

      if (project.audit_script) {
        runCommand("npm", ["run", project.audit_script], destinationDir);
      }
    }

    const projectServerEntries = resolveMcpServerEntries(project, globalDir, destinationDir);
    Object.assign(installedServerEntries, projectServerEntries);
  }

  mergeMcpServers(globalMcpConfig, installedServerEntries);
  process.stdout.write(`Updated global config: ${globalMcpConfig}\n`);

  if (options.activate) {
    const warpMcpConfig = path.join(os.homedir(), ".warp", ".mcp.json");
    mergeMcpServers(warpMcpConfig, installedServerEntries);
    process.stdout.write(`Updated Warp config: ${warpMcpConfig}\n`);
  }
}

function main() {
  const [, , command, ...rest] = process.argv;
  const registry = loadRegistry();

  if (!command || command === "help" || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  if (command === "list") {
    if (rest.length > 0) {
      fail("list does not accept arguments");
    }
    listProjects(registry);
    return;
  }

  if (command === "install") {
    const [projectTarget, ...optionArgs] = rest;
    if (!projectTarget) {
      fail("install requires a project name or 'all'");
    }
    const options = parseOptions(optionArgs);
    installProjects(registry, projectTarget, options);
    return;
  }

  if (command === "update") {
    const [projectTarget, ...optionArgs] = rest;
    if (!projectTarget) {
      fail("update requires a project name or 'all'");
    }
    const options = parseOptions(optionArgs);
    updateProjects(registry, projectTarget, options);
    return;
  }

  fail(`Unknown command: ${command}`);
}

main();
