# Permissions Bootstrap

Bootstrap command:

```bash
./scripts/reconcile-permissions.sh
```

Compatibility wrapper:

```bash
./scripts/bootstrap-permissions.sh
```

Both commands now reconcile the tracked desired state instead of applying a one-time hard-coded bootstrap only.

## Group model

LuckPerms keeps the immutable `default` group. This repo maps your intended closed-beta roles like this:

- `default` inherits `guest`
- `member` inherits `guest`
- `mod` inherits `member`
- `admin` inherits `mod`

This preserves LuckPerms defaults while still making `guest` the effective baseline role.

## Default nodes

- `guest`
  - basic messaging and MOTD commands
  - `/spawn`
  - `/home`, `/sethome`, `/delhome`
  - QuickConnect selector permissions for `lobby`, `survival`, and `creative`
- `member`
  - inherits `guest`
  - `back`
  - basic teleport-request quality-of-life nodes
  - additional EssentialsX homes via `essentials.sethome.multiple.member`
- `mod`
  - inherits `member`
  - `OpenInv`
  - moderation nodes like kick, mute, tempban, unban, and social spy
  - intended OliveTin role for whitelist sync and backend restarts
- `admin`
  - inherits `mod`
  - wildcard-style in-game management access for LuckPerms, EssentialsX, WorldEdit, WorldGuard, and OpenInv
  - intended external access to Portainer, Filebrowser, and all OliveTin actions

## Optional initial assignments

Set any of these in `.env` before running the bootstrap:

- `LP_BOOTSTRAP_MEMBER_PLAYERS`
- `LP_BOOTSTRAP_MOD_PLAYERS`
- `LP_BOOTSTRAP_ADMIN_PLAYERS`

Each accepts a comma-separated player list.

These env-based bootstrap players are merged into the tracked player state during reconcile so first-run admin access still works before the UI is fully populated.
