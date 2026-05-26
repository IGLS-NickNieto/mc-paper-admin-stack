# Validation Checklist

## Preflight

- Copy or export the core stack contract into `.env`.
- Fill in the admin-side secrets and access values.
- Run `./scripts/validate-target.sh`.
- Run `docker compose config`.

## Runtime validation

- Start the sidecar with `docker compose up -d`.
- Confirm the console is reachable on `http://${ADMIN_BIND_IP}:${CONSOLE_PORT}`.
- Confirm Portainer is reachable on `https://${ADMIN_BIND_IP}:${PORTAINER_PORT}`.
- Confirm Filebrowser is reachable on `http://${ADMIN_BIND_IP}:${FILEBROWSER_PORT}`.
- Confirm OliveTin is reachable on `http://${ADMIN_BIND_IP}:${OLIVETIN_PORT}`.
- Confirm MariaDB is bound only to `MARIADB_BIND_IP:MARIADB_PORT`.

## Core integration

- Review `config/console/*.json` or update the draft state from the console.
- Review `config/console/policy.json` and `config/console/datapacks.json` before approving gameplay changes.
- Run `./scripts/sync-plugins.sh`.
- Run `./scripts/render-luckperms-config.sh`.
- Restart the target proxy and Paper containers.
- Run `./scripts/reconcile-permissions.sh`.
- Verify LuckPerms reports MariaDB storage on proxy and Paper startup logs.

## Functional checks

- The console shows `Dashboard`, `Servers`, `Worlds`, `Players`, `Plugins`, `Perks`, `Backups`, `Operations`, and `Environment`.
- The console shows a `Policies` page with approved-now features, delayed features, and safe-now datapacks.
- Saving a draft server profile change updates `config/console/servers.json`.
- Applying draft state updates the running core profile config through `scripts/admin-apply-profile.sh`.
- Plugin entries show Bedrock-risk and rollout phase metadata.
- `/hub` works from every backend.
- Lobby selector connects players to `survival` and `creative`.
- `ops/access/invite-players.txt` changes still apply through `sync_whitelist`.
- World imports land under the core runtime world library path and can be assigned to a profile.
- Backup screens can queue local backup, offsite backup, staged restore, verify, and rollback promotion jobs.
- `backup_now` stages `data/proxy/admin-state/` before calling the core backup script.
- Runtime status shows proxy forwarding, Geyser/Floodgate, Java/Bedrock ports, and backend non-public checks.
- The imported lobby world exists in the core lobby data directory and keeps its protected spawn behavior.
