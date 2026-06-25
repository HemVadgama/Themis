def count_unresolved_high_risk(conjunction_count, planned_maneuver_count):
    return max(0, conjunction_count - planned_maneuver_count)
