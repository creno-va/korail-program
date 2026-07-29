"""Station-name normalization and fuzzy matching."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

_TEXT_CLEAN_RE = re.compile(r"[^0-9A-Za-z가-힣]+")


@dataclass(frozen=True, slots=True)
class StationMatch:
    raw_text: str
    station_name: str | None
    confidence: float
    matched: bool


def normalize_station_text(value: str) -> str:
    return _TEXT_CLEAN_RE.sub("", value).strip().lower()


def station_aliases(station_name: str) -> set[str]:
    normalized = normalize_station_text(station_name)
    aliases = {normalized}
    if normalized.endswith("역"):
        aliases.add(normalized[:-1])
    else:
        aliases.add(f"{normalized}역")
    return {alias for alias in aliases if alias}


class StationMatcher:
    """Match noisy OCR text against a known station dictionary."""

    def __init__(self, station_names: list[str], *, cutoff: float = 0.65) -> None:
        if not station_names:
            raise ValueError("station_names must not be empty")
        self.cutoff = cutoff
        self._stations = list(dict.fromkeys(station_names))
        self._alias_to_station: dict[str, str] = {}
        for station in self._stations:
            for alias in station_aliases(station):
                self._alias_to_station[alias] = station

    def match(self, raw_text: str) -> StationMatch:
        normalized = normalize_station_text(raw_text)
        if not normalized:
            return StationMatch(raw_text=raw_text, station_name=None, confidence=0.0, matched=False)

        exact = self._alias_to_station.get(normalized)
        if exact is not None:
            return StationMatch(raw_text=raw_text, station_name=exact, confidence=1.0, matched=True)

        best_station: str | None = None
        best_score = 0.0
        for alias, station in self._alias_to_station.items():
            score = SequenceMatcher(None, normalized, alias).ratio()
            if score > best_score:
                best_score = score
                best_station = station

        if best_station is None or best_score < self.cutoff:
            return StationMatch(
                raw_text=raw_text,
                station_name=None,
                confidence=round(best_score, 4),
                matched=False,
            )

        return StationMatch(
            raw_text=raw_text,
            station_name=best_station,
            confidence=round(best_score, 4),
            matched=True,
        )
