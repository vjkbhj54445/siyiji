"""模块说明：Prometheus 指标输出。"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
import redis

from api.config import settings
from api.db import get_db_connection

router = APIRouter()

registry = CollectorRegistry()

run_status_total = Gauge(
    "automation_hub_run_status_total",
    "Number of runs by status",
    ["status"],
    registry=registry,
)
run_total = Gauge(
    "automation_hub_runs_total",
    "Total number of runs",
    registry=registry,
)
run_duration_avg = Gauge(
    "automation_hub_run_duration_seconds_avg",
    "Average run duration in seconds",
    registry=registry,
)
queue_length = Gauge(
    "automation_hub_queue_length",
    "RQ queue length (per primary queue)",
    registry=registry,
)


def _refresh_metrics() -> None:
    with get_db_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] or 0
        run_total.set(total)

        rows = conn.execute("SELECT status, COUNT(*) AS c FROM runs GROUP BY status").fetchall()
        for row in rows:
            run_status_total.labels(status=row["status"]).set(row["c"])

        avg = conn.execute(
            """
            SELECT AVG((julianday(completed_at) - julianday(started_at)) * 86400.0)
            FROM runs
            WHERE completed_at IS NOT NULL AND started_at IS NOT NULL
            """
        ).fetchone()[0]
        run_duration_avg.set(float(avg) if avg is not None else 0.0)

    try:
        queue_names = [name.strip() for name in settings.QUEUE_NAME.split(",") if name.strip()]
        queue_name = queue_names[0] if queue_names else "default"
        redis_conn = redis.from_url(settings.REDIS_URL)
        queue_length.set(redis_conn.llen(queue_name))
    except Exception:
        queue_length.set(-1)


@router.get("/metrics")
def metrics() -> Response:
    _refresh_metrics()
    payload = generate_latest(registry)
    return Response(payload, media_type=CONTENT_TYPE_LATEST)
