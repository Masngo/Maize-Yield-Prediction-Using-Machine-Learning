import pytest

from maize_yield import create_app
from maize_yield.config import PROJECT_ROOT
from maize_yield.extensions import db
from maize_yield.models import User


@pytest.fixture(scope="session")
def model_path(tmp_path_factory):
    return tmp_path_factory.mktemp("model") / "model.joblib"


@pytest.fixture()
def app(tmp_path, model_path):
    app = create_app(
        {
            "TESTING": True,
            "AUTO_TRAIN": True,  # trains once into the session-scoped temp path
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "MODEL_PATH": model_path,
            "DATA_PATH": PROJECT_ROOT / "data" / "yield_maize_df.csv",
        }
    )
    with app.app_context():
        for name, role in [("alice", "User"), ("bob", "Expert"), ("root", "Admin")]:
            user = User(username=name, role=role)
            user.set_password("password123")
            db.session.add(user)
        db.session.commit()
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password="password123"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=False)


@pytest.fixture()
def user_client(client):
    login(client, "alice")
    return client
