from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db, services, state
from .config import load_settings


settings = load_settings()
services.ensure_runtime(settings)

app = FastAPI(title=settings.console_title)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, https_only=False)
app.mount("/static", StaticFiles(directory=str(settings.repo_root / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(settings.repo_root / "app" / "templates"))


def current_user(request: Request) -> dict | None:
    return request.session.get("user")


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise PermissionError("login required")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "admin":
        raise PermissionError("admin required")
    return user


def render(request: Request, template_name: str, extra: dict) -> HTMLResponse:
    with db.connect(settings.database_path) as connection:
        context = {
            "request": request,
            "user": current_user(request),
            "console_title": settings.console_title,
            "jobs": services.list_jobs(connection, limit=8),
            "audit_logs": services.list_audit_logs(connection, limit=8),
        }
    context.update(extra)
    return templates.TemplateResponse(template_name, context)


@app.on_event("startup")
def startup() -> None:
    with db.connect(settings.database_path) as connection:
        auth.ensure_seed_users(connection, dict(os.environ))


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return render(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> HTMLResponse:
    with db.connect(settings.database_path) as connection:
        user = auth.authenticate(connection, username, password)
    if user is None:
        return render(request, "login.html", {"error": "Invalid username or password."})
    request.session["user"] = user
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)

    overview = services.stability_overview(settings)
    return render(
        request,
        "dashboard.html",
        {
            "section": "dashboard",
            "state": overview["state"],
            "status": overview["status"],
            "snapshots": overview["snapshots"],
            "disk": overview["disk"],
        },
    )


@app.get("/servers", response_class=HTMLResponse)
def servers_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "servers.html", {"section": "servers", "state": current_state})


@app.post("/servers/{profile_name}")
async def update_server(
    request: Request,
    profile_name: str,
    display_name: str = Form(...),
    assigned_world_id: str = Form(...),
    whitelist_mode: str = Form(...),
    plugin_bundles: list[str] = Form(...),
    gamemode: str = Form(...),
    difficulty: str = Form(...),
    max_players: int = Form(...),
    view_distance: int = Form(...),
    simulation_distance: int = Form(...),
    pvp: str = Form(...),
    allow_nether: str = Form(...),
    allow_flight: str = Form(...),
    force_gamemode: str = Form(...),
    world_border_enabled: str = Form(...),
    world_border_radius: int = Form(...),
    pregeneration_state: str = Form(...),
    pregeneration_last_run_at: str = Form(""),
    pregeneration_notes: str = Form(""),
    maintenance_window: str = Form(""),
    cleanup_notes: str = Form(""),
) -> RedirectResponse:
    require_admin(request)
    services.update_server_profile(
        settings,
        profile_name,
        {
            "display_name": display_name,
            "assigned_world_id": assigned_world_id,
            "whitelist_mode": whitelist_mode,
            "plugin_bundles": plugin_bundles,
            "world_border": {
                "enabled": world_border_enabled == "true",
                "radius_blocks": world_border_radius,
            },
            "pregeneration_status": {
                "state": pregeneration_state,
                "last_run_at": pregeneration_last_run_at,
                "notes": pregeneration_notes,
            },
            "maintenance_window": maintenance_window,
            "cleanup_notes": cleanup_notes,
            "settings": {
                "gamemode": gamemode,
                "difficulty": difficulty,
                "max-players": max_players,
                "view-distance": view_distance,
                "simulation-distance": simulation_distance,
                "pvp": pvp == "true",
                "allow-nether": allow_nether == "true",
                "allow-flight": allow_flight == "true",
                "force-gamemode": force_gamemode == "true",
            },
        },
    )
    return RedirectResponse("/servers", status_code=303)


@app.get("/worlds", response_class=HTMLResponse)
def worlds_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "worlds.html", {"section": "worlds", "state": current_state})


@app.post("/worlds/import")
async def import_world(
    request: Request,
    world_id: str = Form(...),
    display_name: str = Form(...),
    notes: str = Form(""),
    archive: UploadFile = File(...),
) -> RedirectResponse:
    require_admin(request)
    services.import_world_archive(settings, archive.filename or f"{world_id}.zip", await archive.read(), world_id, display_name, notes)
    return RedirectResponse("/worlds", status_code=303)


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "players.html", {"section": "players", "state": current_state})


@app.post("/players")
async def update_player(
    request: Request,
    player_name: str = Form(...),
    role: str = Form(...),
    perks: str = Form(""),
    notes: str = Form(""),
    whitelisted: str = Form("false"),
) -> RedirectResponse:
    require_admin(request)
    services.update_player_state(
        settings,
        player_name,
        role,
        whitelisted == "true",
        notes,
        [value.strip() for value in perks.split(",") if value.strip()],
    )
    return RedirectResponse("/players", status_code=303)


@app.get("/plugins", response_class=HTMLResponse)
def plugins_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "plugins.html", {"section": "plugins", "state": current_state})


@app.get("/policies", response_class=HTMLResponse)
def policies_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "policies.html", {"section": "policies", "state": current_state})


@app.post("/plugins/{profile_name}")
async def update_plugins(request: Request, profile_name: str, plugin_bundles: list[str] = Form(...)) -> RedirectResponse:
    require_admin(request)
    services.update_plugin_bundles(settings, profile_name, plugin_bundles)
    return RedirectResponse("/plugins", status_code=303)


