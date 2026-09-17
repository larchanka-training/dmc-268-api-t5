"""Transport-only health routes; no database or external service is needed."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "Welcome to DMC-268 Team 5 API"}


@router.get("/health")
def health_check():
    return {"status": "ok"}
