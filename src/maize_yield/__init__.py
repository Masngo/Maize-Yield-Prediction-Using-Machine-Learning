"""Maize yield prediction web app (Zimbabwe)."""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask

from .config import Config
from .extensions import csrf, db, login_manager
from .ml import Predictor, train
from .weather import WeatherService

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
    app.extensions["area_means"] = _historical_means(app)
    app.extensions["rain_range"] = _rain_range(app)
    app.extensions["weather"] = WeatherService(fetcher=app.config.get("WEATHER_FETCHER"))

    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        from . import models  # noqa: F401  (register tables)

        db.create_all()
        _bootstrap_admin(app)

    _register_cli(app)
    return app


def _historical_means(app: Flask) -> dict[str, float]:
    """Mean observed yield (hg/ha) per district in the training data, for chart comparisons."""
    from .ml import TARGET, load_data

    try:
        df = load_data(app.config["DATA_PATH"])
        return {area: float(v) for area, v in df.groupby("Area")[TARGET].mean().items()}
    except OSError:
        app.logger.warning("Training data not found; historical averages unavailable.")
        return {}


def _rain_range(app: Flask) -> tuple[float, float]:
    """Typical rainfall span (5th-95th percentile) used for the what-if curve and heat map."""
    from .ml import load_data

    try:
        rain = load_data(app.config["DATA_PATH"])["Average_Rainfall_mm_per_year"]
        return float(rain.quantile(0.05)), float(rain.quantile(0.95))
    except OSError:
        return 400.0, 1800.0


def _bootstrap_admin(app: Flask) -> None:
    """Create the admin named by ADMIN_USERNAME/ADMIN_PASSWORD if it is missing."""
    from .models import User

    username, password = app.config.get("ADMIN_USERNAME"), app.config.get("ADMIN_PASSWORD")
    if not username or not password:
        return
    if len(password) < 8:
        app.logger.warning("ADMIN_PASSWORD is shorter than 8 characters; admin not created.")
        return
    if User.query.filter_by(username=username).first():
        return
    admin = User(username=username, role="Admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    app.logger.info("Created admin user '%s'.", username)


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
