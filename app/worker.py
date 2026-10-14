from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Short interval so the health-check key expires soon after the worker dies.
    health_check_interval = 10
