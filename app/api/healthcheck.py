from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


@router.get("/healthcheck")
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


# Legacy alias kept for backward compatibility.
@router.get("/health", include_in_schema=False)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
