from collections import defaultdict
from itertools import combinations

from src.detection.distance import calculate_distance_km


def _validate_positive_threshold(threshold_km):
    if threshold_km <= 0:
        raise ValueError("threshold_km must be positive")


def _ordered_pair_name(satellite_a, satellite_b):
    return tuple(sorted((satellite_a, satellite_b)))


def find_close_pairs_at_time(position_records, threshold_km):
    """
    Find all satellite pairs at one timestamp within the distance threshold.
    """
    _validate_positive_threshold(threshold_km)

    if not position_records:
        return []

    times = {record.get("time") for record in position_records}
    if len(times) != 1:
        raise ValueError("All position records must be from the same timestamp")

    events = []
    event_time = next(iter(times))
    seen_pairs = set()

    for position_a, position_b in combinations(position_records, 2):
        satellite_a = position_a.get("satellite")
        satellite_b = position_b.get("satellite")

        if satellite_a == satellite_b:
            continue

        pair_a, pair_b = _ordered_pair_name(satellite_a, satellite_b)
        pair = (pair_a, pair_b)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        distance_km = calculate_distance_km(position_a, position_b)
        if distance_km <= threshold_km:
            events.append(
                {
                    "time": event_time,
                    "satellite_a": pair_a,
                    "satellite_b": pair_b,
                    "distance_km": distance_km,
                }
            )

    return sorted(events, key=lambda event: event["distance_km"])


def detect_conjunctions(position_table, threshold_km):
    """
    Detect conjunction events across a position table containing many times.
    """
    _validate_positive_threshold(threshold_km)

    records_by_time = defaultdict(list)
    for record in position_table:
        records_by_time[record.get("time")].append(record)

    events = []
    for event_time in sorted(records_by_time):
        events.extend(find_close_pairs_at_time(records_by_time[event_time], threshold_km))

    return sorted(events, key=lambda event: (event["time"], event["distance_km"]))


def closest_approaches(position_table, max_pairs=None):
    """
    Find the minimum observed distance for each unique satellite pair.
    """
    records_by_time = defaultdict(list)
    for record in position_table:
        records_by_time[record.get("time")].append(record)

    closest_by_pair = {}

    for event_time in sorted(records_by_time):
        for position_a, position_b in combinations(records_by_time[event_time], 2):
            satellite_a = position_a.get("satellite")
            satellite_b = position_b.get("satellite")

            if satellite_a == satellite_b:
                continue

            pair = _ordered_pair_name(satellite_a, satellite_b)
            distance_km = calculate_distance_km(position_a, position_b)

            if pair not in closest_by_pair or distance_km < closest_by_pair[pair]["closest_distance_km"]:
                closest_by_pair[pair] = {
                    "satellite_a": pair[0],
                    "satellite_b": pair[1],
                    "closest_time": event_time,
                    "closest_distance_km": distance_km,
                }

    approaches = sorted(
        closest_by_pair.values(),
        key=lambda approach: approach["closest_distance_km"],
    )

    if max_pairs is not None:
        return approaches[:max_pairs]

    return approaches
