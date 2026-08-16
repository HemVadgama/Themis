"""Legacy TLE propagation demo, separate from the validated benchmark runner.

This script is useful for exploring the optional orbit input stack. It does not
produce the versioned Themis run-artifact contract and must not be used to make
operational conjunction or flight-safety decisions.
"""

import argparse
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import sys


if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

from src.detection.conjunction import detect_conjunctions
from src.propagation.propagator import get_position_table
from src.propagation.tle_loader import DEFAULT_DATA_DIRECTORY, load_satellites
from src.utils.export import save_records_to_csv


SATELLITE_COUNT = 25
HOURS = 24
STEP_MINUTES = 30
THRESHOLD_KM = 1000.0
DEFAULT_START = "2025-01-01T00:00:00+00:00"
OUTPUT_PATH = "results/conjunctions.csv"


def build_timestamps(start_time, hours=HOURS, step_minutes=STEP_MINUTES):
    timestamp_count = int((hours * 60) / step_minutes) + 1
    return [
        start_time + timedelta(minutes=step_minutes * index)
        for index in range(timestamp_count)
    ]


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START, help="ISO-8601 UTC start time; fixed by default for repeatability.")
    parser.add_argument("--output", default=OUTPUT_PATH, help="CSV output path.")
    parser.add_argument("--tle-group", default="active", help="Local TLE filename stem (default: active).")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIRECTORY), help="Directory containing <group>.tle.")
    parser.add_argument("--refresh-tle", action="store_true", help="Explicitly refresh stale/missing TLE data from CelesTrak.")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    start_time = datetime.fromisoformat(args.start)
    if start_time.tzinfo is None:
        raise SystemExit("--start must include a timezone offset, such as +00:00")
    satellites = load_satellites(
        args.tle_group,
        data_directory=args.data_dir,
        refresh=args.refresh_tle,
    )[:SATELLITE_COUNT]
    tle_path = Path(args.data_dir).expanduser().resolve() / f"{args.tle_group}.tle"
    tle_sha256 = hashlib.sha256(tle_path.read_bytes()).hexdigest()
    times = build_timestamps(start_time)

    position_table = get_position_table(satellites, times)
    events = detect_conjunctions(position_table, THRESHOLD_KM)
    save_records_to_csv(events, args.output)

    print("Conjunction detection demo")
    print(f"Satellites: {len(satellites)}")
    print(f"Timestamps: {len(times)}")
    print(f"Threshold: {THRESHOLD_KM} km")
    print(f"Conjunction events: {len(events)}")
    print(f"Start: {start_time.isoformat()}")
    print(f"TLE input: {tle_path}")
    print(f"TLE SHA-256: {tle_sha256}")
    print(f"Saved: {args.output}")

    if events:
        print("First 10 events:")
        for event in events[:10]:
            print(
                f"{event['time']} | {event['satellite_a']} / {event['satellite_b']} | "
                f"{event['distance_km']:.3f} km"
            )
    else:
        print("No conjunction events found. Try increasing THRESHOLD_KM.")


if __name__ == "__main__":
    main()
