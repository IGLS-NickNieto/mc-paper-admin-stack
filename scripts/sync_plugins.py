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
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    target_data_dir = Path(os.environ["TARGET_DATA_DIR"]).resolve()
    manual_dir = repo_root / "plugins" / "manual"
    plan = load_plan(Path(args.plan).resolve() if args.plan else None, repo_root)

    failures: list[str] = []
    synced: list[dict] = []
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_root = Path(temp_dir)
      for service_name, entries in plan["plans"].items():
          for entry in entries:
              install_target = entry.get("install_target", service_name)
              source_path = None
              if entry.get("manual_source"):
                  source_path = manual_dir / entry["file_name"]
                  if not source_path.exists():
                      failures.append(f"Missing manual plugin jar: {source_path}")
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

    payload = {"status": "error" if failures else "success", "synced": synced, "failures": failures}
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        for item in synced:
            print(f"Synced {item['plugin_id']} -> {item['install_target']}")
        if failures:
            for failure in failures:
                print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
