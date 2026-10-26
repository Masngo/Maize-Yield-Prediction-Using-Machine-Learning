"""Live weather for each district, from the free Open-Meteo API (no API key needed).

One request fetches all districts; results are cached for ``ttl`` seconds so that many
dashboard viewers never trigger more than one upstream call per interval. If the API is
unreachable we keep serving the last good reading (flagged ``stale``).

Open-Meteo is free for non-commercial use: https://open-meteo.com/en/terms
Coordinates below are approximate district centres.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

API_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CURRENT_VARIABLES = (
    "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl"
)
HOURLY_VARIABLES = "temperature_2m,relative_humidity_2m,precipitation,pressure_msl,wind_speed_10m"
HARARE = timezone(timedelta(hours=2))  # Central Africa Time, no daylight saving
GAS_CONSTANT_AIR = 287.05  # J/(kg K)

# district -> (latitude, longitude); approximate centres, all in north-east Zimbabwe
DISTRICTS: dict[str, tuple[float, float]] = {
    "Bindura": (-17.30, 31.33),
    "Centenary": (-16.72, 31.10),
    "Chikomba": (-19.02, 30.88),
    "Guruve": (-16.66, 30.70),
    "Hwedza": (-18.62, 31.57),
    "Marondera": (-18.18, 31.55),
    "Mazowe": (-17.52, 30.97),
    "Mrehwa": (-17.65, 31.78),
    "Mt Darwin": (-16.77, 31.58),
    "Mudzi": (-17.03, 32.60),
    "Mutoko": (-17.40, 32.22),
    "Rushinga": (-16.72, 32.25),
    "Seke": (-18.02, 31.10),
    "Shamva": (-17.31, 31.57),
    "Uzumba": (-17.40, 31.95),
}

# WMO weather interpretation codes -> short text
_WMO = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


def wind_pressure_pa(wind_kmh: float | None, pressure_hpa: float | None, temp_c: float | None) -> float | None:
    """Dynamic wind pressure q = 1/2 * rho * v^2 in pascals, with air density from pressure and temperature."""
    if wind_kmh is None:
        return None
    pressure = 1013.25 if pressure_hpa is None else pressure_hpa
    temperature = 20.0 if temp_c is None else temp_c
    density = pressure * 100.0 / (GAS_CONSTANT_AIR * (temperature + 273.15))
    speed = wind_kmh / 3.6
    return round(0.5 * density * speed * speed, 1)


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((degrees % 360) / 22.5 + 0.5) % 16]


class WeatherUnavailable(RuntimeError):
    """No weather data could be fetched and none is cached."""


def describe(code: int | None) -> str:
    return _WMO.get(code, "Unknown") if code is not None else "Unknown"


def open_meteo_fetch(timeout: float = 8.0) -> list[dict]:
    """Fetch current conditions for every district in one request (order matches DISTRICTS)."""
    names = list(DISTRICTS)
    query = urlencode(
        {
            "latitude": ",".join(str(DISTRICTS[n][0]) for n in names),
            "longitude": ",".join(str(DISTRICTS[n][1]) for n in names),
            "current": CURRENT_VARIABLES,
            "timezone": "Africa/Harare",
        },
        safe=",",
    )
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": "maize-yield-app/2.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URL)
        payload = json.load(response)
    return payload if isinstance(payload, list) else [payload]  # a single location comes back as an object


class WeatherService:
    def __init__(self, fetcher: Callable[[], list[dict]] | None = None, ttl: float = 600.0, retry_after: float = 60.0):
        self._fetch = fetcher or open_meteo_fetch
        self._ttl = ttl
        self._retry_after = retry_after
        self._lock = threading.Lock()
        self._cache: dict | None = None
        self._cached_at = 0.0
        self._failed_at = 0.0

    @staticmethod
    def _parse(raw: list[dict]) -> list[dict]:
        names = list(DISTRICTS)
        if len(raw) != len(names):
            raise ValueError(f"expected {len(names)} locations, got {len(raw)}")
        rows = []
        for name, item in zip(names, raw, strict=True):
            cur = item["current"]
            code = cur.get("weather_code")
            rows.append(
                {
                    "area": name,
                    "lat": DISTRICTS[name][0],
                    "lon": DISTRICTS[name][1],
                    "temp": cur.get("temperature_2m"),
                    "humidity": cur.get("relative_humidity_2m"),
                    "wind": cur.get("wind_speed_10m"),
                    "wind_dir": compass(cur.get("wind_direction_10m")),
                    "gust": cur.get("wind_gusts_10m"),
                    "pressure": cur.get("pressure_msl"),
                    "wind_pressure": wind_pressure_pa(
                        cur.get("wind_speed_10m"), cur.get("pressure_msl"), cur.get("temperature_2m")
                    ),
                    "rain": cur.get("precipitation"),
                    "code": code,
                    "summary": describe(code),
                    "time": cur.get("time"),
                }
            )
        return rows

    def get(self) -> dict:
        with self._lock:
            now = time.monotonic()
            fresh = self._cache is not None and now - self._cached_at < self._ttl
            if fresh:
                return {**self._cache, "stale": False}
            recently_failed = self._failed_at and now - self._failed_at < self._retry_after
            if not recently_failed:
                try:
                    districts = self._parse(self._fetch())
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError):
                    self._failed_at = now
                else:
                    self._cache = {
                        "source": "Open-Meteo",
                        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "districts": districts,
                    }
                    self._cached_at, self._failed_at = now, 0.0
                    return {**self._cache, "stale": False}
            if self._cache is not None:
                return {**self._cache, "stale": True}
            raise WeatherUnavailable("Weather service is not reachable right now.")


# ---------------------------------------------------------------------------
# Day-by-day weather for a whole year (calendar heat map)
# ---------------------------------------------------------------------------

def _get_json(url: str, params: dict, timeout: float) -> dict:
    query = urlencode(params, safe=",")
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "maize-yield-app/2.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URLs)
        return json.load(response)


def open_meteo_archive(lat: float, lon: float, start: str, end: str, timeout: float = 25.0) -> dict:
    """Hourly history (ERA5) between two ISO dates, in Harare local time."""
    payload = _get_json(
        ARCHIVE_URL,
        {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
         "hourly": HOURLY_VARIABLES, "timezone": "Africa/Harare"},
        timeout,
    )
    return payload["hourly"]


def open_meteo_forecast_hourly(
    lat: float, lon: float, past_days: int, forecast_days: int, timeout: float = 20.0
) -> dict:
    """Recent days plus the forecast, hourly, in Harare local time."""
    payload = _get_json(
        API_URL,
        {"latitude": lat, "longitude": lon, "hourly": HOURLY_VARIABLES, "past_days": past_days,
         "forecast_days": forecast_days, "timezone": "Africa/Harare"},
        timeout,
    )
    return payload["hourly"]


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def aggregate_daily(hourly: dict) -> dict[str, dict]:
    """Collapse Open-Meteo hourly arrays into one summary per local date (keys are YYYY-MM-DD)."""
    buckets: dict[str, dict[str, list[float]]] = {}
    fields = ("temperature_2m", "relative_humidity_2m", "precipitation", "pressure_msl", "wind_speed_10m")
    for index, stamp in enumerate(hourly.get("time", [])):
        day = buckets.setdefault(stamp[:10], {name: [] for name in fields})
        for name in fields:
            series = hourly.get(name) or []
            value = series[index] if index < len(series) else None
            if value is not None:
                day[name].append(float(value))
    days = {}
    for day, b in buckets.items():
        wind = _mean(b["wind_speed_10m"])
        pressure = _mean(b["pressure_msl"])
        temp = _mean(b["temperature_2m"])
        days[day] = {
            "temp": temp,
            "tmin": round(min(b["temperature_2m"]), 1) if b["temperature_2m"] else None,
            "tmax": round(max(b["temperature_2m"]), 1) if b["temperature_2m"] else None,
            "humidity": _mean(b["relative_humidity_2m"]),
            "pressure": pressure,
            "wind": wind,
            "wind_max": round(max(b["wind_speed_10m"]), 1) if b["wind_speed_10m"] else None,
            "wind_pressure": wind_pressure_pa(wind, pressure, temp),
            "rain": round(sum(b["precipitation"]), 1) if b["precipitation"] else None,
        }
    return days


class YearService:
    """Daily weather for every day of the current year in one district.

    Days up to ~8 days ago come from the ERA5 archive (cached for hours); the last week and the
    next ~15 days come from the forecast service (cached for minutes).
    """

    def __init__(self, archive=None, forecast=None, clock: Callable[[], date] | None = None,
                 archive_ttl: float = 6 * 3600, forecast_ttl: float = 1200.0):
        self._archive = archive or open_meteo_archive
        self._forecast = forecast or open_meteo_forecast_hourly
        self._today = clock or (lambda: datetime.now(HARARE).date())
        self._archive_ttl, self._forecast_ttl = archive_ttl, forecast_ttl
        self._lock = threading.Lock()
        self._archive_cache: dict[tuple, tuple[float, dict]] = {}
        self._forecast_cache: dict[tuple, tuple[float, dict]] = {}

    def _cached(self, cache: dict, key: tuple, ttl: float, loader: Callable[[], dict]) -> dict:
        now = time.monotonic()
        hit = cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        try:
            value = loader()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError):
            if hit:
                return hit[1]  # serve the last good copy
            raise
        cache[key] = (now, value)
        return value

    def get(self, area: str) -> dict:
        if area not in DISTRICTS:
            raise KeyError(area)
        lat, lon = DISTRICTS[area]
        today = self._today()
        start, end = date(today.year, 1, 1), date(today.year, 12, 31)
        archive_end = today - timedelta(days=8)
        recent_start = max(start, today - timedelta(days=7))
        with self._lock:
            observed: dict[str, dict] = {}
            recent: dict[str, dict] = {}
            problems = 0
            if archive_end >= start:
                try:
                    observed = self._cached(
                        self._archive_cache, (area, start.year, archive_end), self._archive_ttl,
                        lambda: aggregate_daily(self._archive(lat, lon, start.isoformat(), archive_end.isoformat())),
                    )
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError):
                    problems += 1
            past_days = (today - recent_start).days
            forecast_days = min(16, (end - today).days + 1)
            try:
                recent = self._cached(
                    self._forecast_cache, (area, today, past_days, forecast_days), self._forecast_ttl,
                    lambda: aggregate_daily(self._forecast(lat, lon, past_days, forecast_days)),
                )
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError):
                problems += 1
        if problems and not observed and not recent:
            raise WeatherUnavailable("Daily weather is not reachable right now.")

        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            key = day.isoformat()
            values = recent.get(key) or observed.get(key)
            days.append({
                "date": key,
                "doy": offset + 1,
                **(values or {}),
                "kind": None if not values else ("observed" if day <= today else "forecast"),
            })
        return {"area": area, "year": today.year, "today": today.isoformat(), "source": "Open-Meteo",
                "partial": bool(problems), "days": days}
