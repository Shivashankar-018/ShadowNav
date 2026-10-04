"""
Walking-road network from OpenStreetMap via OSMnx.

GIS operations used here:
1. Bounding box around the study centre.
2. OSMnx queries Overpass for the pedestrian (`walk`) network.
3. OSMnx builds a NetworkX MultiDiGraph (nodes = junctions, edges = street segments).
4. Edge `length` is metres along the geometry.
5. We keep the largest connected piece (OSMnx retain_all=False).
6. GraphML cache so the next run does not download again.
7. Each edge midpoint gets the same prototype heat estimate as the grid.

OSM roads are geometry only. They are not temperature measurements.
"""

from __future__ import annotations

import json
import logging
import traceback
from threading import Lock
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
import requests
from geopandas import _compat as geopandas_compat

import config
from gis.heat_layer import RISK_COLORS, _solar_bump, estimate_temperature_at
from services.weather_service import get_current_weather

GRAPH_PATH = config.BASE_DIR / "data" / "processed" / "walk_network.graphml"
META_PATH = config.BASE_DIR / "data" / "processed" / "walk_network_meta.json"
OSM_CACHE = config.BASE_DIR / "data" / "raw" / "osmnx_cache"
logger = logging.getLogger(__name__)
GRAPH_DOWNLOAD_LOCK = Lock()
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api",
    "https://lz4.overpass-api.de/api",
)


class NetworkServiceError(Exception):
    """Raised when the walking graph cannot be downloaded or loaded."""


def study_bbox(center_lat: float, center_lon: float) -> tuple[float, float, float, float]:
    """OSMnx 2 bbox: (left, bottom, right, top) = (west, south, east, north)."""
    half = config.GRID_HALF_SIZE_DEG
    west = center_lon - half
    south = center_lat - half
    east = center_lon + half
    north = center_lat + half
    return (west, south, east, north)


def _configure_osmnx(overpass_url: str) -> None:
    OSM_CACHE.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(OSM_CACHE)
    ox.settings.requests_timeout = 180
    ox.settings.overpass_url = overpass_url
    # OSMnx expects unprojected bbox/polygon coordinates in EPSG:4326.
    ox.settings.default_crs = "EPSG:4326"


def _download_bbox_graph_without_pyproj(
    bbox: tuple[float, float, float, float], overpass_url: str
) -> nx.MultiDiGraph:
    """Download an unprojected walk graph when Windows blocks PyProj's DLL.

    This keeps OSMnx's walk filters, OSM response parser, and great-circle edge
    lengths, while querying by a slightly expanded bounding box directly. No
    coordinate projection is needed for this local route graph.
    """
    west, south, east, north = bbox
    # Roughly 500 m of buffer at Bengaluru's latitude, as OSMnx normally adds
    # before requesting a polygon network.
    buffer_deg = 0.005
    south -= buffer_deg
    north += buffer_deg
    west -= buffer_deg
    east += buffer_deg

    walk_filter = ox._overpass._get_network_filter("walk")
    query = (
        "[out:json][timeout:180];\n"
        f"way{walk_filter}({south},{west},{north},{east});\n"
        "(._;>;);\n"
        "out body;"
    )
    response = requests.post(
        f"{overpass_url.rstrip('/')}/interpreter",
        data={"data": query},
        headers={"User-Agent": "ShadowNav/0.1 (local student project)"},
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("elements"):
        raise ValueError("Overpass returned no walking roads for the study area.")

    # OSMnx builds the directed road graph and calculates edge lengths from
    # lat/lon coordinates. The walk network is bidirectional by OSMnx design.
    graph = ox.graph._create_graph([payload], bidirectional=True)
    if graph.number_of_edges() == 0:
        return graph

    largest_component = max(nx.weakly_connected_components(graph), key=len)
    return graph.subgraph(largest_component).copy()


def _meta_matches(center_lat: float, center_lon: float) -> bool:
    if not META_PATH.exists() or not GRAPH_PATH.exists():
        return False
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        abs(meta.get("lat", 0) - center_lat) < 1e-6
        and abs(meta.get("lon", 0) - center_lon) < 1e-6
        and abs(meta.get("half", 0) - config.GRID_HALF_SIZE_DEG) < 1e-9
    )


