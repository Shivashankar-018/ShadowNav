"""
Prototype hyper-local heat layer.

This is NOT a trained machine-learning model and NOT medical guidance.

What is real:
- Base air temperature, humidity, and solar radiation from Open-Meteo (model grid).

What is a prototype proxy (not measured at the street):
- An urban-core offset that is larger near the study-area centre.
  Real cities often have a heat-island peak toward dense built-up cores,
  but we do not yet have building or vegetation maps, so this offset is
  only a demonstration spatial pattern.

Formula:
  estimated_temp_c = T_air
                   + UHI_MAX * (1 - min(1, distance_km / RADIUS_km))
                   + solar_bump

  solar_bump = 0.4 if shortwave_radiation > 500 W/m² else 0

Risk bands are project-defined from estimated_temp_c:
  Low < 28, Moderate < 32, High < 36, Very High >= 36  (degrees C)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import config
from gis.grid import build_grid, haversine_km
from services.weather_service import get_current_weather

RISK_COLORS = {
    "Low": "#2b83ba",
    "Moderate": "#abdda4",
    "High": "#fdae61",
    "Very High": "#d7191c",
}


def classify_heat_risk(temp_c: float | None) -> str:
    if temp_c is None:
        return "Low"
    if temp_c < 28:
        return "Low"
    if temp_c < 32:
        return "Moderate"
    if temp_c < 36:
        return "High"
    return "Very High"


def _solar_bump(shortwave: Any) -> float:
    try:
        value = float(shortwave)
    except (TypeError, ValueError):
        return 0.0
    if value > 500:
        return 0.4
    return 0.0


def _uhi_proxy_c(distance_km: float) -> float:
    radius = max(config.UHI_RADIUS_KM, 0.001)
    closeness = 1.0 - min(1.0, distance_km / radius)
    return config.UHI_MAX_OFFSET_C * closeness


def estimate_temperature_at(
    lat: float,
    lon: float,
    center_lat: float,
    center_lon: float,
    t_air: float,
    solar: float,
) -> dict[str, Any]:
    """Prototype heat estimate at one point (not a street thermometer)."""
    distance_km = haversine_km(lat, lon, center_lat, center_lon)
    uhi = _uhi_proxy_c(distance_km)
    estimated = round(float(t_air) + uhi + solar, 2)
    risk = classify_heat_risk(estimated)
    return {
        "estimated_temp_c": estimated,
        "uhi_proxy_c": round(uhi, 2),
        "solar_bump_c": solar,
        "heat_risk": risk,
        "color": RISK_COLORS[risk],
        "distance_to_centre_km": round(distance_km, 3),
    }


def build_heatmap_geojson(lat: float, lon: float) -> dict[str, Any]:
    weather = get_current_weather(lat, lon)
    t_air = weather.get("temperature_c")
    if t_air is None:
        raise ValueError("Weather response had no temperature_c.")

    solar = _solar_bump(weather.get("shortwave_radiation_wm2"))
    cells = build_grid(lat, lon)
    features = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for cell in cells:
        estimate = estimate_temperature_at(
            cell["lat"], cell["lon"], lat, lon, float(t_air), solar
        )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": cell["id"],
                    "latitude": cell["lat"],
                    "longitude": cell["lon"],
                    "estimated_temp_c": estimate["estimated_temp_c"],
                    "base_temp_c": t_air,
                    "uhi_proxy_c": estimate["uhi_proxy_c"],
                    "solar_bump_c": estimate["solar_bump_c"],
                    "heat_risk": estimate["heat_risk"],
                    "color": estimate["color"],
                    "timestamp": weather.get("timestamp") or timestamp,
                    "method": "prototype-uhi-offset",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [cell["ring"]],
                },
            }
        )

    return {
        "ok": True,
        "type": "FeatureCollection",
        "features": features,
        "legend": [
            {"label": "Low", "color": RISK_COLORS["Low"], "rule": "< 28 °C"},
            {"label": "Moderate", "color": RISK_COLORS["Moderate"], "rule": "28–32 °C"},
            {"label": "High", "color": RISK_COLORS["High"], "rule": "32–36 °C"},
            {"label": "Very High", "color": RISK_COLORS["Very High"], "rule": "≥ 36 °C"},
        ],
        "disclaimer": (
            "Colours are a prototype heat-risk layer for this project. "
            "They are not medical safety classes. Spatial offsets are not "
            "street thermometer readings. OSM tiles do not contain temperature."
        ),
        "weather_timestamp": weather.get("timestamp"),
        "cell_count": len(features),
    }
