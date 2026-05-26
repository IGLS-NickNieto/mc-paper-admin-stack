#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

failures=0

print_matches() {
  local header="$1"
  shift

  if [[ "$#" -eq 0 ]]; then
    return 0
  fi

  echo "${header}"
  printf '  %s\n' "$@"
  echo
}

check_tracked_paths() {
  local header="$1"
  shift
  local -a matches=()

  while IFS= read -r match; do
    [[ -e "${match}" ]] || continue
    matches+=("${match}")
  done < <(git ls-files -- "$@")

  if [[ "${#matches[@]}" -gt 0 ]]; then
    print_matches "${header}" "${matches[@]}"
    failures=1
  fi
}

check_tracked_content() {
  local header="$1"
  local pattern="$2"
  shift 2
  local -a matches=()

  while IFS= read -r match; do
    case "${match}" in
      scripts/public-repo-check.sh:*|docs/public-github-checklist.md:*)
        continue
        ;;
    esac
    matches+=("${match}")
  done < <(git grep -nI -E "${pattern}" -- "$@" || true)

  if [[ "${#matches[@]}" -gt 0 ]]; then
    print_matches "${header}" "${matches[@]}"
    failures=1
  fi
}

check_tracked_paths \
  "Tracked local-only or generated files detected:" \
  .env \
  .env.local \
  .env.production \
  .env.staging \
  data \
  plugins/manual/*.jar \
  plugins/manual/.checksums \
  __pycache__ \
  app/__pycache__ \
  app/tests/__pycache__ \
  '*.pyc' \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  .venv

check_tracked_content \
  "Tracked private key material detected:" \
  'BEGIN [A-Z ]*PRIVATE KEY' \
  .

check_tracked_content \
  "Tracked local absolute paths detected:" \
  'C:\\Users\\|/c/Users/|/Users/|/home/[^/]+/' \
  .

check_tracked_content \
  "Tracked exported target values detected in public env files:" \
  '^TARGET_[A-Z0-9_]+=.+$' \
  .env.example \
  .env \
  .env.*

lp_db_host_line="$(grep -E '^LP_DB_HOST=' .env.example || true)"
if [[ "${lp_db_host_line}" != "LP_DB_HOST=CHANGE_ME_TO_VM_LAN_IP_OR_HOSTNAME" ]]; then
  print_matches \
    "LP_DB_HOST in .env.example should stay on the public-safe placeholder:" \
    "${lp_db_host_line:-LP_DB_HOST line missing}"
  failures=1
fi

admin_bind_line="$(grep -E '^ADMIN_BIND_IP=' .env.example || true)"
if [[ "${admin_bind_line}" != "ADMIN_BIND_IP=127.0.0.1" ]]; then
  print_matches \
    "ADMIN_BIND_IP in .env.example should default to localhost:" \
    "${admin_bind_line:-ADMIN_BIND_IP line missing}"
  failures=1
fi

if [[ "${failures}" -ne 0 ]]; then
  echo "Public repo safety check failed." >&2
  exit 1
fi

echo "Public repo safety check passed."
