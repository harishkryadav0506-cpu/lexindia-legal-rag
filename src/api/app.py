"""
src/api/app.py — ASGI application entrypoint for LexIndia.
Re-exports FastAPI app from src.api.main for compatibility with uvicorn src.api.app:app.
"""

from src.api.main import app

__all__ = ["app"]
