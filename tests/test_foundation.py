"""Import direction and compatibility of the existing API entry point."""

import ast
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import configure_mappers

from code_review.adapters.outbound.postgres import models  # noqa: F401
from code_review.adapters.outbound.postgres.base import Base
from code_review.bootstrap import create_app

ROOT = Path(__file__).resolve().parents[1]


async def test_existing_http_routes_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        assert (await client.get("/")).json() == {"message": "Welcome to DMC-268 Team 5 API"}
        assert (await client.get("/health")).json() == {"status": "ok"}


def test_domain_and_application_do_not_import_infrastructure():
    forbidden = ("fastapi", "sqlalchemy", "psycopg", "ollama", "code_review.adapters")
    for layer in ("domain", "application"):
        for file in (ROOT / "src/code_review" / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text())):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                assert not any(name.startswith(forbidden) for name in names), file


def test_all_34_mappers_configure():
    configure_mappers()
    assert len(Base.metadata.tables) == 34