@app.post("/policies")
async def update_policy(
    request: Request,
    approved_features_now: str = Form(""),
    delayed_features: str = Form(""),
    maintenance_window: str = Form(""),
    entity_limits: str = Form(""),
    log_retention_days: int = Form(...),
    spark_report_retention_days: int = Form(...),
    crash_report_retention_days: int = Form(...),
    data_warn_percent: int = Form(...),
    backups_warn_percent: int = Form(...),
    suspicious_growth_gb: int = Form(...),
    backup_freshness_target_hours: int = Form(...),
    alerts: str = Form(""),
) -> RedirectResponse:
    require_admin(request)
    services.update_policy_state(
        settings,
        approved_features_now,
        delayed_features,
        maintenance_window,
        entity_limits,
        log_retention_days,
        spark_report_retention_days,
        crash_report_retention_days,
        data_warn_percent,
        backups_warn_percent,
        suspicious_growth_gb,
        backup_freshness_target_hours,
        alerts,
    )
    return RedirectResponse("/policies", status_code=303)


@app.post("/datapacks")
async def update_datapacks(request: Request, safe_now: str = Form(""), delayed: str = Form("")) -> RedirectResponse:
    require_admin(request)
    services.update_datapack_state(settings, safe_now, delayed)
    return RedirectResponse("/policies", status_code=303)


@app.get("/perks", response_class=HTMLResponse)
def perks_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    return render(request, "perks.html", {"section": "perks", "state": current_state})


@app.post("/perks/bundle")
async def update_perk_bundle(
    request: Request,
    bundle_name: str = Form(...),
    description: str = Form(""),
    permissions: str = Form(""),
) -> RedirectResponse:
    require_admin(request)
    services.update_perk_bundle(settings, bundle_name, description, permissions)
    return RedirectResponse("/perks", status_code=303)


@app.post("/perks/group/{group_name}")
async def update_group(request: Request, group_name: str, permissions: str = Form(...)) -> RedirectResponse:
    require_admin(request)
    services.update_group_permissions(settings, group_name, permissions)
    return RedirectResponse("/perks", status_code=303)


@app.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    current_state = state.load_all_state(settings.state_dir)
    snapshots = services.snapshot_overview(settings)
    return render(request, "backups.html", {"section": "backups", "snapshots": snapshots, "state": current_state})


@app.post("/backups/{action}")
async def queue_backup_job(
    request: Request,
    action: str,
    source_ref: str = Form("latest"),
    scope: str = Form("full"),
    stage_path: str = Form(""),
    allow_playerdata_rollback: str = Form("false"),
) -> RedirectResponse:
    user = require_admin(request)
    job_map = {
        "local": ("run_local_backup", {}),
        "offsite": ("run_offsite_backup", {}),
        "verify": ("verify_backups", {}),
        "restore": ("stage_restore", {"source_ref": source_ref, "scope": scope}),
        "promote": (
            "promote_rollback",
            {
                "stage_path": stage_path,
                "scope": scope,
                "allow_playerdata_rollback": allow_playerdata_rollback == "true",
            },
        ),
    }
    job_type, payload = job_map[action]
    with db.connect(settings.database_path) as connection:
        services.enqueue_job(connection, job_type, user["username"], payload)
    return RedirectResponse("/backups", status_code=303)


@app.get("/operations", response_class=HTMLResponse)
def operations_page(request: Request) -> HTMLResponse:
    try:
        require_user(request)
    except PermissionError:
        return RedirectResponse("/login", status_code=303)
    status = services.status_overview(settings)
    return render(request, "operations.html", {"section": "operations", "status": status})


@app.get("/env", response_class=HTMLResponse)
def env_page(request: Request) -> HTMLResponse:
    try:
        require_admin(request)
    except PermissionError:
        if current_user(request) is None:
            return RedirectResponse("/login", status_code=303)
        raise HTTPException(status_code=403, detail="admin required")
    return render(
        request,
        "env.html",
        {
            "section": "env",
            "targets": services.load_env_targets(settings),
            "saved": request.query_params.get("saved", ""),
        },
    )


@app.post("/env/{target_id}")
async def update_env(request: Request, target_id: str) -> RedirectResponse:
    user = require_admin(request)
    form = await request.form()
    changed_keys = services.save_env_target(settings, target_id, {key: str(value) for key, value in form.items()})
    with db.connect(settings.database_path) as connection:
        db.add_audit_log(connection, user["username"], "update_env", {"target": target_id, "keys": changed_keys})
        connection.commit()
    return RedirectResponse(f"/env?saved={target_id}", status_code=303)


@app.post("/operations/{action}")
async def run_operation(request: Request, action: str) -> RedirectResponse:
    user = require_admin(request)
    with db.connect(settings.database_path) as connection:
        services.enqueue_job(connection, "operation", user["username"], {"action": action})
    return RedirectResponse("/operations", status_code=303)


@app.post("/apply")
async def queue_apply(request: Request) -> RedirectResponse:
    user = require_admin(request)
    with db.connect(settings.database_path) as connection:
        services.enqueue_job(connection, "apply_state", user["username"], {})
    return RedirectResponse("/", status_code=303)
