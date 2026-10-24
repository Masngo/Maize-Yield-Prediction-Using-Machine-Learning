"""Application configuration, driven by environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Config:
    # In production SECRET_KEY must be set; a random key per process is only a
    # development convenience (sessions reset on every restart).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'instance' / 'maize_yield.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MODEL_PATH = Path(os.environ.get("MODEL_PATH", PROJECT_ROOT / "models" / "maize_yield_model.joblib"))
    DATA_PATH = Path(os.environ.get("DATA_PATH", PROJECT_ROOT / "data" / "yield_maize_df.csv"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
