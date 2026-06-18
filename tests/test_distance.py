import pytest

from src.detection.distance import calculate_distance_km


def test_calculate_distance_km_returns_euclidean_distance():
    position_a = {"x_km": 0, "y_km": 0, "z_km": 0}
    position_b = {"x_km": 3, "y_km": 4, "z_km": 0}

    assert calculate_distance_km(position_a, position_b) == 5.0


def test_calculate_distance_km_raises_for_missing_coordinate():
    position_a = {"x_km": 0, "y_km": 0}
    position_b = {"x_km": 3, "y_km": 4, "z_km": 0}

    with pytest.raises(ValueError, match="missing required coordinate 'z_km'"):
        calculate_distance_km(position_a, position_b)
