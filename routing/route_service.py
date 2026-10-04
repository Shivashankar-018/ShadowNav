"""Heat-aware walking route calculation on the cached OSM graph."""

from __future__ import annotations

from math import cos, radians
from typing import Any

import networkx as nx

import config
from gis.heat_layer import _solar_bump, estimate_temperature_at
from gis.network import NetworkServiceError, load_walk_graph, study_bbox
from services.weather_service import WeatherServiceError, get_current_weather

WALKING_SPEED_KMH = 5.0
HEAT_REFERENCE_C = 20.0
HIGH_RISK_C = 32.0
ROUTE_MODES = ("shortest", "balanced", "cooler")


class RouteServiceError(Exception):
    """Raised when a walking route cannot be calculated."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _edge_length(data: dict[str, Any]) -> float:
    try:
        return max(0.0, float(data.get("length", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _route_edge_cost(length_m: float, temp_c: float, mode: str) -> float:
    """Return one walking-edge cost using the selected experimental mode."""
    heat_multipliers = {"shortest": 0.0, "balanced": 0.7, "cooler": 1.8}
    if mode not in heat_multipliers:
        raise RouteServiceError("mode must be shortest, cooler, or balanced.")

    heat_factor = max(0.0, min(1.0, (temp_c - HEAT_REFERENCE_C) / 20.0))
    return max(0.01, length_m * (1.0 + heat_multipliers[mode] * heat_factor))


def _nearest_node(graph: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """Find the closest local graph node using a small-area distance proxy.

    This avoids OSMnx's projected-coordinate index, which needs PyProj. The
    study area is only a few kilometres wide, so an equirectangular distance
    is accurate enough for snapping a click to its nearest road node.
    """
    longitude_scale = cos(radians(lat))
    return min(
        graph.nodes,
        key=lambda node: (
            (float(graph.nodes[node]["x"]) - lon) * longitude_scale
        ) ** 2
        + (float(graph.nodes[node]["y"]) - lat) ** 2,
    )


def _edge_coordinates(graph: nx.MultiDiGraph, u: int, v: int, data: dict[str, Any]) -> list[list[float]]:
    geometry = data.get("geometry")
    if geometry is not None:
        return [[float(x), float(y)] for x, y in geometry.coords]
    return [
        [float(graph.nodes[u]["x"]), float(graph.nodes[u]["y"])],
        [float(graph.nodes[v]["x"]), float(graph.nodes[v]["y"])],
    ]


def _within_study_area(lat: float, lon: float, center_lat: float, center_lon: float) -> bool:
    west, south, east, north = study_bbox(center_lat, center_lon)
    return south <= lat <= north and west <= lon <= east


def calculate_route(
    source_lat: float,
    source_lon: float,
    destination_lat: float,
    destination_lon: float,
    mode: str = "balanced",
) -> dict[str, Any]:
    """Return one route and its distance/time/prototype heat metrics.

    Route weights are experimental. `shortest` uses distance only; `cooler`
    and `balanced` add a heat-related penalty to edge length.
    """
    if mode not in {"shortest", "cooler", "balanced"}:
        raise RouteServiceError("mode must be shortest, cooler, or balanced.")

    center_lat, center_lon = config.MAP_LAT, config.MAP_LON
    if not _within_study_area(source_lat, source_lon, center_lat, center_lon):
        raise RouteServiceError("Source is outside the current study-area map bounds.")
    if not _within_study_area(destination_lat, destination_lon, center_lat, center_lon):
        raise RouteServiceError("Destination is outside the current study-area map bounds.")

    try:
        graph = load_walk_graph(center_lat, center_lon)
        weather = get_current_weather(center_lat, center_lon)
    except (NetworkServiceError, WeatherServiceError) as exc:
        raise RouteServiceError(str(exc), status_code=502) from exc

    base_temp = weather.get("temperature_c")
    if base_temp is None:
        raise RouteServiceError("Weather response had no temperature value.")
    solar = _solar_bump(weather.get("shortwave_radiation_wm2"))

    try:
        origin = _nearest_node(graph, source_lat, source_lon)
        target = _nearest_node(graph, destination_lat, destination_lon)
        if origin == target:
            raise RouteServiceError("Source and destination snap to the same road junction. Choose points farther apart.")

        # Give every directed edge a generalized cost. In a MultiDiGraph,
        # NetworkX's string weight uses the minimum parallel edge cost.
        for u, v, key, data in graph.edges(keys=True, data=True):
            coords = _edge_coordinates(graph, u, v, data)
            mid_lon = sum(point[0] for point in coords) / len(coords)
            mid_lat = sum(point[1] for point in coords) / len(coords)
            estimate = estimate_temperature_at(
                mid_lat, mid_lon, center_lat, center_lon, float(base_temp), solar
            )
            temp_c = estimate["estimated_temp_c"]
            length_m = _edge_length(data)
            # Dimensionless heat proxy; not a health or safety score.
            data["_sn_route_weight"] = _route_edge_cost(length_m, temp_c, mode)
            data["_sn_temp_c"] = temp_c

        nodes = nx.shortest_path(graph, origin, target, weight="_sn_route_weight", method="dijkstra")
    except RouteServiceError:
        raise
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RouteServiceError("No connected walking path was found between those points.") from exc
    except Exception as exc:
        raise RouteServiceError("Could not snap points to the walking network.") from exc

    coordinates: list[list[float]] = []
    length_m_total = 0.0
    heat_degree_km = 0.0
    max_temp = float("-inf")
    high_length_m = 0.0
    segment_count = 0
    weighted_temperature_sum = 0.0

    for u, v in zip(nodes, nodes[1:]):
        candidates = graph.get_edge_data(u, v) or {}
        if not candidates:
            continue
        key, data = min(candidates.items(), key=lambda item: float(item[1].get("_sn_route_weight", float("inf"))))
        coords = _edge_coordinates(graph, u, v, data)
        if coordinates and coords and coordinates[0] == coordinates[-1]:
            coordinates.extend(coords[1:])
        else:
            coordinates.extend(coords)

        length_m = _edge_length(data)
        temp_c = float(data["_sn_temp_c"])
        length_m_total += length_m
        weighted_temperature_sum += temp_c * length_m
        heat_degree_km += max(0.0, temp_c - HEAT_REFERENCE_C) * (length_m / 1000.0)
        max_temp = max(max_temp, temp_c)
        if temp_c >= HIGH_RISK_C:
            high_length_m += length_m
        segment_count += 1

    if not segment_count or length_m_total <= 0:
        raise RouteServiceError("The walking route had no usable road segments.")

    distance_km = length_m_total / 1000.0
    return {
        "ok": True,
        "mode": mode,
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {
            "distance_m": round(length_m_total, 1),
            "distance_km": round(distance_km, 3),
            "estimated_time_min": round(distance_km / WALKING_SPEED_KMH * 60, 1),
            "average_estimated_temp_c": round(weighted_temperature_sum / length_m_total, 2),
            "maximum_estimated_temp_c": round(max_temp, 2),
            "heat_exposure_degree_km": round(heat_degree_km, 3),
            "high_risk_segment_percent": round(high_length_m / length_m_total * 100, 1),
            "segment_count": segment_count,
            "walking_speed_kmh_assumption": WALKING_SPEED_KMH,
            "heat_reference_c": HEAT_REFERENCE_C,
            "timestamp": weather.get("timestamp"),
            "disclaimer": "Route heat metrics use a prototype spatial estimate from model-grid weather; they are not measured road temperatures or medical guidance.",
        },
    }


def calculate_route_options(
    source_lat: float,
    source_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> dict[str, dict[str, Any]]:
    """Calculate one candidate for each documented route preference."""
    return {
        mode: calculate_route(
            source_lat,
            source_lon,
            destination_lat,
            destination_lon,
            mode=mode,
        )
        for mode in ROUTE_MODES
    }
