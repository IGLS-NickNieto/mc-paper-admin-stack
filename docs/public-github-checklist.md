# Public GitHub Checklist

Before pushing this repo to a public remote, verify:

- `.env` is not tracked.
- `data/` is not tracked.
- `plugins/manual/*.jar` is not tracked.
- Python cache or test/build artifacts are not tracked.
- No generated OliveTin config exists outside ignored `data/`.
- No real LAN hostname, IP, token, password, or exported target path was copied into tracked docs or examples.
- `git status --short` shows only the files you intend to publish.

Helpful checks:

```bash
git status --short
git ls-files
./scripts/public-repo-check.sh
./scripts/public-history-check.sh
rg -n --hidden -S "password|secret|token|api[_-]?key|BEGIN .*KEY|PRIVATE KEY|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|mc\." .
```

Expected sensitive locations stay local-only:

- `.env`
- `data/olivetin/config/config.yaml`
- `data/filebrowser/`
- `data/mariadb/`
- any manual proprietary plugin jars in `plugins/manual/`
- `__pycache__/`, `*.pyc`, and local test cache directories
