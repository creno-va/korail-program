"""SQLite persistence helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from korail_program.core.models import (
    AnalysisEvent,
    JudgeObservation,
    OcrObservation,
    SectionMapping,
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    fps REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ocr_observations (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL,
    video_time_ms INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    station_name TEXT,
    confidence REAL NOT NULL,
    roi_x1 INTEGER,
    roi_y1 INTEGER,
    roi_x2 INTEGER,
    roi_y2 INTEGER,
    method TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS section_mappings (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL,
    start_time_ms INTEGER NOT NULL,
    end_time_ms INTEGER NOT NULL,
    section_start TEXT NOT NULL,
    section_end TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS judge_observations (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL,
    video_time_ms INTEGER NOT NULL,
    has_tree INTEGER NOT NULL,
    bamboo_likely REAL NOT NULL,
    near_catenary INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    bbox_x1 INTEGER,
    bbox_y1 INTEGER,
    bbox_x2 INTEGER,
    bbox_y2 INTEGER,
    evidence TEXT NOT NULL,
    needs_human_review INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS analysis_events (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL,
    start_time_ms INTEGER NOT NULL,
    end_time_ms INTEGER NOT NULL,
    section_start TEXT NOT NULL,
    section_end TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    summary TEXT NOT NULL,
    needs_human_review INTEGER NOT NULL,
    source_observation_count INTEGER NOT NULL,
    capture_count INTEGER NOT NULL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    video_time_ms INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES analysis_events(id)
);
"""


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    connection = connect(database_path)
    try:
        connection.executescript(SCHEMA_SQL)
    finally:
        connection.close()


class AnalysisRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_schema(self) -> None:
        self.connection.executescript(SCHEMA_SQL)

    def upsert_video(
        self,
        *,
        file_path: str,
        duration_ms: int = 0,
        width: int = 0,
        height: int = 0,
        fps: float = 0,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO videos (file_path, duration_ms, width, height, fps)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                duration_ms = excluded.duration_ms,
                width = excluded.width,
                height = excluded.height,
                fps = excluded.fps
            RETURNING id
            """,
            (file_path, duration_ms, width, height, fps),
        )
        return int(cursor.fetchone()["id"])

    def insert_ocr_observations(self, observations: Iterable[OcrObservation]) -> None:
        self.connection.executemany(
            """
            INSERT INTO ocr_observations (
                video_id, video_time_ms, raw_text, station_name, confidence,
                roi_x1, roi_y1, roi_x2, roi_y2, method
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.video_id,
                    item.video_time_ms,
                    item.raw_text,
                    item.station_name,
                    item.confidence,
                    *(item.roi or (None, None, None, None)),
                    item.method,
                )
                for item in observations
            ],
        )

    def insert_section_mappings(self, mappings: Iterable[SectionMapping]) -> None:
        self.connection.executemany(
            """
            INSERT INTO section_mappings (
                video_id, start_time_ms, end_time_ms, section_start, section_end, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.video_id,
                    item.start_time_ms,
                    item.end_time_ms,
                    item.section_start,
                    item.section_end,
                    item.confidence,
                )
                for item in mappings
            ],
        )

    def insert_judge_observations(self, observations: Iterable[JudgeObservation]) -> None:
        self.connection.executemany(
            """
            INSERT INTO judge_observations (
                video_id, video_time_ms, has_tree, bamboo_likely, near_catenary,
                risk_level, bbox_x1, bbox_y1, bbox_x2, bbox_y2, evidence, needs_human_review
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.video_id,
                    item.video_time_ms,
                    int(item.has_tree),
                    item.bamboo_likely,
                    int(item.near_catenary),
                    item.risk_level.value,
                    *(item.bbox_hint or (None, None, None, None)),
                    item.evidence,
                    int(item.needs_human_review),
                )
                for item in observations
            ],
        )

    def insert_events(self, events: Iterable[AnalysisEvent]) -> list[int]:
        ids: list[int] = []
        for item in events:
            cursor = self.connection.execute(
                """
                INSERT INTO analysis_events (
                    video_id, start_time_ms, end_time_ms, section_start, section_end,
                    risk_level, summary, needs_human_review, source_observation_count,
                    capture_count, review_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.video_id,
                    item.start_time_ms,
                    item.end_time_ms,
                    item.section_start,
                    item.section_end,
                    item.risk_level.value,
                    item.summary,
                    int(item.needs_human_review),
                    item.source_observation_count,
                    item.capture_count,
                    item.review_status.value,
                ),
            )
            ids.append(int(cursor.lastrowid))
        return ids
