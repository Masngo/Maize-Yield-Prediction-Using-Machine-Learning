import importlib

from maize_yield import create_app
from maize_yield.config import PROJECT_ROOT
from maize_yield.models import User


def test_database_url_is_normalised(monkeypatch):
    from maize_yield import config

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert importlib.reload(config).Config.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert importlib.reload(config).Config.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://u:p@host/db"
    monkeypatch.delenv("DATABASE_URL")
    assert importlib.reload(config).Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///")


def _app(tmp_path, model_path, **extra):
    return create_app(
        {
            "TESTING": True,
            "AUTO_TRAIN": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'boot.db'}",
            "MODEL_PATH": model_path,
            "DATA_PATH": PROJECT_ROOT / "data" / "yield_maize_df.csv",
            **extra,
        }
    )


def test_admin_is_bootstrapped_from_settings(tmp_path, model_path):
    app = _app(tmp_path, model_path, ADMIN_USERNAME="boss", ADMIN_PASSWORD="long-enough-1")
    with app.app_context():
        boss = User.query.filter_by(username="boss").one()
        assert boss.role == "Admin" and boss.check_password("long-enough-1")
    _app(tmp_path, model_path, ADMIN_USERNAME="boss", ADMIN_PASSWORD="other-pass-2")  # must not duplicate/overwrite
    with app.app_context():
        assert User.query.filter_by(username="boss").count() == 1
        assert User.query.filter_by(username="boss").one().check_password("long-enough-1")


def test_short_bootstrap_password_is_ignored(tmp_path, model_path):
    app = _app(tmp_path, model_path, ADMIN_USERNAME="boss", ADMIN_PASSWORD="short")
    with app.app_context():
        assert User.query.count() == 0
