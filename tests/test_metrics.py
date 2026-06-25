from src.metrics.summary import MetricsSummary


def test_metrics_summary_to_dict_contains_expected_values():
    metrics = MetricsSummary(
        conjunctions_detected=3,
        coordination_attempts=2,
        planned_maneuvers=2,
        messages_sent=18,
        messages_delivered=15,
        messages_dropped=3,
        estimated_fuel_used=2.0,
        unresolved_high_risk_conjunctions=1,
        runtime_seconds=0.25,
    )

    assert metrics.to_dict() == {
        "conjunctions_detected": 3,
        "coordination_attempts": 2,
        "planned_maneuvers": 2,
        "messages_sent": 18,
        "messages_delivered": 15,
        "messages_dropped": 3,
        "estimated_fuel_used": 2.0,
        "unresolved_high_risk_conjunctions": 1,
        "runtime_seconds": 0.25,
    }
