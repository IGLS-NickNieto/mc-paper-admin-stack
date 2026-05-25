# Minecraft Admin Sidecar Stack

Docker Compose sidecar for administering an existing `mc-paper-velocity-geyser-stack` runtime without rehosting Minecraft itself.

This repo owns the admin layer only:

- `Portainer` for container visibility and restarts
- `Filebrowser` for world, player, backup, and access-file management
- `OliveTin` for one-click operational workflows
- `MariaDB` for shared `LuckPerms`
- operational plugin manifests, config, and permissions bootstrap

The core stack remains the owner of bootstrap, Docker runtime, Paper/Velocity/Geyser/Floodgate, whitelist sync, backups, restore, and world storage.

## Public repo safety

This repository is designed to be safe for public GitHub upload when you keep local runtime files untracked.

- Do not commit `.env`.
- Do not commit anything under `data/`.
- Do not commit manual plugin jars under `plugins/manual/`.
- Keep real passwords, DB hostnames, and exported core-stack paths only in local `.env`.
- `.dockerignore` excludes local env/data files from Docker build context so they are not sent to the daemon during image builds.

## What this does not do

- no Crafty or Pterodactyl rehosting
- no relocation of world folders into panel-managed volumes
- no path assumption like `/opt/minecraft`
- no public-by-default admin exposure

## Quick start

1. Export the target contract from the sibling core repo:

   ```bash
   ../mc-paper-velocity-geyser-stack/scripts/export-admin-target-env.sh > .env
   ```

2. Copy the admin defaults from [`.env.example`](.env.example) into `.env` and fill in the passwords and ports you want.

3. Validate the target:

   ```bash
   ./scripts/validate-target.sh
   ```

4. Start the sidecar:

   ```bash
   docker compose up -d --build
   ```

5. Install the plugin set and configs into the existing core runtime:

   ```bash
   ./scripts/sync-plugins.sh
   ./scripts/render-luckperms-config.sh
   ./scripts/bootstrap-permissions.sh
   ```

6. Restart the target proxy and backend containers from Portainer or OliveTin.

## Default access model

- Admin UIs bind to `127.0.0.1` by default.
- Reach them through local login, SSH tunnel, or VPN.
- `Portainer` and `Filebrowser` are intended for `admin` staff only in v1.
- `OliveTin` exposes separate `mod` and `admin` local-user logins.
- `MariaDB` must bind to an address the core containers can reach, and `LP_DB_HOST` must point at that same VM address or hostname.

Default endpoints:

- Portainer: `https://127.0.0.1:9443`
- Filebrowser: `http://127.0.0.1:8080`
- OliveTin: `http://127.0.0.1:1337`

## Plugin ownership

Plugin versions and install targets are tracked in [plugins/manifest.csv](plugins/manifest.csv).

- Automated downloads are copied directly into the mounted core runtime plugin folders.
- Manual-source plugins go in `plugins/manual/`.
- Use [docs/plugin-management.md](docs/plugin-management.md) for the workflow and current defaults.

## LuckPerms and closed-beta roles

This repo renders LuckPerms onto the proxy and all Paper backends with shared MariaDB storage.

Bootstrap hierarchy:

- `default -> guest`
- `member -> guest`
- `mod -> member`
- `admin -> mod`

Use [docs/permissions-bootstrap.md](docs/permissions-bootstrap.md) for the default nodes and optional initial assignments.

## Backups and whitelist state

- Whitelist state stays owned by the core repo through `TARGET_INVITE_PLAYERS_FILE` and `TARGET_SYNC_WHITELIST_SCRIPT`.
- `./scripts/run-backup-now.sh` stages LuckPerms SQL plus plugin/bootstrap snapshots into `data/proxy/admin-state/`, then calls the core backup script.
- The core backup archive picks up that staged admin state because it already archives `data/proxy`.

## Imported lobby flow

This repo does not ship or rehost the lobby world.

To import an existing protected hub:

1. Stop the core lobby container.
2. Copy the hub world into the existing core lobby world directory under `TARGET_DATA_DIR/lobby`.
3. Sync the lobby plugin set from this repo.
4. Configure spawn and protection with the lobby plugins already mounted into that same core data directory.
5. Restart the lobby container and verify protected spawn behavior.

## Operations

Useful commands:

```bash
docker compose up -d --build
docker compose logs -f olivetin
./scripts/validate-target.sh
./scripts/sync-plugins.sh
./scripts/render-luckperms-config.sh
./scripts/bootstrap-permissions.sh
./scripts/stage-admin-state.sh
./scripts/run-backup-now.sh
```

OliveTin actions included by default:

- `backup_now`
- `sync_whitelist`
- `restart_proxy`
- `restart_lobby`
- `restart_survival`
- `restart_creative`
- `restart_all_core`
- `stage_admin_state`
- `reapply_plugins_and_configs`

## Documentation

- [docs/integration-contract.md](docs/integration-contract.md)
- [docs/plugin-management.md](docs/plugin-management.md)
- [docs/permissions-bootstrap.md](docs/permissions-bootstrap.md)
- [docs/validation-checklist.md](docs/validation-checklist.md)

## Upstream references

Implementation defaults in this repo align with current upstream docs:

- LuckPerms network install: https://luckperms.net/wiki/Network-Installation
- LuckPerms config locations: https://luckperms.net/wiki/Configuration
- OliveTin config and security: https://docs.olivetin.app/config.html
- OliveTin local users: https://docs.olivetin.app/security/local.html
- Filebrowser Docker install: https://filebrowser.org/installation
- Portainer CLI and HTTPS defaults: https://docs.portainer.io/advanced/cli
