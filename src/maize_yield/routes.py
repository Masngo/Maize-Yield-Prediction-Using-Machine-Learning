from __future__ import annotations

from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from .extensions import db
from .models import ROLES, Prediction, User
from .weather import WeatherUnavailable

bp = Blueprint("main", __name__)

HOME_BY_ROLE = {"Admin": "main.admin_dashboard", "Expert": "main.expert_dashboard", "User": "main.index"}


def role_required(role: str):
    """Restrict a view to one role (403 for other logged-in users)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for(HOME_BY_ROLE.get(user.role, "main.login")))
        flash("Login unsuccessful. Please check username and password.", "danger")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


@bp.route("/")
@login_required
def index():
    if current_user.role != "User":
        return redirect(url_for(HOME_BY_ROLE.get(current_user.role, "main.login")))
    return render_template("user/index.html", areas=current_app.extensions["predictor"].areas)


@bp.route("/admin")
@role_required("Admin")
def admin_dashboard():
    return render_template("admin/dashboard.html", users=User.query.order_by(User.id).all())


@bp.route("/expert")
@role_required("Expert")
def expert_dashboard():
    latest = Prediction.query.order_by(Prediction.id.desc()).limit(50).all()
    return render_template("expert/dashboard.html", predictions=latest)


def _prediction_row(p: Prediction) -> dict:
    return {
        "id": p.id,
        "user": p.user_name,
        "year": p.year,
        "rainfall": p.average_rainfall,
        "pesticides": p.pesticides_tonnes,
        "temp": p.avg_temp,
        "area": p.area,
        "value": p.predicted_value,
    }


@bp.route("/api/stats")
@login_required
def api_stats():
    """Aggregate prediction data for the live expert charts (values in hg/ha)."""
    if current_user.role not in ("Expert", "Admin"):
        abort(403)
    by_area = (
        db.session.query(Prediction.area, func.count(Prediction.id), func.avg(Prediction.predicted_value))
        .group_by(Prediction.area)
        .order_by(func.count(Prediction.id).desc(), Prediction.area)
        .all()
    )
    total = sum(count for _, count, _ in by_area)
    overall = db.session.query(func.avg(Prediction.predicted_value)).scalar()
    by_year = (
        db.session.query(Prediction.year, func.count(Prediction.id))
        .group_by(Prediction.year)
        .order_by(Prediction.year)
        .all()
    )
    history = current_app.extensions.get("area_means", {})
    # What the same districts averaged historically, weighted by how often each was requested.
    known = [(count, history[area]) for area, count, _ in by_area if area in history]
    expected = sum(c * h for c, h in known) / sum(c for c, _ in known) if known else None
    latest = Prediction.query.order_by(Prediction.id.desc()).limit(200).all()
    by_user = (
        db.session.query(Prediction.user_name, func.count(Prediction.id))
        .group_by(Prediction.user_name)
        .order_by(func.count(Prediction.id).desc(), Prediction.user_name)
        .limit(10)
        .all()
    )
    return jsonify(
        total=total,
        average=float(overall) if overall is not None else None,
        by_area=[{"area": a, "count": c, "average": float(avg)} for a, c, avg in by_area],
        by_user=[{"user": u, "count": c} for u, c in by_user],
        by_year=[{"year": y, "count": c} for y, c in by_year],
        expected_historical=expected,
        recent=[_prediction_row(p) for p in latest[:50]],
        series=[{"id": p.id, "value": p.predicted_value} for p in reversed(latest[:20])],
        points=[_prediction_row(p) for p in latest],  # newest 200, for scatter plot and histogram
        historical=current_app.extensions.get("area_means", {}),
    )


@bp.route("/api/admin-stats")
@role_required("Admin")
def api_admin_stats():
    """System overview for the live admin charts."""
    roles = db.session.query(User.role, func.count(User.id)).group_by(User.role).order_by(User.role).all()
    per_user = (
        db.session.query(Prediction.user_name, func.count(Prediction.id))
        .group_by(Prediction.user_name)
        .order_by(func.count(Prediction.id).desc(), Prediction.user_name)
        .limit(10)
        .all()
    )
    by_area = (
        db.session.query(Prediction.area, func.count(Prediction.id))
        .group_by(Prediction.area)
        .order_by(func.count(Prediction.id).desc(), Prediction.area)
        .all()
    )
    recent = Prediction.query.order_by(Prediction.id.desc()).limit(10).all()
    return jsonify(
        users=sum(c for _, c in roles),
        predictions=Prediction.query.count(),
        by_role=[{"role": r, "count": c} for r, c in roles],
        per_user=[{"user": u, "count": c} for u, c in per_user],
        by_area=[{"area": a, "count": c} for a, c in by_area],
        recent=[_prediction_row(p) for p in recent],
    )


@bp.route("/api/my-stats")
@role_required("User")
def api_my_stats():
    """The signed-in user's own predictions, plus the dataset's historical mean yield per district."""
    mine = Prediction.query.filter_by(user_id=current_user.id)
    by_area = (
        db.session.query(Prediction.area, func.count(Prediction.id))
        .filter(Prediction.user_id == current_user.id)
        .group_by(Prediction.area)
        .order_by(func.count(Prediction.id).desc(), Prediction.area)
        .all()
    )
    latest = mine.order_by(Prediction.id.desc()).limit(20).all()
    return jsonify(
        total=sum(c for _, c in by_area),
        by_area=[{"area": a, "count": c} for a, c in by_area],
        recent=[_prediction_row(p) for p in reversed(latest[:8])],
        series=[{"id": p.id, "value": p.predicted_value} for p in reversed(latest)],
        points=[_prediction_row(p) for p in latest],
        historical=current_app.extensions.get("area_means", {}),
    )


def _parse_prediction_input(data: dict, areas: list[str]) -> dict:
    """Validate and coerce the JSON payload; raises ValueError with a user-facing message."""
    try:
        parsed = {
            "year": int(float(data["Year"])),
            "rainfall": float(data["Average_Rainfall_mm_per_year"]),
            "pesticides": float(data["Pesticides_Tonnes"]),
            "temp": float(data["Avg_Temp"]),
            "area": str(data["Area"]),
        }
    except KeyError as exc:
        raise ValueError(f"Missing field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("All numeric fields must be valid numbers.") from exc

    if not 1990 <= parsed["year"] <= 2100:
        raise ValueError("Year must be between 1990 and 2100.")
    if parsed["rainfall"] < 0 or parsed["pesticides"] < 0:
        raise ValueError("Rainfall and pesticides cannot be negative.")
    if not -10 <= parsed["temp"] <= 50:
        raise ValueError("Temperature must be between -10 and 50 °C.")
    if parsed["area"] not in areas:
        raise ValueError("Unknown area.")
    return parsed


@bp.route("/predict", methods=["POST"])
@role_required("User")
def predict():
    predictor = current_app.extensions["predictor"]
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object."), 400
    try:
        values = _parse_prediction_input(data, predictor.areas)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    value = predictor.predict(**values)
    db.session.add(
        Prediction(
            user_id=current_user.id,
            user_name=current_user.username,
            year=values["year"],
            average_rainfall=values["rainfall"],
            pesticides_tonnes=values["pesticides"],
            avg_temp=values["temp"],
            area=values["area"],
            predicted_value=value,
        )
    )
    db.session.commit()
    return jsonify(prediction=value, unit="hg/ha")


@bp.route("/api/preview", methods=["POST"])
@role_required("User")
def api_preview():
    """Live what-if: predictions for the current form values. Nothing is saved."""
    predictor = current_app.extensions["predictor"]
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object."), 400
    try:
        values = _parse_prediction_input(data, predictor.areas)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(predictor.what_if(**values, rain_range=current_app.extensions["rain_range"]))


@bp.route("/api/weather")
@login_required
def api_weather():
    """Current weather for every district (cached; see weather.py)."""
    try:
        return jsonify(current_app.extensions["weather"].get())
    except WeatherUnavailable as exc:
        return jsonify(error=str(exc)), 503


# --- Admin user management -------------------------------------------------


@bp.route("/admin/create_user", methods=["GET", "POST"])
@role_required("Admin")
def create_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        if not username or len(password) < 8 or role not in ROLES:
            flash("Username, role and a password of at least 8 characters are required.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "danger")
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for("main.admin_dashboard"))
    return render_template("admin/create_user.html")


@bp.route("/admin/update_user/<int:user_id>", methods=["GET", "POST"])
@role_required("Admin")
def update_user(user_id: int):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        taken = User.query.filter(User.username == username, User.id != user.id).first()
        if not username or role not in ROLES or (password and len(password) < 8):
            flash("Valid username and role are required; passwords need at least 8 characters.", "danger")
        elif taken:
            flash("That username is already taken.", "danger")
        else:
            user.username, user.role = username, role
            if password:  # leave the existing password untouched when the field is blank
                user.set_password(password)
            db.session.commit()
            return redirect(url_for("main.admin_dashboard"))
    return render_template("admin/update_user.html", user=user)


@bp.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@role_required("Admin")
def delete_user(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("main.admin_dashboard"))
    Prediction.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("main.admin_dashboard"))
