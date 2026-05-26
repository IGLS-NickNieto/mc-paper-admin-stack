from __future__ import annotations

import json
import time
from typing import Any

from . import db, services
from .config import load_settings


def main() -> None:
    settings = load_settings()
    services.ensure_runtime(settings)

    while True:
        with db.connect(settings.database_path) as connection:
            job = services.get_next_queued_job(connection)
            if job is None:
                time.sleep(2)
                continue

            job_id = int(job["id"])
            services.append_job_log(connection, job_id, f"Starting job {job['job_type']}")
            try:
                result = services.execute_job(settings, connection, job)
            except Exception as exc:  # noqa: BLE001
                services.append_job_log(connection, job_id, f"Job failed: {exc}")
                services.finish_job(connection, job_id, "failed", {"status": "error", "message": str(exc)})
                continue

            status = "completed" if result.get("status", "success") != "error" and result.get("returncode", 0) == 0 else "failed"
            services.finish_job(connection, job_id, status, result)
            services.append_job_log(connection, job_id, f"Job finished with status {status}")


if __name__ == "__main__":
    main()
