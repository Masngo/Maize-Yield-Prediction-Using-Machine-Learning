"""Application configuration, driven by environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _database_uri() -> str:
    """Use DATABASE_URL when set (Render/Heroku style URLs are normalised for psycopg 3)."""
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        return f"sqlite:///{PROJECT_ROOT / 'instance' / 'maize_yield.db'}"
    for prefix in ("postgres://", "postgresql://"):
        if uri.startswith(prefix):
            return "postgresql+psycopg://" + uri[len(prefix):]
    return uri


class Config:
    # In production SECRET_KEY must be set; a random key per process is only a
    # development convenience (sessions reset on every restart).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MODEL_PATH = Path(os.environ.get("MODEL_PATH", PROJECT_ROOT / "models" / "maize_yield_model.joblib"))
    DATA_PATH = Path(os.environ.get("DATA_PATH", PROJECT_ROOT / "data" / "yield_maize_df.csv"))
    # Optional: create this admin on startup if it does not exist yet (for hosts without a shell).
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
