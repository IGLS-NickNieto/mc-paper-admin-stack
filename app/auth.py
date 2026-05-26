from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from typing import Any

from . import db


PBKDF2_ITERATIONS = 120_000


def first_run_setup_enabled(env: dict[str, str]) -> bool:
    value = env.get("ENABLE_CONSOLE_FIRST_RUN_SETUP", "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def value_needs_setup(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("'\"").lower()
    if normalized in {"", "todo", "placeholder"}:
        return True
    return normalized.startswith(("change-me", "changeme", "change_me", "replace-me", "replace_me"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt_b64),
        int(iterations),
    )
    return hmac.compare_digest(base64.b64decode(digest_b64), digest)


def seed_user_specs(env: dict[str, str]) -> list[tuple[str, str, str]]:
    return [
        (env.get("CONSOLE_ADMIN_USER", "admin"), "admin", env.get("CONSOLE_ADMIN_PASSWORD", "change-me-console-admin")),
        (env.get("CONSOLE_MOD_USER", "mod"), "mod", env.get("CONSOLE_MOD_PASSWORD", "change-me-console-mod")),
    ]


def ensure_seed_users(connection: sqlite3.Connection, env: dict[str, str]) -> None:
    setup_enabled = first_run_setup_enabled(env)
    for username, role, password in seed_user_specs(env):
        if setup_enabled and (value_needs_setup(username) or value_needs_setup(password)):
            continue

        password_hash = hash_password(password)
        row = connection.execute("SELECT id, role, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
                (username, role, password_hash),
            )
            db.add_audit_log(connection, "system", "seed_user", {"username": username, "role": role})
            continue

        if row["role"] != role or not verify_password(password, row["password_hash"]):
            connection.execute(
                "UPDATE users SET role = ?, password_hash = ? WHERE id = ?",
                (role, password_hash, row["id"]),
            )
            db.add_audit_log(connection, "system", "update_seed_user", {"username": username, "role": role})
    connection.commit()


def console_setup_required(connection: sqlite3.Connection, env: dict[str, str]) -> bool:
    if not first_run_setup_enabled(env):
        return False

    required_env_keys = (
        "CONSOLE_ADMIN_USER",
        "CONSOLE_ADMIN_PASSWORD",
        "CONSOLE_MOD_USER",
        "CONSOLE_MOD_PASSWORD",
        "CONSOLE_SESSION_SECRET",
    )
    if any(value_needs_setup(env.get(key)) for key in required_env_keys):
        return True

    for username, role, _password in seed_user_specs(env):
        row = connection.execute("SELECT id FROM users WHERE username = ? AND role = ?", (username, role)).fetchone()
        if row is None:
            return True

    return False


def set_local_user(connection: sqlite3.Connection, username: str, role: str, password: str) -> None:
    password_hash = hash_password(password)
    row = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
            (username, role, password_hash),
        )
    else:
        connection.execute(
            "UPDATE users SET role = ?, password_hash = ? WHERE id = ?",
            (role, password_hash, row["id"]),
        )
    connection.execute("DELETE FROM users WHERE role = ? AND username <> ?", (role, username))


def set_console_credentials(
    connection: sqlite3.Connection,
    admin_username: str,
    admin_password: str,
    mod_username: str,
    mod_password: str,
) -> None:
    set_local_user(connection, admin_username, "admin", admin_password)
    set_local_user(connection, mod_username, "mod", mod_password)
    db.add_audit_log(
        connection,
        "system",
        "first_run_credentials",
        {"admin_username": admin_username, "mod_username": mod_username},
    )
    connection.commit()


def authenticate(connection: sqlite3.Connection, username: str, password: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT id, username, role, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}
