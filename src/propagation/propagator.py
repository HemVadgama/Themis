from skyfield.api import load
from datetime import datetime, timezone, timedelta

ts = load.timescale()

def to_skyfield_time(time):
    """
    Converts supported time inputs into a Skyfield Time object.
    """

    if time == "now":
        return ts.now()

    if isinstance(time, datetime):
        if time.tzinfo is None:
            time = time.replace(tzinfo=timezone.utc)
        return ts.from_datetime(time)

    return time

def get_position(satellite, time='now'):
    """
    Returns the postion of a single satellite at given time
    """
    t = to_skyfield_time(time)
    
    geocentric = satellite.at(t)
    x, y, z = geocentric.position.km

    return {
        "satellite": satellite.name,
        "time": t.utc_iso(),
        "x_km": float(x),
        "y_km": float(y),
        "z_km": float(z)
    }

def get_positions(satellite, times):
    """
    Returns position of one satellite at many times
    """
    positions = []

    for time in times:
        pos = get_position(satellite, time)
        positions.append(pos)

    return positions

def get_position_table(satellites, times):
    """
    Returns postions of multiple satellites at many times
    """

    table = []

    for sat in satellites:
        positions = get_positions(sat, times)
        table.extend(positions)
    
    return table    