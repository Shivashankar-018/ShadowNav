"""Build a regular latitude/longitude grid over the study area."""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt

import config


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * radius_km * atan2(sqrt(a), sqrt(1 - a))


def build_grid(
    center_lat: float | None = None,
    center_lon: float | None = None,
) -> list[dict]:
    """
    Return square cells covering the study box.

    Each cell has centre coordinates and a closed ring in GeoJSON order
    (longitude, latitude).
    """
    lat0 = config.MAP_LAT if center_lat is None else center_lat
    lon0 = config.MAP_LON if center_lon is None else center_lon
    n = config.GRID_CELLS
    half = config.GRID_HALF_SIZE_DEG
    step = (2 * half) / n

    cells = []
    south = lat0 - half
    west = lon0 - half
    for row in range(n):
        for col in range(n):
            lat_min = south + row * step
            lon_min = west + col * step
            lat_max = lat_min + step
            lon_max = lon_min + step
            lat_c = (lat_min + lat_max) / 2
            lon_c = (lon_min + lon_max) / 2
            ring = [
                [lon_min, lat_min],
                [lon_max, lat_min],
                [lon_max, lat_max],
                [lon_min, lat_max],
                [lon_min, lat_min],
            ]
            cells.append(
                {
                    "id": f"r{row}c{col}",
                    "row": row,
                    "col": col,
                    "lat": lat_c,
                    "lon": lon_c,
                    "distance_to_centre_km": round(
                        haversine_km(lat_c, lon_c, lat0, lon0), 3
                    ),
                    "ring": ring,
                }
            )
    return cells
