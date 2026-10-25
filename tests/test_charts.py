from conftest import login

PAYLOAD = {
    "Year": 2022,
    "Average_Rainfall_mm_per_year": 1200,
    "Pesticides_Tonnes": 40000,
    "Avg_Temp": 21.5,
}


def _predict(client, area):
    assert client.post("/predict", json={**PAYLOAD, "Area": area}).status_code == 200


def test_stats_api_is_role_gated(client):
    assert client.get("/api/stats").status_code == 302  # not logged in
    login(client, "alice")
    assert client.get("/api/stats").status_code == 403  # plain users cannot see everyone's data
    assert client.get("/api/my-stats").status_code == 200
    client.get("/logout")
    login(client, "bob")
    assert client.get("/api/my-stats").status_code == 403


def test_expert_stats_aggregate_predictions(client):
    login(client, "alice")
    for area in ("Bindura", "Bindura", "Mazowe"):
        _predict(client, area)
    client.get("/logout")
    login(client, "bob")

    data = client.get("/api/stats").get_json()
    assert data["total"] == 3
    assert [(a["area"], a["count"]) for a in data["by_area"]] == [("Bindura", 2), ("Mazowe", 1)]
    assert data["average"] > 0
    assert len(data["recent"]) == 3 and len(data["series"]) == 3
    assert [s["id"] for s in data["series"]] == sorted(s["id"] for s in data["series"])  # oldest -> newest


def test_empty_stats_are_safe(client):
    login(client, "bob")
    data = client.get("/api/stats").get_json()
    assert data["total"] == 0 and data["average"] is None and data["by_area"] == []


def test_user_stats_only_include_own_predictions_and_history(client):
    login(client, "alice")
    _predict(client, "Mazowe")
    data = client.get("/api/my-stats").get_json()
    assert data["total"] == 1 and data["recent"][0]["area"] == "Mazowe"
    assert 1_000 < data["historical"]["Mazowe"] < 300_000
    assert len(data["historical"]) == 15


def test_expert_stats_include_analysis_data(client):
    login(client, "alice")
    for area in ("Bindura", "Mazowe"):
        _predict(client, area)
    client.get("/logout")
    login(client, "bob")
    data = client.get("/api/stats").get_json()
    assert [u["user"] for u in data["by_user"]] == ["alice"] and data["by_user"][0]["count"] == 2
    assert len(data["points"]) == 2
    assert {"rainfall", "pesticides", "temp", "value", "area"} <= data["points"][0].keys()
    assert len(data["historical"]) == 15


def test_admin_stats_overview_and_gating(client):
    login(client, "alice")
    _predict(client, "Bindura")
    assert client.get("/api/admin-stats").status_code == 403
    client.get("/logout")
    login(client, "bob")
    assert client.get("/api/admin-stats").status_code == 403
    client.get("/logout")
    login(client, "root")
    data = client.get("/api/admin-stats").get_json()
    assert data["users"] == 3 and data["predictions"] == 1
    assert {r["role"]: r["count"] for r in data["by_role"]} == {"Admin": 1, "Expert": 1, "User": 1}
    assert data["per_user"] == [{"user": "alice", "count": 1}]


def test_user_stats_include_series(client):
    login(client, "alice")
    for _ in range(3):
        _predict(client, "Seke")
    data = client.get("/api/my-stats").get_json()
    assert len(data["series"]) == 3


def test_expert_stats_include_year_and_expected_history(client):
    login(client, "alice")
    for year in (2020, 2020, 2022):
        client.post("/predict", json={**PAYLOAD, "Year": year, "Area": "Mazowe"})
    client.get("/logout")
    login(client, "bob")
    data = client.get("/api/stats").get_json()
    assert data["by_year"] == [{"year": 2020, "count": 2}, {"year": 2022, "count": 1}]
    # every prediction was for Mazowe, so the expected historical value is exactly Mazowe's mean
    assert data["expected_historical"] == data["historical"]["Mazowe"]


def test_expected_history_is_none_without_predictions(client):
    login(client, "bob")
    data = client.get("/api/stats").get_json()
    assert data["expected_historical"] is None and data["by_year"] == []


def test_admin_stats_include_districts_and_feed(client):
    login(client, "alice")
    _predict(client, "Seke")
    client.get("/logout")
    login(client, "root")
    data = client.get("/api/admin-stats").get_json()
    assert data["by_area"] == [{"area": "Seke", "count": 1}]
    assert data["recent"][0]["user"] == "alice"


def test_user_stats_include_points(client):
    login(client, "alice")
    _predict(client, "Hwedza")
    point = client.get("/api/my-stats").get_json()["points"][0]
    assert point["area"] == "Hwedza" and point["rainfall"] == 1200
