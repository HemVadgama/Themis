import csv
from pathlib import Path


def save_records_to_csv(records, path):
    """
    Save a list of dictionaries to CSV, creating parent directories as needed.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if records:
        fieldnames = list(records[0].keys())
    else:
        fieldnames = []

    with output_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(records)
