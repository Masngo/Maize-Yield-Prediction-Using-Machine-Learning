from conftest import login

VALID = {
    "Year": 2022,
    "Average_Rainfall_mm_per_year": 1200,
    "Pesticides_Tonnes": 40000,
    "Avg_Temp": 21.5,
    "Area": "Bindura",
}


def test_login_redirects_by_role(client):
    assert login(client, "alice").headers["Location"].endswith("/")
    client.get("/logout")
    assert login(client, "bob").headers["Location"].endswith("/expert")
    client.get("/logout")
    assert login(client, "root").headers["Location"].endswith("/admin")


def test_bad_login_is_rejected(client):
    response = login(client, "alice", "wrong-password")
    assert response.status_code == 200
    assert b"Login unsuccessful" in response.data


def test_dashboards_require_login(client):
    assert client.get("/admin").status_code == 302
    assert client.post("/predict", json=VALID).status_code == 302


def test_role_gating(client):
    login(client, "alice")
    assert client.get("/admin").status_code == 403
    assert client.get("/expert").status_code == 403


def test_user_page_lists_all_areas(user_client, app):
    html = user_client.get("/").data.decode()
    for area in app.extensions["predictor"].areas:
        assert f'value="{area}"' in html
    assert len(app.extensions["predictor"].areas) == 15


def test_predict_returns_plausible_positive_yield(user_client):
    response = user_client.post("/predict", json=VALID)
    assert response.status_code == 200
    prediction = response.get_json()["prediction"]
    assert 1_000 < prediction < 300_000  # hg/ha; the training data spans roughly this range


def test_predict_is_recorded_for_experts(client):
    login(client, "alice")
    client.post("/predict", json=VALID)
    client.get("/logout")
    login(client, "bob")
    assert b"Bindura" in client.get("/expert").data


def test_predict_validation(user_client):
    assert user_client.post("/predict", json={**VALID, "Area": "Atlantis"}).status_code == 400
    assert user_client.post("/predict", json={**VALID, "Avg_Temp": "hot"}).status_code == 400
    assert user_client.post("/predict", json={k: v for k, v in VALID.items() if k != "Year"}).status_code == 400
    assert user_client.post("/predict", data="not json", content_type="text/plain").status_code == 400


def test_admin_user_lifecycle(client):
    login(client, "root")
    client.post("/admin/create_user", data={"username": "carol", "password": "longenough1", "role": "User"})
    assert b"carol" in client.get("/admin").data
    client.post("/admin/create_user", data={"username": "dave", "password": "short", "role": "User"})
    assert b"dave" not in client.get("/admin").data
    client.get("/logout")
    assert login(client, "carol", "longenough1").status_code == 302


def test_password_hash_is_never_rendered(client, app):
    from maize_yield.models import User

    login(client, "root")
    with app.app_context():
        alice = User.query.filter_by(username="alice").one()
        user_id, stored_hash = alice.id, alice.password
    assert stored_hash.encode() not in client.get(f"/admin/update_user/{user_id}").data
