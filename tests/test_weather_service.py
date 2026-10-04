"""Weather-field normalization tests that do not call the internet."""

from services.weather_service import _normalise


def test_normalise_maps_open_meteo_fields_to_application_names():
    payload = {
        "latitude": 12.97,
        "longitude": 77.59,
        "elevation": 915.0,
        "timezone": "Asia/Kolkata",
        "current_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
        },
        "current": {
            "time": "2026-10-03T12:00",
            "temperature_2m": 30.5,
            "relative_humidity_2m": 55,
            "apparent_temperature": 31.0,
            "wind_speed_10m": 8.0,
            "wind_direction_10m": 210,
            "cloud_cover": 20,
            "precipitation": 0.0,
            "shortwave_radiation": 450.0,
            "weather_code": 2,
        },
    }

    weather = _normalise(payload, 12.97, 77.59, cached=False)

    assert weather["temperature_c"] == 30.5
    assert weather["relative_humidity_percent"] == 55
    assert weather["wind_direction_deg"] == 210
    assert weather["weather_condition"] == "Partly cloudy"
    assert weather["cached"] is False
    assert "not a street thermometer" in weather["note"]
