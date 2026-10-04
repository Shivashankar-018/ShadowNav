"""ShadowNav web application — Step 31: synthetic prediction history."""

from datetime import datetime, timezone
from math import isfinite
import re

from flask import Flask, jsonify, render_template, request

import config
from database.db import (
    HistoryDatabaseError,
    delete_prediction_history,
    delete_route_search,
    get_recent_prediction_history,
    get_recent_route_history,
    initialize_database,
    save_prediction_history,
    save_route_options,
)
from gis.heat_layer import build_heatmap_geojson
from gis.network import NetworkServiceError, build_roads_geojson
from services.weather_service import WeatherServiceError, get_current_weather
from routing.route_service import (
    RouteServiceError,
    calculate_route,
    calculate_route_options,
)
from ml.predict import predict_heat
from ml.reporting import load_ml_metrics

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
initialize_database()

PUBLIC_HISTORY_MESSAGE = (
    "History is disabled on this public demo so visitors' route locations "
    "and demo inputs are not shared."
)


@app.after_request
def add_security_headers(response):
    """Add browser protections to HTML, JSON, and error responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.route("/")
def home():
    """Show the main webpage."""
    return render_template(
        "index.html",
        app_name=config.APP_NAME,
        tagline=config.APP_TAGLINE,
        map_lat=config.MAP_LAT,
        map_lon=config.MAP_LON,
        map_zoom=config.MAP_ZOOM,
        grid_half_size_deg=config.GRID_HALF_SIZE_DEG,
    )


def _status_payload():
    """Shared status data for the HTML page and the JSON API."""
    return {
        "ok": True,
        "app": config.APP_NAME,
        "message": "ShadowNav backend is running",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "step": 31,
    }


@app.route("/status")
def status_page():
    """Human-readable status page (same dark theme as Home)."""
    data = _status_payload()
    return render_template(
        "status.html",
        app_name=config.APP_NAME,
        status=data,
    )


@app.route("/api/status")
def api_status():
    """JSON health check used by JavaScript and later tests."""
    return jsonify(_status_payload())


def _parse_coordinate(name: str, raw_value: str | None, default: float) -> float:
    if raw_value is None or raw_value == "":
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    return value


def _parse_route_coordinates(payload):
    """Validate and return the four coordinates shared by route endpoints."""
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object in the request body.")

    names = ("source_lat", "source_lon", "destination_lat", "destination_lon")
    if any(payload.get(name) is None or payload.get(name) == "" for name in names):
        raise ValueError("All four source/destination coordinates are required.")
    if any(isinstance(payload[name], bool) for name in names):
        raise ValueError("All four source/destination coordinates must be numbers.")

    try:
        coordinates = tuple(float(payload[name]) for name in names)
    except (TypeError, ValueError) as exc:
        raise ValueError("All four source/destination coordinates must be numbers.") from exc

    if not all(isfinite(value) for value in coordinates):
        raise ValueError("All four source/destination coordinates must be finite numbers.")

    source_lat, source_lon, destination_lat, destination_lon = coordinates
    if not -90 <= source_lat <= 90 or not -90 <= destination_lat <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180 <= source_lon <= 180 or not -180 <= destination_lon <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    return coordinates


@app.route("/api/weather")
def api_weather():
    """Current weather for a point. Defaults to the map centre."""
    try:
        lat = _parse_coordinate("lat", request.args.get("lat"), config.MAP_LAT)
        lon = _parse_coordinate("lon", request.args.get("lon"), config.MAP_LON)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not -90.0 <= lat <= 90.0:
        return jsonify({"ok": False, "error": "lat must be between -90 and 90."}), 400
    if not -180.0 <= lon <= 180.0:
        return jsonify({"ok": False, "error": "lon must be between -180 and 180."}), 400

    try:
        data = get_current_weather(lat, lon)
    except WeatherServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(data)


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Run the local synthetic demo model with caller-supplied feature values."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), dict):
        return jsonify({"ok": False, "error": "Send a JSON object with a features object."}), 400

    try:
        result = predict_heat(payload["features"])
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception:
        app.logger.exception("Synthetic demo prediction failed")
        return jsonify({"ok": False, "error": "Could not run the local prediction model."}), 500

    if config.PUBLIC_DEMO:
        prediction_id = None
        history_saved = False
        history_message = PUBLIC_HISTORY_MESSAGE
    else:
        try:
            prediction_id = save_prediction_history(payload["features"], result)
            history_saved = True
            history_message = None
        except HistoryDatabaseError:
            app.logger.exception("Could not save synthetic prediction history")
            prediction_id = None
            history_saved = False
            history_message = "Could not save local demo history."

    return jsonify(
        {
            "ok": True,
            **result,
            "prediction_id": prediction_id,
            "history_saved": history_saved,
            "history_message": history_message,
        }
    )


@app.route("/api/predictions")
def api_predictions():
    """List recent local synthetic-model demonstration runs."""
    raw_limit = request.args.get("limit", "20")
    try:
        limit = int(raw_limit)
    except ValueError:
        return jsonify({"ok": False, "error": "limit must be an integer."}), 400
    if not 1 <= limit <= 100:
        return jsonify({"ok": False, "error": "limit must be between 1 and 100."}), 400

    if config.PUBLIC_DEMO:
        return jsonify(
            {
                "ok": True,
                "items": [],
                "history_enabled": False,
                "message": PUBLIC_HISTORY_MESSAGE,
            }
        )

    try:
        items = get_recent_prediction_history(limit)
    except HistoryDatabaseError:
        app.logger.exception("Could not read local prediction history")
        return jsonify({"ok": False, "error": "Could not read local prediction history."}), 500
    return jsonify({"ok": True, "items": items})


@app.route("/api/predictions/<prediction_id>", methods=["DELETE"])
def api_delete_prediction(prediction_id: str):
    """Delete one locally saved synthetic prediction by its generated ID."""
    if not re.fullmatch(r"[0-9a-f]{32}", prediction_id):
        return jsonify({"ok": False, "error": "Invalid prediction-history ID."}), 400
    if config.PUBLIC_DEMO:
        return jsonify({"ok": False, "error": PUBLIC_HISTORY_MESSAGE}), 403
    try:
        deleted_count = delete_prediction_history(prediction_id)
    except HistoryDatabaseError:
        app.logger.exception("Could not delete local prediction history")
        return jsonify({"ok": False, "error": "Could not delete local prediction history."}), 500
    if deleted_count == 0:
        return jsonify({"ok": False, "error": "Prediction-history item was not found."}), 404
    return jsonify({"ok": True, "deleted_count": deleted_count})


@app.route("/api/ml/metrics")
def api_ml_metrics():
    """Return saved synthetic validation and test results for the dashboard."""
    try:
        return jsonify(load_ml_metrics())
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except (OSError, ValueError):
        app.logger.exception("Could not read the local synthetic ML reports")
        return jsonify({"ok": False, "error": "Could not read the local ML reports."}), 500


@app.route("/api/heatmap")
def api_heatmap():
    """Prototype heat-risk grid as GeoJSON."""
    try:
        lat = _parse_coordinate("lat", request.args.get("lat"), config.MAP_LAT)
        lon = _parse_coordinate("lon", request.args.get("lon"), config.MAP_LON)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not -90.0 <= lat <= 90.0:
        return jsonify({"ok": False, "error": "lat must be between -90 and 90."}), 400
    if not -180.0 <= lon <= 180.0:
        return jsonify({"ok": False, "error": "lon must be between -180 and 180."}), 400

    try:
        data = build_heatmap_geojson(lat, lon)
    except WeatherServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(data)


@app.route("/api/route", methods=["POST"])
def api_route():
    """Calculate one walking route. JSON requires source and destination coordinates."""
    try:
        coordinates = _parse_route_coordinates(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    payload = request.get_json(silent=True)
    mode = payload.get("mode", "balanced")
    if not isinstance(mode, str):
        return jsonify({"ok": False, "error": "mode must be a string."}), 400

    try:
        result = calculate_route(*coordinates, mode=mode)
    except RouteServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    if config.PUBLIC_DEMO:
        result["history_id"] = None
        result["history_saved"] = False
        result["history_message"] = PUBLIC_HISTORY_MESSAGE
    else:
        try:
            result["history_id"] = save_route_options(
                *coordinates, {mode: result}
            )
            result["history_saved"] = True
        except HistoryDatabaseError:
            app.logger.exception("Could not save calculated route history")
            result["history_saved"] = False
            result["history_message"] = "Could not save local route history."
    return jsonify(result)


@app.route("/api/routes", methods=["POST"])
def api_routes():
    """Calculate shortest, balanced, and cooler candidates for one trip."""
    try:
        coordinates = _parse_route_coordinates(request.get_json(silent=True))
        routes = calculate_route_options(*coordinates)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except RouteServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    if config.PUBLIC_DEMO:
        history_id = None
        history_saved = False
        history_message = PUBLIC_HISTORY_MESSAGE
    else:
        try:
            history_id = save_route_options(*coordinates, routes)
            history_saved = True
            history_message = None
        except HistoryDatabaseError:
            app.logger.exception("Could not save route comparison history")
            history_id = None
            history_saved = False
            history_message = "Could not save local route history."

    return jsonify(
        {
            "ok": True,
            "routes": routes,
            "history_id": history_id,
            "history_saved": history_saved,
            "history_message": history_message,
        }
    )


@app.route("/api/history", methods=["GET"])
def api_history():
    """Return recent route results saved on this computer."""
    raw_limit = request.args.get("limit", "30")
    try:
        limit = int(raw_limit)
    except ValueError:
        return jsonify({"ok": False, "error": "limit must be an integer."}), 400
    if not 1 <= limit <= 100:
        return jsonify({"ok": False, "error": "limit must be between 1 and 100."}), 400

    if config.PUBLIC_DEMO:
        return jsonify(
            {
                "ok": True,
                "items": [],
                "history_enabled": False,
                "message": PUBLIC_HISTORY_MESSAGE,
            }
        )

    try:
        items = get_recent_route_history(limit)
    except HistoryDatabaseError:
        app.logger.exception("Could not read local route history")
        return jsonify({"ok": False, "error": "Could not read local route history."}), 500
    return jsonify({"ok": True, "items": items})


@app.route("/api/history/<search_id>", methods=["DELETE"])
def api_delete_history(search_id: str):
    """Delete every saved candidate belonging to a route comparison."""
    if not re.fullmatch(r"[0-9a-f]{32}", search_id):
        return jsonify({"ok": False, "error": "Invalid route-history ID."}), 400
    if config.PUBLIC_DEMO:
        return jsonify({"ok": False, "error": PUBLIC_HISTORY_MESSAGE}), 403
    try:
        deleted_count = delete_route_search(search_id)
    except HistoryDatabaseError:
        app.logger.exception("Could not delete local route history")
        return jsonify({"ok": False, "error": "Could not delete local route history."}), 500
    if deleted_count == 0:
        return jsonify({"ok": False, "error": "Route-history item was not found."}), 404
    return jsonify({"ok": True, "deleted_count": deleted_count})

@app.route("/api/roads")
def api_roads():
    """OSM walking streets as GeoJSON LineStrings."""
    try:
        lat = _parse_coordinate("lat", request.args.get("lat"), config.MAP_LAT)
        lon = _parse_coordinate("lon", request.args.get("lon"), config.MAP_LON)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not -90.0 <= lat <= 90.0:
        return jsonify({"ok": False, "error": "lat must be between -90 and 90."}), 400
    if not -180.0 <= lon <= 180.0:
        return jsonify({"ok": False, "error": "lon must be between -180 and 180."}), 400

    try:
        data = build_roads_geojson(lat, lon)
    except NetworkServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    except WeatherServiceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(data)


@app.errorhandler(404)
def not_found(_error):
    """User opened a URL that does not exist."""
    return (
        render_template(
            "error.html",
            app_name=config.APP_NAME,
            title="Page not found",
            message="This page does not exist yet.",
        ),
        404,
    )


@app.errorhandler(413)
def request_too_large(_error):
    """Return a concise error when a request exceeds the small API limit."""
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Request body is too large (16 KB maximum)."}), 413
    return (
        render_template(
            "error.html",
            app_name=config.APP_NAME,
            title="Request too large",
            message="This request is larger than the local application accepts.",
        ),
        413,
    )


@app.errorhandler(500)
def server_error(_error):
    """Unexpected crash. Do not leak internal details to the browser."""
    return (
        render_template(
            "error.html",
            app_name=config.APP_NAME,
            title="Server error",
            message="Something went wrong. Check the terminal for details.",
        ),
        500,
    )


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
