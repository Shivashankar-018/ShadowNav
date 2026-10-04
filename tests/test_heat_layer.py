"""Unit checks for project-defined prototype heat-risk categories."""

import pytest

from gis.heat_layer import classify_heat_risk, estimate_temperature_at


@pytest.mark.parametrize(
    ("temperature_c", "expected_risk"),
    [
        (27.99, "Low"),
        (28.0, "Moderate"),
        (31.99, "Moderate"),
        (32.0, "High"),
        (35.99, "High"),
        (36.0, "Very High"),
    ],
)
def test_heat_risk_category_thresholds(temperature_c, expected_risk):
    assert classify_heat_risk(temperature_c) == expected_risk


def test_estimate_at_study_centre_includes_configured_centre_offset():
    import config

    estimate = estimate_temperature_at(
        config.MAP_LAT,
        config.MAP_LON,
        config.MAP_LAT,
        config.MAP_LON,
        t_air=30.0,
        solar=0.4,
    )

    assert estimate["estimated_temp_c"] == 32.4
    assert estimate["uhi_proxy_c"] == config.UHI_MAX_OFFSET_C
    assert estimate["heat_risk"] == "High"
