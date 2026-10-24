"""Maize yield prediction web app (Zimbabwe)."""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask

from .config import Config
from .extensions import csrf, db, login_manager
from .ml import Predictor, train

__version__ = "2.0.0"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith("sqlite:///") and db_uri != "sqlite:///:memory:":
        Path(db_uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    model_path = Path(app.config["MODEL_PATH"])
    if not model_path.exists():
        if app.config.get("TESTING") and not app.config.get("AUTO_TRAIN"):
            raise RuntimeError(f"Model file not found: {model_path}")
        app.logger.warning("No trained model at %s - training one now.", model_path)
        train(app.config["DATA_PATH"], model_path)
    app.extensions["predictor"] = Predictor(model_path)

    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        from . import models  # noqa: F401  (register tables)

        db.create_all()

    _register_cli(app)
    return app


def _register_cli(app: Flask) -> None:
    from .models import ROLES, User

    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", type=click.Choice(ROLES), default="Admin", show_default=True)
    @click.password_option(help="Minimum 8 characters.")
    def create_user_cmd(username: str, role: str, password: str) -> None:
        """Create a user (use this to bootstrap the first admin)."""
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        if User.query.filter_by(username=username).first():
            raise click.ClickException(f"User '{username}' already exists.")
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created {role} '{username}'.")

    @app.cli.command("train-model")
    def train_model_cmd() -> None:
        """Re-train the model from data/yield_maize_df.csv and print metrics."""
        result = train(app.config["DATA_PATH"], app.config["MODEL_PATH"])
        click.echo(f"Best model: {result.best_model}")
        for name, m in result.metrics.items():
            click.echo(
                f"  {name:<18} CV R²={m['cv_r2']:.3f}  test R²={m['test_r2']:.3f}  "
                f"RMSE={m['test_rmse']:,.0f}  MAE={m['test_mae']:,.0f}"
            )
