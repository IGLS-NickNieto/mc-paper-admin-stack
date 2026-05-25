# Integration Contract

`mc-paper-admin-stack` treats `mc-paper-velocity-geyser-stack` as an external runtime.

## Required inputs

Populate this repo's `.env` with explicit values exported from the sibling core repo:

```bash
../mc-paper-velocity-geyser-stack/scripts/export-admin-target-env.sh > .env
```

Then append the admin-side values from [`.env.example`](../.env.example).

Required target variables:

- `TARGET_STACK_ROOT`
- `TARGET_COMPOSE_PROJECT_DIR`
- `TARGET_COMPOSE_FILE`
- `TARGET_DATA_DIR`
- `TARGET_BACKUPS_DIR`
- `TARGET_ACCESS_DIR`
- `TARGET_INVITE_PLAYERS_FILE`
- `TARGET_BACKUP_SCRIPT`
- `TARGET_SYNC_WHITELIST_SCRIPT`
- `TARGET_PROXY_CONTAINER`
- `TARGET_LOBBY_CONTAINER`
- `TARGET_SURVIVAL_CONTAINER`
- `TARGET_CREATIVE_CONTAINER`

## Contract rules

- This repo does not assume `/opt/minecraft`.
- This repo does not autodiscover Docker networks, paths, or container names.
- This repo does not move worlds or player data into panel-owned storage.
- This repo mounts and manages the existing core runtime folders in place.
- Whitelist source-of-truth remains the core repo's invite file plus whitelist sync script.
- Backup source-of-truth remains the core repo's backup script; this repo stages admin state before invoking it.
