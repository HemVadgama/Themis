import pytest

from src.detection.conjunction import (
    closest_approaches,
    detect_conjunctions,
    find_close_pairs_at_time,
)
from src.utils.export import save_records_to_csv


def position(satellite, time, x, y, z=0):
    return {
        "satellite": satellite,
        "time": time,
        "x_km": x,
        "y_km": y,
        "z_km": z,
    }


def test_find_close_pairs_at_time_detects_close_pair():
    records = [
        position("SAT-A", "2026-01-01T00:00:00Z", 0, 0),
        position("SAT-B", "2026-01-01T00:00:00Z", 3, 4),
        position("SAT-C", "2026-01-01T00:00:00Z", 100, 100),
    ]

    events = find_close_pairs_at_time(records, threshold_km=10)

    assert events == [
        {
            "time": "2026-01-01T00:00:00Z",
            "satellite_a": "SAT-A",
            "satellite_b": "SAT-B",
            "distance_km": 5.0,
        }
    ]


def test_find_close_pairs_at_time_does_not_return_duplicate_pairs():
    records = [
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t1", 3, 4),
        position("SAT-B", "t1", 3, 4),
        position("SAT-C", "t1", 6, 8),
    ]

    events = find_close_pairs_at_time(records, threshold_km=10)
    pairs = {(event["satellite_a"], event["satellite_b"]) for event in events}

    assert len(events) == len(pairs)
    assert pairs == {("SAT-A", "SAT-B"), ("SAT-A", "SAT-C"), ("SAT-B", "SAT-C")}


def test_find_close_pairs_at_time_includes_threshold_distance():
    records = [
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t1", 3, 4),
    ]

    events = find_close_pairs_at_time(records, threshold_km=5)

    assert len(events) == 1
    assert events[0]["distance_km"] == 5.0


def test_find_close_pairs_at_time_rejects_mixed_timestamps():
    records = [
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t2", 3, 4),
    ]

    with pytest.raises(ValueError, match="same timestamp"):
        find_close_pairs_at_time(records, threshold_km=10)


def test_find_close_pairs_at_time_rejects_non_positive_threshold():
    with pytest.raises(ValueError, match="positive"):
        find_close_pairs_at_time([], threshold_km=0)


def test_detect_conjunctions_across_multiple_timestamps():
    table = [
        position("SAT-A", "t2", 0, 0),
        position("SAT-B", "t2", 0, 8),
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t1", 3, 4),
    ]

    events = detect_conjunctions(table, threshold_km=6)

    assert len(events) == 1
    assert events[0]["time"] == "t1"
    assert events[0]["distance_km"] == 5.0


def test_closest_approaches_finds_minimum_distance_for_each_pair():
    table = [
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t1", 10, 0),
        position("SAT-C", "t1", 100, 0),
        position("SAT-A", "t2", 0, 0),
        position("SAT-B", "t2", 3, 4),
        position("SAT-C", "t2", 0, 12),
    ]

    approaches = closest_approaches(table)

    assert approaches[0] == {
        "satellite_a": "SAT-A",
        "satellite_b": "SAT-B",
        "closest_time": "t2",
        "closest_distance_km": 5.0,
    }
    assert len(approaches) == 3


def test_closest_approaches_applies_max_pairs():
    table = [
        position("SAT-A", "t1", 0, 0),
        position("SAT-B", "t1", 3, 4),
        position("SAT-C", "t1", 0, 12),
    ]

    approaches = closest_approaches(table, max_pairs=1)

    assert len(approaches) == 1
    assert approaches[0]["closest_distance_km"] == 5.0


def test_save_records_to_csv_creates_file_with_headers(tmp_path):
    output_path = tmp_path / "nested" / "conjunctions.csv"
    records = [
        {
            "time": "t1",
            "satellite_a": "SAT-A",
            "satellite_b": "SAT-B",
            "distance_km": 5.0,
        }
    ]

    save_records_to_csv(records, output_path)

    assert output_path.exists()
    assert output_path.read_text().splitlines()[0] == "time,satellite_a,satellite_b,distance_km"


def test_save_records_to_csv_handles_empty_records(tmp_path):
    output_path = tmp_path / "empty.csv"

    save_records_to_csv([], output_path)

    assert output_path.exists()
    assert output_path.read_text() == ""
