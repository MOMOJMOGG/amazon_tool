"""FastAPI application entry point."""

from app.app import app

# This allows uvicorn app.main:app to work
__all__ = ["app"]