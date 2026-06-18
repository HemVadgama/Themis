from math import sqrt


REQUIRED_COORDINATES = ("x_km", "y_km", "z_km")


def calculate_distance_km(position_a, position_b):
    """
    Calculate Euclidean distance between two position records in kilometers.
    """
    for label, position in (("position_a", position_a), ("position_b", position_b)):
        for coordinate in REQUIRED_COORDINATES:
            if coordinate not in position:
                raise ValueError(f"{label} is missing required coordinate '{coordinate}'")

    dx = position_a["x_km"] - position_b["x_km"]
    dy = position_a["y_km"] - position_b["y_km"]
    dz = position_a["z_km"] - position_b["z_km"]

    return float(sqrt(dx * dx + dy * dy + dz * dz))