def load_walk_graph(center_lat: float, center_lon: float) -> nx.MultiDiGraph:
    """Load cached walk graph or download it once from OSM."""
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _meta_matches(center_lat, center_lon):
        return ox.load_graphml(GRAPH_PATH)

    with GRAPH_DOWNLOAD_LOCK:
        # A simultaneous /api/roads request may have finished the download
        # while this request waited for the lock.
        if _meta_matches(center_lat, center_lon):
            return ox.load_graphml(GRAPH_PATH)

        bbox = study_bbox(center_lat, center_lon)
        graph = None
        errors: list[Exception] = []
        used_endpoint = None

        for endpoint in OVERPASS_ENDPOINTS:
            _configure_osmnx(endpoint)
            try:
                if geopandas_compat.HAS_PYPROJ:
                    graph = ox.graph_from_bbox(
                        bbox,
                        network_type="walk",
                        simplify=True,
                        retain_all=False,
                    )
                else:
                    graph = _download_bbox_graph_without_pyproj(bbox, endpoint)
                used_endpoint = endpoint
                break
            except Exception as exc:  # OSMnx wraps Overpass/network errors
                errors.append(exc)
                logger.warning(
                    "OSMnx endpoint %s failed (%s): %s",
                    endpoint,
                    type(exc).__name__,
                    exc,
                )

        if graph is None:
            last_error = errors[-1]
            logger.error(
                "All configured Overpass endpoints failed for bbox %s",
                bbox,
                exc_info=(type(last_error), last_error, last_error.__traceback__),
            )
            message = (
                "Could not download the walking network from either Overpass endpoint. "
                "Check the Flask terminal for details, then retry."
            )
            if config.DEBUG:
                frames = traceback.extract_tb(last_error.__traceback__)
                trace_summary = " -> ".join(
                    f"{Path(frame.filename).name}:{frame.lineno} ({frame.name})"
                    for frame in frames[-6:]
                )
                message += (
                    f" Diagnostic: {type(last_error).__name__}: {last_error}."
                    f" Trace: {trace_summary}."
                    f" OSMnx default CRS: {ox.settings.default_crs!r}; bbox: {bbox!r}."
                    f" PyProj available to GeoPandas: {geopandas_compat.HAS_PYPROJ};"
                    f" import error: {getattr(geopandas_compat, 'pyproj_import_error', None)!r}."
                )
            raise NetworkServiceError(
                message
            ) from last_error

        if graph.number_of_edges() == 0:
            raise NetworkServiceError("Walking network download returned no streets.")

        ox.save_graphml(graph, GRAPH_PATH)
        META_PATH.write_text(
            json.dumps(
                {
                    "lat": center_lat,
                    "lon": center_lon,
                    "half": config.GRID_HALF_SIZE_DEG,
                    "nodes": graph.number_of_nodes(),
                    "edges": graph.number_of_edges(),
                    "bbox": bbox,
                    "network_type": "walk",
                    "overpass_url": used_endpoint,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return graph


def _edge_coords(graph: nx.MultiDiGraph, u: int, v: int, data: dict[str, Any]) -> list[list[float]]:
    geom = data.get("geometry")
    if geom is not None:
        return [[float(x), float(y)] for x, y in geom.coords]

    ux = float(graph.nodes[u]["x"])
    uy = float(graph.nodes[u]["y"])
    vx = float(graph.nodes[v]["x"])
    vy = float(graph.nodes[v]["y"])
    return [[ux, uy], [vx, vy]]


def build_roads_geojson(center_lat: float, center_lon: float) -> dict[str, Any]:
    """Walking edges as GeoJSON LineStrings, with prototype heat on each segment."""
    graph = load_walk_graph(center_lat, center_lon)
    weather = get_current_weather(center_lat, center_lon)
    t_air = weather.get("temperature_c")
    if t_air is None:
        raise ValueError("Weather response had no temperature_c.")
    solar = _solar_bump(weather.get("shortwave_radiation_wm2"))

    features = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        coords = _edge_coords(graph, u, v, data)
        mid_lon = sum(pt[0] for pt in coords) / len(coords)
        mid_lat = sum(pt[1] for pt in coords) / len(coords)
        estimate = estimate_temperature_at(
            mid_lat, mid_lon, center_lat, center_lon, float(t_air), solar
        )
        name = data.get("name")
        if isinstance(name, list):
            name = ", ".join(str(part) for part in name)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "u": u,
                    "v": v,
                    "key": key,
                    "name": name or "unnamed path",
                    "highway": data.get("highway"),
                    "length_m": round(float(data.get("length", 0.0)), 1),
                    "estimated_temp_c": estimate["estimated_temp_c"],
                    "heat_risk": estimate["heat_risk"],
                    "color": estimate["color"],
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    return {
        "ok": True,
        "type": "FeatureCollection",
        "features": features,
        "edge_count": len(features),
        "node_count": graph.number_of_nodes(),
        "cached": _meta_matches(center_lat, center_lon),
        "disclaimer": (
            "Streets come from OpenStreetMap walking paths. "
            "Colours are the prototype heat estimate, not measured road temperature."
        ),
        "legend": [
            {"label": "Low", "color": RISK_COLORS["Low"], "rule": "< 28 °C"},
            {"label": "Moderate", "color": RISK_COLORS["Moderate"], "rule": "28–32 °C"},
            {"label": "High", "color": RISK_COLORS["High"], "rule": "32–36 °C"},
            {"label": "Very High", "color": RISK_COLORS["Very High"], "rule": "≥ 36 °C"},
        ],
    }
