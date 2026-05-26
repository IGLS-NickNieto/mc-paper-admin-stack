# Minecraft Admin Sidecar Stack

Docker Compose sidecar for administering an existing `mc-paper-velocity-geyser-stack` runtime without rehosting Minecraft itself.

This repo owns the admin layer only:

- `Console` as the primary web control plane for servers, worlds, players, plugins, perks, backups, and operations
- `Portainer` for container visibility and restarts
- `Filebrowser` for world, player, backup, and access-file management
- `OliveTin` for one-click operational workflows
- `MariaDB` for shared `LuckPerms`
- repo-file desired state, operational plugin catalogs, and permissions reconcile

The core stack remains the owner of bootstrap, Docker runtime, Paper/Velocity/Geyser/Floodgate, whitelist sync, backups, restore, and world storage.
The sibling `mc-backup-google-drive` repo remains the owner of offsite snapshots, staged restore, verification, and rollback promotion.

## Public repo safety

This repository is designed to be safe for public GitHub upload when you keep local runtime files untracked.

- Do not commit `.env`.
- Do not commit anything under `data/`.
- Do not commit manual plugin jars under `plugins/manual/`.
- Keep real passwords, DB hostnames, and exported core-stack paths only in local `.env`.
- `.dockerignore` excludes local env/data files from Docker build context so they are not sent to the daemon during image builds.
- Run `./scripts/public-repo-check.sh` and `./scripts/public-history-check.sh` before pushing a public branch.
- Use [docs/public-github-checklist.md](docs/public-github-checklist.md) as the release checklist.

## What this does not do

- no Crafty or Pterodactyl rehosting
- no relocation of world folders into panel-managed volumes
- no path assumption like `/opt/minecraft`
- no public-by-default admin exposure

## Quick start

Recommended same-host bootstrap after the core repo is already healthy:

```bash
bash scripts/bootstrap-sidecar.sh
```

That command now:

- auto-imports the core stack contract from `/opt/minecraft/scripts/export-admin-target-env.sh`
- fills or repairs `.env` from public-safe defaults
- prompts only for missing first-run values such as `LP_DB_HOST`
- generates local admin passwords when placeholder values are still present
- syncs plugins, renders LuckPerms config, starts the sidecar, and installs boot-time Git refresh

After pushing repo changes, refresh the VM without rebooting:

```bash
./scripts/refresh-from-git.sh
```

Manual flow remains available if you want tighter control:

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

5. Sign into the console and review the draft desired state:

   - Console: `http://<ADMIN_BIND_IP>:8088`
   - default local staff users come from `.env`

6. Apply the draft state from the console, or use the scripts directly if you need to bootstrap from CLI:

   ```bash
   ./scripts/sync-plugins.sh
   ./scripts/render-luckperms-config.sh
   ./scripts/reconcile-permissions.sh
   ```

7. Restart the target proxy and backend containers from the console, Portainer, or OliveTin if you applied changes manually.

## Default access model

- Admin UIs bind to the VM LAN IP recorded in `ADMIN_BIND_IP`.
- Keep that address on a trusted LAN or VPN.
- `Portainer` and `Filebrowser` are intended for `admin` staff only in v1.
- `OliveTin` exposes separate `mod` and `admin` local-user logins.
- `MariaDB` must bind to an address the core containers can reach, and `LP_DB_HOST` must point at that same VM address or hostname.

Default endpoints:

- Console: `http://<ADMIN_BIND_IP>:8088`
- Portainer: `https://<ADMIN_BIND_IP>:9443`
- Filebrowser: `http://<ADMIN_BIND_IP>:8080`
- OliveTin: `http://<ADMIN_BIND_IP>:1337`

## Desired state

Tracked control-plane state lives in [`config/console/`](config/console):

- `servers.json`: profile settings, world assignment, whitelist mode, plugin bundles
- `worlds.json`: imported world catalog and artifact metadata
- `plugins.json`: plugin catalog plus reusable bundles
- `perks.json`: LuckPerms groups and perk bundles
- `players.json`: player roles, perks, notes, and whitelist intent
- `whitelist.json`: invite list source-of-truth used to render the core whitelist file

The console edits these files and the worker applies them to the running stack through machine-readable scripts in the sibling repos.

Additional tracked stabilization state:

- `policy.json`: approved-now features, delayed features, cleanup thresholds, and alert posture
- `datapacks.json`: `safe_now` and `delayed` datapack allowlists with Bedrock-risk notes

## Plugin ownership

Plugin versions and install targets are primarily tracked in [config/console/plugins.json](config/console/plugins.json).

- Automated downloads are copied directly into the mounted core runtime plugin folders.
- Manual-source plugins go in `plugins/manual/`.
- `plugins/manifest.csv` remains as a legacy compatibility export for the existing plugin list.
- Use [docs/plugin-management.md](docs/plugin-management.md) for the workflow and current defaults.

## LuckPerms and closed-beta roles

This repo renders LuckPerms onto the proxy and all Paper backends with shared MariaDB storage, then reconciles groups and player assignments from the tracked console state.

Bootstrap hierarchy:

- `default -> guest`
- `member -> guest`
- `mod -> member`
- `admin -> mod`

Use [docs/permissions-bootstrap.md](docs/permissions-bootstrap.md) for the default nodes, reconcile flow, and optional initial assignments.

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
docker compose logs -f console
docker compose logs -f console-worker
docker compose logs -f olivetin
./scripts/validate-target.sh
./scripts/sync-plugins.sh
./scripts/render-luckperms-config.sh
./scripts/reconcile-permissions.sh
./scripts/stage-admin-state.sh
./scripts/run-backup-now.sh
```

Safe-now posture:

- stay Paper-first and multi-backend for the immediate phase
- no custom resource packs, custom items, custom models, or voice features
- add only datapacks listed in `config/console/datapacks.json`
- treat Bedrock-risk flags in the console as rollout blockers until verified in staging

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
