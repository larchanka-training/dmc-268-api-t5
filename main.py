"""Compatibility entry point: uvicorn main:app."""

from code_review.bootstrap import create_app

app = create_app()
