#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path


def load_plan(plan_path: Path | None, repo_root: Path) -> dict:
    if plan_path:
        return json.loads(plan_path.read_text(encoding="utf-8"))

    state_path = repo_root / "config" / "console" / "plugins.json"
    server_path = repo_root / "config" / "console" / "servers.json"
    if state_path.exists() and server_path.exists():
        plugins_state = json.loads(state_path.read_text(encoding="utf-8"))
        servers_state = json.loads(server_path.read_text(encoding="utf-8"))
        catalog = {entry["plugin_id"]: entry for entry in plugins_state["catalog"]}
        plans = {"proxy": [], "lobby": [], "survival": [], "creative": []}
        for bundle_name, plugin_ids in plugins_state["bundles"].items():
            if bundle_name.startswith("proxy"):
                plans["proxy"].extend(catalog[plugin_id] for plugin_id in plugin_ids if plugin_id in catalog)
        for profile_name, profile in servers_state["profiles"].items():
            resolved = []
            for bundle_name in profile.get("plugin_bundles", []):
                resolved.extend(catalog[plugin_id] for plugin_id in plugins_state["bundles"].get(bundle_name, []) if plugin_id in catalog)
            deduped = list({entry["plugin_id"]: entry for entry in resolved}.values())
            plans[profile_name] = deduped
        return {"plans": plans}

    manifest_path = repo_root / "plugins" / "manifest.csv"
    plans = {"proxy": [], "lobby": [], "survival": [], "creative": []}
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            targets = [row["install_target"]]
            if row["install_target"] == "all-paper":
                targets = ["lobby", "survival", "creative"]
            for target in targets:
                plans[target].append(row)
    return {"plans": plans}


def fetch_adjacent_sha256(url: str) -> str:
    try:
        with urllib.request.urlopen(f"{url}.sha256") as response:
            return response.read().decode("utf-8").strip().split(" ", 1)[0]
    except Exception:  # noqa: BLE001
        return ""


def download_plugin(target_path: Path, source_url: str) -> None:
    with urllib.request.urlopen(source_url) as response, target_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def manual_plugin_source_roots() -> list[Path]:
    roots: list[Path] = []
    raw_source = os.environ.get("MANUAL_PLUGIN_SOURCE_DIR", "")
    for item in raw_source.split(os.pathsep):
        if item.strip():
            roots.append(Path(item).expanduser())

    feature_ops_root = os.environ.get("MC_FEATURE_OPS_ROOT", "")
    if feature_ops_root.strip():
        roots.append(Path(feature_ops_root).expanduser() / "mods" / "manual-plugins")

    return roots


def import_manual_plugin(manual_dir: Path, file_name: str, source_roots: list[Path]) -> tuple[Path | None, Path | None]:
    direct_path = manual_dir / file_name
    if direct_path.exists():
        return direct_path, None

    for root in source_roots:
        if root.is_file() and root.name == file_name:
            source_path = root
        elif root.is_dir():
            matches = sorted(path for path in root.rglob(file_name) if path.is_file())
            if not matches:
                continue
            source_path = matches[0]
        else:
            continue

        manual_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, direct_path)
        return direct_path, source_path

    return None, None


def plugin_targets(target_data_dir: Path, install_target: str) -> list[Path]:
    mapping = {
        "proxy": [target_data_dir / "proxy" / "plugins"],
        "lobby": [target_data_dir / "lobby" / "plugins"],
        "survival": [target_data_dir / "survival" / "plugins"],
        "creative": [target_data_dir / "creative" / "plugins"],
        "all-paper": [
            target_data_dir / "lobby" / "plugins",
            target_data_dir / "survival" / "plugins",
            target_data_dir / "creative" / "plugins",
        ],
    }
    return mapping[install_target]


def install_plugin(source_path: Path, target_dirs: list[Path]) -> None:
    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_dir / source_path.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-missing-manual", action="store_true")
    parser.add_argument("--strict-manual", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    target_data_dir = Path(os.environ["TARGET_DATA_DIR"]).resolve()
    manual_dir = repo_root / "plugins" / "manual"
    source_roots = manual_plugin_source_roots()
    allow_missing_manual = args.allow_missing_manual or env_flag("ALLOW_MISSING_MANUAL_PLUGINS", True)
    if args.strict_manual:
        allow_missing_manual = False
    plan = load_plan(Path(args.plan).resolve() if args.plan else None, repo_root)

    failures: list[str] = []
    warnings: list[str] = []
    imports: list[dict] = []
    synced: list[dict] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for service_name, entries in plan["plans"].items():
            for entry in entries:
                install_target = entry.get("install_target", service_name)
                source_path = None
                if entry.get("manual_source"):
                    source_path, imported_from = import_manual_plugin(manual_dir, entry["file_name"], source_roots)
                    if imported_from:
                        imports.append({"file_name": entry["file_name"], "source": str(imported_from)})
                    if source_path is None:
                        message = f"Missing manual plugin jar: {manual_dir / entry['file_name']}"
                        if allow_missing_manual:
                            warnings.append(message)
                        else:
                            failures.append(message)
                        continue
                else:
                    source_path = temp_root / entry["file_name"]
                    download_plugin(source_path, entry["source_url"])
                    checksum = entry.get("sha256") or fetch_adjacent_sha256(entry["source_url"])
                    if checksum:
                        calculated = hashlib.sha256(source_path.read_bytes()).hexdigest()
                        if calculated != checksum:
                            failures.append(f"Checksum mismatch for {entry['file_name']}")
                            continue

                install_plugin(source_path, plugin_targets(target_data_dir, install_target))
                synced.append({"plugin_id": entry["plugin_id"], "install_target": install_target})

    payload = {"status": "error" if failures else "success", "synced": synced, "imports": imports, "warnings": warnings, "failures": failures}
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        for item in imports:
            print(f"Imported manual plugin jar: {item['file_name']} <- {item['source']}")
        for item in synced:
            print(f"Synced {item['plugin_id']} -> {item['install_target']}")
        for warning in warnings:
            print(warning, file=sys.stderr)
        if failures:
            for failure in failures:
                print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
