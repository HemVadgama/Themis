def estimate_fuel_used(planned_maneuver_count, fuel_per_maneuver=1.0):
    return float(planned_maneuver_count * fuel_per_maneuver)
