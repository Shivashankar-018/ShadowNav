"""Unit checks for the experimental route edge-cost function."""

from routing.route_service import _route_edge_cost


def test_shortest_route_cost_uses_distance_without_heat_penalty():
    assert _route_edge_cost(100.0, temp_c=38.0, mode="shortest") == 100.0


def test_cooler_route_cost_penalizes_a_hotter_edge_more_than_balanced():
    balanced = _route_edge_cost(100.0, temp_c=35.0, mode="balanced")
    cooler = _route_edge_cost(100.0, temp_c=35.0, mode="cooler")

    assert cooler > balanced > 100.0


def test_route_modes_have_equal_cost_at_or_below_heat_reference():
    costs = {
        mode: _route_edge_cost(100.0, temp_c=20.0, mode=mode)
        for mode in ("shortest", "balanced", "cooler")
    }

    assert costs == {"shortest": 100.0, "balanced": 100.0, "cooler": 100.0}
