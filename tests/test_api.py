"""API input, status, size-limit, and response-header checks."""

import json


def valid_route_coordinates():
    return {
        "source_lat": 12.9716,
        "source_lon": 77.5946,
        "destination_lat": 12.9706,
        "destination_lon": 77.5956,
    }


def fake_route_result(mode):
    """Small deterministic route response for API/database integration tests."""
    return {
        "ok": True,
        "type": "Feature",
        "mode": mode,
        "geometry": {
            "type": "LineString",
            "coordinates": [[77.5946, 12.9716], [77.5956, 12.9706]],
        },
        "properties": {
            "distance_km": 1.0,
            "estimated_time_min": 12.0,
            "average_estimated_temp_c": 30.0,
            "maximum_estimated_temp_c": 31.0,
            "heat_exposure_degree_km": 10.0,
            "high_risk_segment_percent": 0.0,
        },
    }


def test_status_endpoint_and_security_headers(client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["step"] == 31
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_weather_rejects_non_numeric_latitude(client):
    response = client.get("/api/weather?lat=abc&lon=77.59")

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert "lat must be a number" in response.get_json()["error"]


def test_predict_requires_features_object(client):
    response = client.post("/api/predict", json={})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    assert "features object" in response.get_json()["error"]


def test_predict_returns_synthetic_source_and_disclaimer(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(
        app_module,
        "predict_heat",
        lambda _features: {
            "estimated_heat_c": 31.25,
            "model_name": "linear_regression",
            "data_source": "synthetic",
            "disclaimer": "Synthetic demo only.",
        },
    )
    response = client.post("/api/predict", json={"features": {"example": 1}})
    result = response.get_json()

    assert response.status_code == 200
    assert result["data_source"] == "synthetic"
    assert result["disclaimer"] == "Synthetic demo only."
    assert result["history_saved"] is True
    prediction_history = client.get("/api/predictions?limit=1").get_json()["items"]
    assert prediction_history[0]["prediction_id"] == result["prediction_id"]
    assert prediction_history[0]["features"] == {"example": 1}
    deleted = client.delete(f"/api/predictions/{result['prediction_id']}")
    assert deleted.status_code == 200
    assert client.get("/api/predictions?limit=1").get_json()["items"] == []


def test_prediction_history_rejects_bad_limit_and_id(client):
    bad_limit = client.get("/api/predictions?limit=101")
    bad_id = client.delete("/api/predictions/not-an-id")

    assert bad_limit.status_code == 400
    assert "between 1 and 100" in bad_limit.get_json()["error"]
    assert bad_id.status_code == 400
    assert "Invalid prediction-history ID" in bad_id.get_json()["error"]


def test_ml_metrics_endpoint_returns_synthetic_reports(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(
        app_module,
        "load_ml_metrics",
        lambda: {
            "ok": True,
            "data_source": "synthetic",
            "selected_model": "linear_regression",
            "selection_metric": "validation_mae_c",
            "validation_results": {"linear_regression": {"validation_mae_c": 0.2}},
            "test_metrics": {
                "model_name": "linear_regression",
                "test_rows": 10,
                "mae_c": 0.2,
                "rmse_c": 0.3,
                "r2": 0.9,
            },
            "disclaimer": "Synthetic demonstration only.",
        },
    )
    response = client.get("/api/ml/metrics")
    result = response.get_json()

    assert response.status_code == 200
    assert result["data_source"] == "synthetic"
    assert result["selected_model"] == "linear_regression"
    assert result["test_metrics"]["test_rows"] == 10


def test_ml_metrics_endpoint_reports_missing_training_outputs(client, monkeypatch):
    import app as app_module

    def no_reports():
        raise FileNotFoundError("Run training and evaluation first.")

    monkeypatch.setattr(app_module, "load_ml_metrics", no_reports)
    response = client.get("/api/ml/metrics")

    assert response.status_code == 503
    assert "Run training and evaluation first" in response.get_json()["error"]


def test_route_requires_all_coordinates(client):
    response = client.post("/api/route", json={})

    assert response.status_code == 400
    assert "coordinates are required" in response.get_json()["error"]


def test_route_rejects_boolean_coordinate(client):
    payload = valid_route_coordinates()
    payload["source_lat"] = True

    response = client.post("/api/route", json=payload)

    assert response.status_code == 400
    assert "must be numbers" in response.get_json()["error"]


def test_route_rejects_unknown_mode_before_network_access(client):
    payload = valid_route_coordinates()
    payload["mode"] = "turbo"

    response = client.post("/api/route", json=payload)

    assert response.status_code == 422
    assert "mode must be" in response.get_json()["error"]


def test_route_api_saves_result_and_returns_it_from_history(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(
        app_module,
        "calculate_route",
        lambda *coordinates, mode: fake_route_result(mode),
    )
    payload = valid_route_coordinates()
    payload["mode"] = "balanced"

    response = client.post("/api/route", json=payload)
    saved_route = response.get_json()
    history_response = client.get("/api/history?limit=1")

    assert response.status_code == 200
    assert saved_route["history_saved"] is True
    assert history_response.status_code == 200
    assert history_response.get_json()["items"][0]["search_id"] == saved_route["history_id"]


def test_history_rejects_limit_outside_allowed_range(client):
    response = client.get("/api/history?limit=0")

    assert response.status_code == 400
    assert "between 1 and 100" in response.get_json()["error"]


def test_history_delete_rejects_malformed_id(client):
    response = client.delete("/api/history/not-an-id")

    assert response.status_code == 400
    assert "Invalid route-history ID" in response.get_json()["error"]


def test_api_rejects_oversized_request_body(client):
    large_body = json.dumps({"payload": "x" * 20_000})

    response = client.post(
        "/api/route",
        data=large_body,
        content_type="application/json",
    )

    assert response.status_code == 413
    assert "16 KB maximum" in response.get_json()["error"]
