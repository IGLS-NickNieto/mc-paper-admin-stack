# Validation Checklist

## Preflight

- Copy or export the core stack contract into `.env`.
- Fill in the admin-side secrets and access values.
- Run `./scripts/validate-target.sh`.
- Run `docker compose config`.

## Runtime validation

- Start the sidecar with `docker compose up -d`.
- Confirm Portainer is reachable only on `https://127.0.0.1:${PORTAINER_PORT}` by default.
- Confirm Filebrowser is reachable only on `http://127.0.0.1:${FILEBROWSER_PORT}` by default.
- Confirm OliveTin is reachable only on `http://127.0.0.1:${OLIVETIN_PORT}` by default.
- Confirm MariaDB is bound only to `MARIADB_BIND_IP:MARIADB_PORT`.

## Core integration

- Run `./scripts/sync-plugins.sh`.
- Run `./scripts/render-luckperms-config.sh`.
- Restart the target proxy and Paper containers.
- Run `./scripts/bootstrap-permissions.sh`.
- Verify LuckPerms reports MariaDB storage on proxy and Paper startup logs.

## Functional checks

- `/hub` works from every backend.
- Lobby selector connects players to `survival` and `creative`.
- `ops/access/invite-players.txt` changes still apply through `sync_whitelist`.
- `backup_now` stages `data/proxy/admin-state/` before calling the core backup script.
- The imported lobby world exists in the core lobby data directory and keeps its protected spawn behavior.
