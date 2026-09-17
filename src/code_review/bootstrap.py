"""Composition root. Importing the app never connects to or migrates a database."""

from fastapi import FastAPI

from code_review.adapters.inbound.http import router


def create_app() -> FastAPI:
    app = FastAPI(title="DMC-268 API", version="0.1.0")
    app.include_router(router)
    return app
