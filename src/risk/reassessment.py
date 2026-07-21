from itertools import combinations

from src.detection.distance import calculate_distance_km
from src.risk.events import RiskOutcome


def records_for_horizon(trajectories, start_time, horizon_steps):
    records = []
    for time_step in range(start_time, start_time + horizon_steps + 1):
        for trajectory in trajectories.values():
            records.append(trajectory.position_record_at(time_step))
    return records


def minimum_pair_distance(trajectories, satellite_a, satellite_b, start_time, horizon_steps):
    minimum = None
    closest_time = None

    for time_step in range(start_time, start_time + horizon_steps + 1):
        distance = calculate_distance_km(
            trajectories[satellite_a].position_record_at(time_step),
            trajectories[satellite_b].position_record_at(time_step),
        )
        if minimum is None or distance < minimum:
            minimum = distance
            closest_time = time_step

    return {
        "closest_time": closest_time,
        "minimum_distance_km": float(minimum),
    }


def secondary_conjunctions_for_agent(
    trajectories,
    maneuvering_satellite,
    excluded_satellites,
    threshold_km,
    start_time,
    horizon_steps,
):
    findings = []

    for other_satellite in sorted(trajectories):
        if other_satellite == maneuvering_satellite or other_satellite in excluded_satellites:
            continue

        pair_result = minimum_pair_distance(
            trajectories,
            maneuvering_satellite,
            other_satellite,
            start_time,
            horizon_steps,
        )
        if pair_result["minimum_distance_km"] <= threshold_km:
            findings.append(
                {
                    "satellite_a": maneuvering_satellite,
                    "satellite_b": other_satellite,
                    "closest_time": pair_result["closest_time"],
                    "distance_km": pair_result["minimum_distance_km"],
                }
            )

    return findings


def evaluate_maneuver_outcome(pre_trajectories, post_trajectories, risk_event, maneuvering_satellite, start_time, horizon_steps):
    pre = minimum_pair_distance(
        pre_trajectories,
        risk_event.satellite_a,
        risk_event.satellite_b,
        start_time,
        horizon_steps,
    )
    post = minimum_pair_distance(
        post_trajectories,
        risk_event.satellite_a,
        risk_event.satellite_b,
        start_time,
        horizon_steps,
    )
    secondary = secondary_conjunctions_for_agent(
        post_trajectories,
        maneuvering_satellite,
        risk_event.participants(),
        risk_event.threshold_km,
        start_time,
        horizon_steps,
    )

    pre_distance = pre["minimum_distance_km"]
    post_distance = post["minimum_distance_km"]

    if secondary:
        outcome = RiskOutcome.SECONDARY_RISK_CREATED
    elif post_distance > risk_event.threshold_km:
        outcome = RiskOutcome.RESOLVED
    elif post_distance > pre_distance:
        outcome = RiskOutcome.PARTIALLY_MITIGATED
    elif post_distance < pre_distance:
        outcome = RiskOutcome.WORSENED
    else:
        outcome = RiskOutcome.UNCHANGED

    return {
        "risk_event_id": risk_event.risk_event_id,
        "outcome": outcome.value,
        "pre_minimum_distance_km": pre_distance,
        "post_minimum_distance_km": post_distance,
        "pre_closest_time": pre["closest_time"],
        "post_closest_time": post["closest_time"],
        "secondary_conjunctions": secondary,
    }
