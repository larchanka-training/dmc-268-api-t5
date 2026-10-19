from fastapi import FastAPI

from app.api import healthcheck
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="DMC-268 API", version=settings.release_tag)
app.include_router(healthcheck.router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to DMC-268 Team 5 API"}
