from datetime import date

import pytest
from conftest import login

from maize_yield.weather import (
    DISTRICTS,
    WeatherService,
    WeatherUnavailable,
    YearService,
    aggregate_daily,
    compass,
    wind_pressure_pa,
)


def hourly(start_day, days, temp=20.0):
    """Fake hourly payload covering `days` whole days starting at start_day (a date)."""
    times, temps, hum, rain, pres, wind = [], [], [], [], [], []
    for d in range(days):
        day = date.fromordinal(start_day.toordinal() + d).isoformat()
        for h in range(24):
            times.append(f"{day}T{h:02d}:00")
            temps.append(temp + h * 0.1)
            hum.append(60.0)
            rain.append(0.5 if h == 3 else 0.0)
            pres.append(1015.0)
            wind.append(10.0)
    return {"time": times, "temperature_2m": temps, "relative_humidity_2m": hum, "precipitation": rain,
            "pressure_msl": pres, "wind_speed_10m": wind}


# ---------- physics helpers ----------

def test_wind_pressure_formula():
    # 20 m/s (72 km/h) at standard conditions: q = 0.5 * rho * v^2 ~ 0.5 * 1.2 * 400 ~ 240 Pa
    q = wind_pressure_pa(72.0, 1013.25, 15.0)
    assert 235 < q < 250
    assert wind_pressure_pa(0.0, 1010, 20) == 0.0
    assert wind_pressure_pa(None, 1010, 20) is None
    assert wind_pressure_pa(36.0, None, None) > 0  # falls back to standard air


def test_compass_points():
    assert [compass(d) for d in (0, 90, 180, 270, 350, 22)] == ["N", "E", "S", "W", "N", "NNE"]
    assert compass(None) is None


# ---------- daily aggregation ----------

def test_aggregate_daily_summarises_each_day():
    days = aggregate_daily(hourly(date(2026, 3, 1), 2))
    assert set(days) == {"2026-03-01", "2026-03-02"}
    day = days["2026-03-01"]
    assert day["tmin"] == 20.0 and day["tmax"] == 22.3 and day["temp"] == 21.2
    assert day["humidity"] == 60.0 and day["pressure"] == 1015.0 and day["wind"] == 10.0
    assert day["rain"] == 0.5 and day["wind_pressure"] > 0


def test_aggregate_daily_skips_missing_values():
    data = hourly(date(2026, 3, 1), 1)
    data["temperature_2m"][0] = None
    data["relative_humidity_2m"] = [None] * 24
    day = aggregate_daily(data)["2026-03-01"]
    assert day["humidity"] is None and day["temp"] is not None


# ---------- YearService ----------

TODAY = date(2026, 10, 25)


def make_service(**overrides):
    calls = {"archive": 0, "forecast": 0}

    def archive(lat, lon, start, end):
        calls["archive"] += 1
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        return hourly(first, (last - first).days + 1)

    def forecast(lat, lon, past_days, forecast_days):
        calls["forecast"] += 1
        first = date.fromordinal(TODAY.toordinal() - past_days)
        return hourly(first, past_days + forecast_days, temp=25.0)

    service = YearService(archive=overrides.get("archive", archive), forecast=overrides.get("forecast", forecast),
                          clock=lambda: TODAY)
    return service, calls


def test_year_has_every_day_with_correct_kinds():
    service, _ = make_service()
    data = service.get("Mazowe")
    assert data["year"] == 2026 and data["today"] == "2026-10-25" and len(data["days"]) == 365
    assert data["days"][0]["date"] == "2026-01-01" and data["days"][0]["doy"] == 1
    assert data["days"][-1]["date"] == "2026-12-31" and data["days"][-1]["doy"] == 365
    by_date = {d["date"]: d for d in data["days"]}
    assert by_date["2026-06-15"]["kind"] == "observed"
    assert by_date["2026-10-25"]["kind"] == "observed"       # today
    assert by_date["2026-11-05"]["kind"] == "forecast"
    assert by_date["2026-11-10"]["kind"] is None and "temp" not in by_date["2026-11-10"]  # beyond forecast range
    assert by_date["2026-10-20"]["temp"] > 24                 # recent days come from the forecast service
    assert data["partial"] is False


def test_year_is_cached():
    service, calls = make_service()
    service.get("Mazowe")
    service.get("Mazowe")
    assert calls == {"archive": 1, "forecast": 1}
    service.get("Seke")
    assert calls == {"archive": 2, "forecast": 2}


def test_year_partial_when_archive_fails():
    def broken_archive(*_):
        raise OSError("offline")

    service, _ = make_service(archive=broken_archive)
    data = service.get("Mazowe")
    assert data["partial"] is True
    by_date = {d["date"]: d for d in data["days"]}
    assert by_date["2026-03-01"]["kind"] is None and by_date["2026-10-24"]["kind"] == "observed"


def test_year_unavailable_when_everything_fails():
    def broken(*_):
        raise OSError("offline")

    service, _ = make_service(archive=broken, forecast=broken)
    with pytest.raises(WeatherUnavailable):
        service.get("Mazowe")


def test_year_rejects_unknown_district():
    service, _ = make_service()
    with pytest.raises(KeyError):
        service.get("Atlantis")


def test_year_handles_new_years_day():
    seen = {}

    def forecast(lat, lon, past_days, forecast_days):
        seen.update(past=past_days, ahead=forecast_days)
        return hourly(date(2027, 1, 1), forecast_days)

    service = YearService(archive=lambda *a: pytest.fail("no archive needed on Jan 1"), forecast=forecast,
                          clock=lambda: date(2027, 1, 1))
    data = service.get("Bindura")
    assert seen == {"past": 0, "ahead": 16} and data["days"][0]["kind"] == "observed"


def test_year_handles_leap_year_end():
    service = YearService(
        archive=lambda *a: hourly(date(2028, 1, 1), 1),
        forecast=lambda *a: hourly(date(2028, 12, 25), 7),
        clock=lambda: date(2028, 12, 25),
    )
    data = service.get("Bindura")
    assert len(data["days"]) == 366 and data["days"][-1]["date"] == "2028-12-31"


# ---------- endpoints ----------

def test_current_weather_includes_humidity_wind_and_pressure():
    current = {
        "temperature_2m": 25.0, "relative_humidity_2m": 55, "precipitation": 0.0, "weather_code": 1,
        "wind_speed_10m": 18.0, "wind_direction_10m": 95, "wind_gusts_10m": 30.0, "pressure_msl": 1012.4,
    }
    raw = [{"current": current} for _ in DISTRICTS]
    row = WeatherService(fetcher=lambda: raw).get()["districts"][0]
    assert row["pressure"] == 1012.4 and row["wind_dir"] == "E" and row["gust"] == 30.0
    assert row["humidity"] == 55 and 14 < row["wind_pressure"] < 16  # 18 km/h = 5 m/s -> ~15 Pa


def test_year_endpoint(tmp_path, model_path):
    from test_live import _weather_app  # reuse the helper that builds an app with fake weather

    app = _weather_app(tmp_path, model_path, lambda: [])
    app.extensions["weather_year"] = make_service()[0]
    client = app.test_client()
    assert client.get("/api/weather/year?area=Mazowe").status_code == 302  # login required
    login(client, "alice")
    data = client.get("/api/weather/year?area=Mazowe").get_json()
    assert len(data["days"]) == 365 and data["area"] == "Mazowe"
    assert client.get("/api/weather/year?area=Nowhere").status_code == 400
    assert client.get("/api/weather/year").status_code == 400
