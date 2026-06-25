def risk_state_for_distance(distance_km, threshold_km):
    if distance_km <= threshold_km:
        return "HIGH"
    return "LOW"
