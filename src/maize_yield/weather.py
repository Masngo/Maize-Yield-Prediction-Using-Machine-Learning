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
from datetime import datetime, timezone
from urllib.parse import urlencode

API_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_VARIABLES = "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"

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
