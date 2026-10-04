"""
Weather client for Open-Meteo.

Open-Meteo needs no API key for this student/non-commercial use.
Docs: https://open-meteo.com/en/docs

This module talks to Open-Meteo from the Flask server only.
The browser never calls Open-Meteo directly.
"""

from __future__ import annotations

import time
from typing import Any

import requests

import config

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Fields we actually request. Names match Open-Meteo, not invented names.
CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "cloud_cover",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
)

# WMO Weather interpretation codes used by Open-Meteo.
# This table is our readable label, not an extra API field.
WMO_WEATHER_CODE = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class WeatherServiceError(Exception):
    """Raised when weather cannot be fetched or parsed."""


def _cache_key(lat: float, lon: float) -> str:
    return f"{lat:.3f},{lon:.3f}"


def _weather_condition(code: Any) -> str:
    if code is None:
        return "Unknown"
    try:
        return WMO_WEATHER_CODE.get(int(code), f"WMO code {int(code)}")
    except (TypeError, ValueError):
        return "Unknown"


def _normalise(payload: dict[str, Any], lat: float, lon: float, cached: bool) -> dict[str, Any]:
    current = payload.get("current") or {}
    units = payload.get("current_units") or {}

    return {
        "ok": True,
        "provider": "open-meteo",
        "cached": cached,
        "latitude": payload.get("latitude", lat),
        "longitude": payload.get("longitude", lon),
        "elevation_m": payload.get("elevation"),
        "timezone": payload.get("timezone"),
        "timestamp": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "apparent_temperature_c": current.get("apparent_temperature"),
        "relative_humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "cloud_cover_percent": current.get("cloud_cover"),
        "precipitation_mm": current.get("precipitation"),
        "shortwave_radiation_wm2": current.get("shortwave_radiation"),
        "weather_code": current.get("weather_code"),
        "weather_condition": _weather_condition(current.get("weather_code")),
        "units": {
            "temperature_c": units.get("temperature_2m", "°C"),
            "relative_humidity_percent": units.get("relative_humidity_2m", "%"),
            "wind_speed_kmh": units.get("wind_speed_10m", "km/h"),
            "cloud_cover_percent": units.get("cloud_cover", "%"),
            "precipitation_mm": units.get("precipitation", "mm"),
            "shortwave_radiation_wm2": units.get("shortwave_radiation", "W/m²"),
        },
        "note": (
            "These values come from a weather model grid, not a street thermometer. "
            "They are not hyper-local road temperatures."
        ),
    }


def get_current_weather(lat: float, lon: float, use_cache: bool = True) -> dict[str, Any]:
    """Fetch current weather for one point. Result is a clean dictionary."""
    key = _cache_key(lat, lon)
    now = time.time()

    if use_cache and key in _cache:
        expires_at, data = _cache[key]
        if now < expires_at:
            copied = dict(data)
            copied["cached"] = True
            return copied

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(CURRENT_FIELDS),
        "timezone": "auto",
        "wind_speed_unit": "kmh",
    }

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=config.WEATHER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise WeatherServiceError("Weather request timed out.") from exc
    except requests.RequestException as exc:
        raise WeatherServiceError("Weather service is unavailable.") from exc
    except ValueError as exc:
        raise WeatherServiceError("Weather response was not valid JSON.") from exc

    if not isinstance(payload, dict) or "current" not in payload:
        raise WeatherServiceError("Weather response was missing current conditions.")

    normalised = _normalise(payload, lat, lon, cached=False)
    _cache[key] = (now + config.WEATHER_CACHE_SECONDS, normalised)
    return normalised
