from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from typing import Any

from . import db


PBKDF2_ITERATIONS = 120_000


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


def ensure_seed_users(connection: sqlite3.Connection, env: dict[str, str]) -> None:
    seed_users = [
        (env.get("CONSOLE_ADMIN_USER", "admin"), "admin", env.get("CONSOLE_ADMIN_PASSWORD", "change-me-console-admin")),
        (env.get("CONSOLE_MOD_USER", "mod"), "mod", env.get("CONSOLE_MOD_PASSWORD", "change-me-console-mod")),
    ]
    for username, role, password in seed_users:
        row = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
                (username, role, hash_password(password)),
            )
            db.add_audit_log(connection, "system", "seed_user", {"username": username, "role": role})
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

