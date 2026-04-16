#!/usr/bin/env python3
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def collect_dependency_versions():
    result = subprocess.run(
        ["npm", "ls", "--json", "--all", "--omit=dev"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout.strip() or result.stderr.strip()
    if not output:
        raise SystemExit("npm ls returned no output")

    root = json.loads(output)
    versions = {}

    def add(name, version):
        if not name or not version:
            return
        versions.setdefault(name, set()).add(version)

    def walk(node, node_name=None):
        if not isinstance(node, dict):
            return
        add(node_name or node.get("name"), node.get("version"))

        deps = node.get("dependencies")
        if isinstance(deps, dict):
            for dep_name, dep_node in deps.items():
                walk(dep_node, dep_name)
        elif isinstance(deps, list):
            for dep_node in deps:
                walk(dep_node)

    walk(root, root.get("name"))
    return {name: sorted(vset) for name, vset in versions.items() if name and vset}


def fetch_bulk_advisories(payload):
    req = urllib.request.Request(
        "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    payload = collect_dependency_versions()
    advisories = fetch_bulk_advisories(payload)

    if not isinstance(advisories, dict):
        raise SystemExit("Unexpected advisories response format")

    affected = []
    total = 0
    for pkg, package_advisories in advisories.items():
        if isinstance(package_advisories, list) and package_advisories:
            count = len(package_advisories)
            total += count
            affected.append((pkg, count))

    print(f"Packages submitted: {len(payload)}")
    print(f"Packages with advisories: {len(affected)}")
    print(f"Total advisories: {total}")

    if affected:
        print("\nTop affected packages:")
        for pkg, count in sorted(affected, key=lambda x: x[1], reverse=True)[:20]:
            print(f"- {pkg}: {count}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
