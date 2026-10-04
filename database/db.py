"""Small SQLite helpers for local route and synthetic-prediction history."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import uuid4

import config

DATABASE_PATH = config.BASE_DIR / "data" / "shadownav.sqlite3"


class HistoryDatabaseError(Exception):
    """Raised when local route or prediction history cannot be accessed."""


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create local route-history and synthetic-prediction tables if needed."""
    try:
        with _connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS route_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source_lat REAL NOT NULL,
                    source_lon REAL NOT NULL,
                    destination_lat REAL NOT NULL,
                    destination_lon REAL NOT NULL,
                    mode TEXT NOT NULL CHECK (mode IN ('shortest', 'balanced', 'cooler')),
                    distance_km REAL NOT NULL,
                    estimated_time_min REAL NOT NULL,
                    average_estimated_temp_c REAL NOT NULL,
                    maximum_estimated_temp_c REAL NOT NULL,
                    heat_exposure_degree_km REAL NOT NULL,
                    high_risk_segment_percent REAL NOT NULL,
                    geometry_json TEXT NOT NULL,
                    UNIQUE (search_id, mode)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_route_history_created_at
                ON route_history (created_at DESC, id DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_history (
                    prediction_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    data_source TEXT NOT NULL CHECK (data_source = 'synthetic'),
                    model_name TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    estimated_heat_c REAL NOT NULL,
                    disclaimer TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_prediction_history_created_at
                ON prediction_history (created_at DESC, prediction_id DESC)
                """
            )
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not initialize local history tables.") from exc


def save_prediction_history(features: dict[str, Any], prediction: dict[str, Any]) -> str:
    """Save one synthetic demo prediction and return its local history ID."""
    if not isinstance(features, dict) or not isinstance(prediction, dict):
        raise HistoryDatabaseError("Prediction history needs feature and result objects.")
    if prediction.get("data_source") != "synthetic":
        raise HistoryDatabaseError("Only synthetic demo predictions can be saved here.")
    model_name = prediction.get("model_name")
    disclaimer = prediction.get("disclaimer")
    try:
        estimated_heat_c = float(prediction["estimated_heat_c"])
        features_json = json.dumps(features, separators=(",", ":"), allow_nan=False)
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoryDatabaseError("Prediction result or features are invalid.") from exc
    if not isfinite(estimated_heat_c) or not isinstance(model_name, str) or not model_name:
        raise HistoryDatabaseError("Prediction result is missing a valid value or model name.")
    if not isinstance(disclaimer, str) or not disclaimer:
        raise HistoryDatabaseError("Prediction result is missing its disclaimer.")

    prediction_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO prediction_history (
                    prediction_id, created_at, data_source, model_name,
                    features_json, estimated_heat_c, disclaimer
                ) VALUES (?, ?, 'synthetic', ?, ?, ?, ?)
                """,
                (prediction_id, created_at, model_name, features_json, estimated_heat_c, disclaimer),
            )
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not save this prediction to local history.") from exc
    return prediction_id


def get_recent_prediction_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent synthetic demo predictions without any location identity."""
    limit = max(1, min(int(limit), 100))
    try:
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT prediction_id, created_at, data_source, model_name,
                       features_json, estimated_heat_c, disclaimer
                FROM prediction_history
                ORDER BY created_at DESC, prediction_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not read local prediction history.") from exc

    try:
        history = []
        for row in rows:
            item = dict(row)
            item["features"] = json.loads(item.pop("features_json"))
            history.append(item)
        return history
    except (json.JSONDecodeError, TypeError) as exc:
        raise HistoryDatabaseError("Saved prediction features are not valid JSON.") from exc


def delete_prediction_history(prediction_id: str) -> int:
    """Delete one saved synthetic demo prediction."""
    try:
        with _connection() as connection:
            cursor = connection.execute(
                "DELETE FROM prediction_history WHERE prediction_id = ?", (prediction_id,)
            )
            return cursor.rowcount
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not delete this prediction history item.") from exc


def save_route_options(
    source_lat: float,
    source_lon: float,
    destination_lat: float,
    destination_lon: float,
    routes: dict[str, dict[str, Any]],
) -> str:
    """Store one or more route results as a grouped search and return its ID."""
    search_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []

    for mode, route in routes.items():
        properties = route["properties"]
        rows.append(
            (
                search_id,
                created_at,
                source_lat,
                source_lon,
                destination_lat,
                destination_lon,
                mode,
                properties["distance_km"],
                properties["estimated_time_min"],
                properties["average_estimated_temp_c"],
                properties["maximum_estimated_temp_c"],
                properties["heat_exposure_degree_km"],
                properties["high_risk_segment_percent"],
                json.dumps(route["geometry"], separators=(",", ":")),
            )
        )

    if not rows:
        raise HistoryDatabaseError("No route results were provided to save.")

    try:
        with _connection() as connection:
            connection.executemany(
                """
                INSERT INTO route_history (
                    search_id, created_at, source_lat, source_lon,
                    destination_lat, destination_lon, mode, distance_km,
                    estimated_time_min, average_estimated_temp_c,
                    maximum_estimated_temp_c, heat_exposure_degree_km,
                    high_risk_segment_percent, geometry_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        raise HistoryDatabaseError("Could not save this route to local history.") from exc

    return search_id


def get_recent_route_history(limit: int = 30) -> list[dict[str, Any]]:
    """Return recent saved candidates, including geometry for future replay."""
    limit = max(1, min(int(limit), 100))
    try:
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT id, search_id, created_at, source_lat, source_lon,
                       destination_lat, destination_lon, mode, distance_km,
                       estimated_time_min, average_estimated_temp_c,
                       maximum_estimated_temp_c, heat_exposure_degree_km,
                       high_risk_segment_percent, geometry_json
                FROM route_history
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not read local route history.") from exc

    history = []
    try:
        for row in rows:
            item = dict(row)
            item["geometry"] = json.loads(item.pop("geometry_json"))
            history.append(item)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HistoryDatabaseError("Saved route geometry is not valid JSON.") from exc
    return history


def delete_route_search(search_id: str) -> int:
    """Delete all saved candidate routes belonging to one search."""
    try:
        with _connection() as connection:
            cursor = connection.execute(
                "DELETE FROM route_history WHERE search_id = ?", (search_id,)
            )
            return cursor.rowcount
    except sqlite3.Error as exc:
        raise HistoryDatabaseError("Could not delete this route history item.") from exc
