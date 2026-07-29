"""Load route station dictionaries."""

from __future__ import annotations

import csv
from pathlib import Path


def load_station_names(path: str | Path) -> list[str]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        return _load_station_names_csv(file_path)
    return [
        line.strip()
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _load_station_names_csv(path: Path) -> list[str]:
    stations: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames and "station_name" in reader.fieldnames:
            for row in reader:
                station = (row.get("station_name") or "").strip()
                if station:
                    stations.append(station)
            return stations

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        for row in reader:
            if row and row[0].strip() and not row[0].lstrip().startswith("#"):
                stations.append(row[0].strip())
    return stations

