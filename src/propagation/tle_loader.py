"""Explicit local loading and optional refresh of TLE input data."""

from pathlib import Path

from skyfield.api import Loader
from skyfield.iokit import parse_tle_file


DEFAULT_DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"


def load_satellites(group="active", *, data_directory=None, refresh=False, max_age_days=7.0):
    """Load one named TLE group, refreshing from CelesTrak only when requested.

    The default is intentionally offline and repeatable. Callers that opt into a
    refresh should archive and hash the resulting input alongside their analysis.
    """
    if not isinstance(group, str) or not group or any(character in group for character in "/\\"):
        raise ValueError("group must be a non-empty filename stem without path separators")
    directory = Path(data_directory or DEFAULT_DATA_DIRECTORY).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    load = Loader(str(directory))
    name = f"{group}.tle"
    if refresh and (not load.exists(name) or load.days_old(name) >= max_age_days):
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
        load.download(url, filename=name)
    if not load.exists(name):
        raise FileNotFoundError(
            f"TLE input not found: {directory / name}. Supply a local file or explicitly request refresh=True."
        )

    ts = load.timescale()
    with load.open(name) as handle:
        return list(parse_tle_file(handle, ts))


def find_satellite_by_name(satellites, name):
    """Return the exact-name match or raise an actionable lookup error."""
    for satellite in satellites:
        if satellite.name == name:
            return satellite
    raise ValueError(f"Satellite {name!r} was not found in the loaded TLE group.")
