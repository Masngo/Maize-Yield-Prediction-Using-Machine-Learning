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

from .extensions import db
from .models import ROLES, Prediction, User

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
    return render_template("expert/dashboard.html", predictions=Prediction.query.order_by(Prediction.id.desc()).all())


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
