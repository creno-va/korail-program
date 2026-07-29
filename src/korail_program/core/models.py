"""Shared data models for the analysis pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """Business-facing risk labels."""

    HIGH = "상"
    MEDIUM = "중"
    LOW = "하"
    NONE = "없음"

    @classmethod
    def coerce(cls, value: str | "RiskLevel" | None) -> "RiskLevel":
        if isinstance(value, RiskLevel):
            return value
        if value is None:
            return cls.NONE

        normalized = str(value).strip().lower()
        aliases = {
            "상": cls.HIGH,
            "high": cls.HIGH,
            "높음": cls.HIGH,
            "위험": cls.HIGH,
            "중": cls.MEDIUM,
            "medium": cls.MEDIUM,
            "보통": cls.MEDIUM,
            "하": cls.LOW,
            "low": cls.LOW,
            "낮음": cls.LOW,
            "없음": cls.NONE,
            "none": cls.NONE,
            "no": cls.NONE,
            "없다": cls.NONE,
            "무": cls.NONE,
        }
        if normalized not in aliases:
            raise ValueError(f"Unsupported risk level: {value!r}")
        return aliases[normalized]

    @property
    def priority(self) -> int:
        return {
            RiskLevel.NONE: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
        }[self]


class ReviewStatus(str, Enum):
    """Manual review lifecycle for a detected event."""

    UNREVIEWED = "미확인"
    CONFIRMED = "확인"
    FALSE_POSITIVE = "오탐"
    HOLD = "보류"


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    video_id: int
    file_path: str
    duration_ms: int
    width: int
    height: int
    fps: float


@dataclass(frozen=True, slots=True)
class OcrObservation:
    video_id: int
    video_time_ms: int
    raw_text: str
    station_name: str | None
    confidence: float
    roi: tuple[int, int, int, int] | None = None
    method: str = "paddleocr"


@dataclass(frozen=True, slots=True)
class SectionMapping:
    video_id: int
    start_time_ms: int
    end_time_ms: int
    section_start: str
    section_end: str
    confidence: float


@dataclass(frozen=True, slots=True)
class JudgeObservation:
    video_id: int
    video_time_ms: int
    has_tree: bool
    bamboo_likely: float
    near_catenary: bool
    risk_level: RiskLevel
    bbox_hint: tuple[int, int, int, int] | None
    evidence: str
    needs_human_review: bool

    @property
    def is_risky(self) -> bool:
        return self.risk_level is not RiskLevel.NONE and (self.has_tree or self.near_catenary)


@dataclass(frozen=True, slots=True)
class AnalysisEvent:
    video_id: int
    start_time_ms: int
    end_time_ms: int
    section_start: str
    section_end: str
    risk_level: RiskLevel
    summary: str
    needs_human_review: bool
    source_observation_count: int
    capture_count: int = 0
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses and enums into JSON-serializable values."""

    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value

