#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANUAL_DIR="${ROOT_DIR}/plugins/manual"
STRICT=0
SOURCES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=1
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: scripts/import-manual-plugins.sh [--strict] SOURCE_DIR [...]

Copies approved manual plugin jars from private/local source folders into
plugins/manual/. The destination is ignored by Git and preserved by VM refresh.

Environment fallback:
  MANUAL_PLUGIN_SOURCE_DIR=/path/one:/path/two
  MC_FEATURE_OPS_ROOT=/path/to/mc-feature-ops
EOF
      exit 0
      ;;
    *)
      SOURCES+=("$1")
      shift
      ;;
  esac
done

if [[ "${#SOURCES[@]}" -eq 0 && -n "${MANUAL_PLUGIN_SOURCE_DIR:-}" ]]; then
  IFS=':' read -r -a SOURCES <<< "${MANUAL_PLUGIN_SOURCE_DIR}"
fi

if [[ "${#SOURCES[@]}" -eq 0 && -n "${MC_FEATURE_OPS_ROOT:-}" ]]; then
  SOURCES+=("${MC_FEATURE_OPS_ROOT}/mods/manual-plugins")
fi

if [[ "${#SOURCES[@]}" -eq 0 ]]; then
  echo "Provide at least one private manual plugin source directory." >&2
  exit 1
fi

mkdir -p "${MANUAL_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1 || ! "${PYTHON_BIN}" -c 'import sys' >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Required command not found: python3" >&2
    exit 1
  fi
fi

"${PYTHON_BIN}" - "${STRICT}" "${ROOT_DIR}" "${MANUAL_DIR}" "${SOURCES[@]}" <<'PY'
from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path


def load_manual_entries(repo_root: Path) -> list[dict[str, str]]:
    state_path = repo_root / "config" / "console" / "plugins.json"
    if state_path.exists():
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        entries = payload.get("catalog", [])
    else:
        manifest_path = repo_root / "plugins" / "manifest.csv"
        with manifest_path.open("r", encoding="utf-8", newline="") as handle:
            entries = list(csv.DictReader(handle))

    deduped: dict[str, dict[str, str]] = {}
    for entry in entries:
        manual_source = entry.get("manual_source")
        if manual_source is True or str(manual_source).strip().lower() == "true":
            deduped[entry["file_name"]] = {"plugin_id": entry["plugin_id"], "file_name": entry["file_name"]}
    return list(deduped.values())


def find_source(file_name: str, roots: list[Path]) -> Path | None:
    for root in roots:
        if root.is_file() and root.name == file_name:
            return root
        if not root.is_dir():
            continue
        matches = sorted(path for path in root.rglob(file_name) if path.is_file())
        if matches:
            return matches[0]
    return None


def main() -> int:
    strict = sys.argv[1] == "1"
    repo_root = Path(sys.argv[2])
    manual_dir = Path(sys.argv[3])
    roots = [Path(value).expanduser() for value in sys.argv[4:] if value]
    missing: list[str] = []

    for entry in load_manual_entries(repo_root):
        destination = manual_dir / entry["file_name"]
        if destination.exists():
            print(f"Already present {entry['file_name']}")
            continue

        source = find_source(entry["file_name"], roots)
        if source is None:
            missing.append(entry["file_name"])
            continue

        shutil.copy2(source, destination)
        print(f"Imported {entry['file_name']} from {source}")

    if missing:
        for file_name in missing:
            print(f"Missing manual plugin jar: {manual_dir / file_name}", file=sys.stderr)
        return 1 if strict else 0

    return 0


raise SystemExit(main())
PY
