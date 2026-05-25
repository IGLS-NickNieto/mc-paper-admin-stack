# Plugin Management

Operational plugin ownership lives in this repo.

## Manifest format

Tracked file: [`plugins/manifest.csv`](../plugins/manifest.csv)

Columns:

- `plugin_id`
- `version`
- `install_target`
- `file_name`
- `source_url`
- `sha256`
- `manual_source`
- `notes`

`install_target` supports `proxy`, `lobby`, `survival`, `creative`, and `all-paper`.

## Source policy

- Direct-download entries are copied automatically by `scripts/sync-plugins.sh`.
- If `sha256` is blank, the sync script attempts to fetch an adjacent `.sha256` file from the same upstream URL.
- Manual-source entries expect the jar in `plugins/manual/`.
- Manual-source entries are used when upstream downloads are gated, redistribution is unclear, or the approved source is a project page instead of a stable artifact URL.

## Current default set

- Proxy: LuckPerms Velocity, ExoHub
- Lobby: LuckPerms, EssentialsX, EssentialsXSpawn, WorldEdit, WorldGuard, QuickConnect, OpenInv
- Survival: LuckPerms, EssentialsX, OpenInv
- Creative: LuckPerms, EssentialsX, OpenInv

## Workflow

1. Place any required manual jars into `plugins/manual/`.
2. Run `./scripts/sync-plugins.sh`.
3. Run `./scripts/render-luckperms-config.sh`.
4. Restart the affected core containers, or use OliveTin `Reapply Plugins and Configs`.
