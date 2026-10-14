import asyncio

from app.worker import WorkerSettings, ping


def test_ping_returns_pong() -> None:
    assert asyncio.run(ping({})) == "pong"


def test_worker_registers_ping() -> None:
    assert ping in WorkerSettings.functions


def test_worker_uses_redis_from_settings() -> None:
    redis = WorkerSettings.redis_settings

    assert redis.host == "localhost"
    assert redis.port == 6379
    assert redis.database == 0
