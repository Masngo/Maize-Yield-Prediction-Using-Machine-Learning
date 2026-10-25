import pytest
from conftest import login

from maize_yield import create_app
from maize_yield.config import PROJECT_ROOT
from maize_yield.extensions import db
from maize_yield.models import Prediction, User
from maize_yield.weather import DISTRICTS, WeatherService, WeatherUnavailable, describe

PAYLOAD = {
    "Year": 2022,
    "Average_Rainfall_mm_per_year": 1000,
    "Pesticides_Tonnes": 30000,
    "Avg_Temp": 21,
    "Area": "Mazowe",
}


def fake_raw(temp=24.0):
    return [
        {"current": {"time": "2026-10-25T12:00", "temperature_2m": temp + i * 0.1, "relative_humidity_2m": 50 + i,
                     "precipitation": 0.0, "weather_code": 2, "wind_speed_10m": 10.0 + i}}
        for i, _ in enumerate(DISTRICTS)
    ]


# ---------- live what-if predictor ----------

def test_preview_returns_curve_bars_and_heatmap_without_saving(client, app):
    login(client, "alice")
    data = client.post("/api/preview", json=PAYLOAD).get_json()
    assert data["prediction"] > 0
    assert len(data["curve"]["x"]) == len(data["curve"]["y"]) == 15
    assert data["curve"]["x"] == sorted(data["curve"]["x"])
    assert len(data["by_area"]) == 15
    heat = data["heatmap"]
    assert len(heat["areas"]) == 15 and len(heat["rainfall"]) == 5
    assert len(heat["values"]) == 15 and all(len(row) == 5 for row in heat["values"])
    with app.app_context():
        assert Prediction.query.count() == 0  # previews are never stored


def test_preview_matches_saved_prediction(client):
    login(client, "alice")
    preview = client.post("/api/preview", json=PAYLOAD).get_json()["prediction"]
    saved = client.post("/predict", json=PAYLOAD).get_json()["prediction"]
    assert preview == pytest.approx(saved)


def test_preview_by_area_contains_the_selected_district(client):
    login(client, "alice")
    data = client.post("/api/preview", json=PAYLOAD).get_json()
    entry = next(a for a in data["by_area"] if a["area"] == "Mazowe")
    assert entry["value"] == pytest.approx(data["prediction"])


def test_preview_validation_and_gating(client):
    assert client.post("/api/preview", json=PAYLOAD).status_code == 302
    login(client, "alice")
    assert client.post("/api/preview", json={**PAYLOAD, "Area": "Nowhere"}).status_code == 400
    assert client.post("/api/preview", json={**PAYLOAD, "Avg_Temp": "x"}).status_code == 400
    assert client.post("/api/preview", data="nope", content_type="text/plain").status_code == 400
    client.get("/logout")
    login(client, "bob")
    assert client.post("/api/preview", json=PAYLOAD).status_code == 403


# ---------- weather ----------

def test_weather_service_parses_caches_and_flags_stale():
    calls = []

    def fetcher():
        calls.append(1)
        if len(calls) > 1:
            raise OSError("network down")
        return fake_raw()

    service = WeatherService(fetcher=fetcher, ttl=0.0, retry_after=0.0)  # ttl 0 => always try to refresh
    first = service.get()
    assert first["stale"] is False and first["source"] == "Open-Meteo"
    assert [d["area"] for d in first["districts"]] == list(DISTRICTS)
    assert first["districts"][0]["summary"] == "Partly cloudy"
    second = service.get()  # refresh fails, last good reading is served
    assert second["stale"] is True and second["districts"] == first["districts"]


def test_weather_service_caches_between_requests():
    calls = []
    service = WeatherService(fetcher=lambda: calls.append(1) or fake_raw(), ttl=600)
    service.get()
    service.get()
    assert len(calls) == 1


def test_weather_unavailable_without_cache():
    def broken():
        raise OSError("offline")

    with pytest.raises(WeatherUnavailable):
        WeatherService(fetcher=broken, retry_after=0.0).get()


def test_weather_rejects_malformed_payload():
    service = WeatherService(fetcher=lambda: [{"current": {}}], retry_after=0.0)  # wrong length
    with pytest.raises(WeatherUnavailable):
        service.get()


def test_describe_weather_codes():
    assert describe(0) == "Clear sky" and describe(95) == "Thunderstorm" and describe(12345) == "Unknown"


def _weather_app(tmp_path, model_path, fetcher):
    app = create_app(
        {
            "TESTING": True,
            "AUTO_TRAIN": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "t",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'w.db'}",
            "MODEL_PATH": model_path,
            "DATA_PATH": PROJECT_ROOT / "data" / "yield_maize_df.csv",
            "WEATHER_FETCHER": fetcher,
        }
    )
    with app.app_context():
        user = User(username="alice", role="User")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
    return app


def test_weather_endpoint_requires_login_and_returns_districts(tmp_path, model_path):
    client = _weather_app(tmp_path, model_path, fake_raw).test_client()
    assert client.get("/api/weather").status_code == 302
    login(client, "alice")
    data = client.get("/api/weather").get_json()
    assert len(data["districts"]) == 15 and data["stale"] is False
    assert {"area", "lat", "lon", "temp", "humidity", "wind", "rain", "summary"} <= data["districts"][0].keys()


def test_weather_endpoint_returns_503_when_unreachable(tmp_path, model_path):
    def offline():
        raise OSError("offline")

    client = _weather_app(tmp_path, model_path, offline).test_client()
    login(client, "alice")
    response = client.get("/api/weather")
    assert response.status_code == 503 and "error" in response.get_json()
