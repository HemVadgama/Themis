from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

from src.detection.conjunction import detect_conjunctions
from src.propagation.propagator import get_position_table
from src.propagation.tle_loader import load_satellites
from src.utils.export import save_records_to_csv


SATELLITE_COUNT = 25
HOURS = 24
STEP_MINUTES = 30
THRESHOLD_KM = 1000.0
OUTPUT_PATH = "results/conjunctions.csv"


def build_timestamps(start_time, hours=HOURS, step_minutes=STEP_MINUTES):
    timestamp_count = int((hours * 60) / step_minutes) + 1
    return [
        start_time + timedelta(minutes=step_minutes * index)
        for index in range(timestamp_count)
    ]


def main():
    satellites = load_satellites()[:SATELLITE_COUNT]
    start_time = datetime.now(timezone.utc)
    times = build_timestamps(start_time)

    position_table = get_position_table(satellites, times)
    events = detect_conjunctions(position_table, THRESHOLD_KM)
    save_records_to_csv(events, OUTPUT_PATH)

    print("Conjunction detection demo")
    print(f"Satellites: {len(satellites)}")
    print(f"Timestamps: {len(times)}")
    print(f"Threshold: {THRESHOLD_KM} km")
    print(f"Conjunction events: {len(events)}")
    print(f"Saved: {OUTPUT_PATH}")

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
