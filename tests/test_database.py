"""SQLite history tests using a temporary database file."""


def sample_route():
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[77.59, 12.97], [77.60, 12.98]],
        },
        "properties": {
            "distance_km": 1.25,
            "estimated_time_min": 15.0,
            "average_estimated_temp_c": 31.2,
            "maximum_estimated_temp_c": 32.1,
            "heat_exposure_degree_km": 14.0,
            "high_risk_segment_percent": 10.0,
        },
    }


def test_history_saves_reads_and_deletes_one_route(temporary_history_database):
    database = temporary_history_database
    route = sample_route()

    search_id = database.save_route_options(
        12.97, 77.59, 12.98, 77.60, {"balanced": route}
    )
    items = database.get_recent_route_history()

    assert len(items) == 1
    assert items[0]["search_id"] == search_id
    assert items[0]["mode"] == "balanced"
    assert items[0]["geometry"] == route["geometry"]
    assert database.delete_route_search(search_id) == 1
    assert database.get_recent_route_history() == []


def test_delete_removes_all_candidates_from_a_comparison(temporary_history_database):
    database = temporary_history_database
    routes = {
        mode: sample_route()
        for mode in ("shortest", "balanced", "cooler")
    }

    search_id = database.save_route_options(
        12.97, 77.59, 12.98, 77.60, routes
    )

    assert {item["mode"] for item in database.get_recent_route_history()} == {
        "shortest",
        "balanced",
        "cooler",
    }
    assert database.delete_route_search(search_id) == 3


def test_synthetic_prediction_history_saves_reads_and_deletes(temporary_history_database):
    database = temporary_history_database
    features = {
        "air_temperature_c": 30.0,
        "vegetation_proxy": 0.4,
    }
    prediction = {
        "estimated_heat_c": 31.2,
        "model_name": "linear_regression",
        "data_source": "synthetic",
        "disclaimer": "Synthetic demo only.",
    }

    prediction_id = database.save_prediction_history(features, prediction)
    items = database.get_recent_prediction_history()

    assert len(items) == 1
    assert items[0]["prediction_id"] == prediction_id
    assert items[0]["data_source"] == "synthetic"
    assert items[0]["features"] == features
    assert items[0]["estimated_heat_c"] == 31.2
    assert database.delete_prediction_history(prediction_id) == 1
    assert database.get_recent_prediction_history() == []
