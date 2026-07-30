"""Merge frame-level judge observations with OCR section mappings."""

from __future__ import annotations

from collections.abc import Iterable

from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel, SectionMapping

UNKNOWN_SECTION = "구간 미확인"


def merge_judge_observations(
    observations: Iterable[JudgeObservation],
    sections: Iterable[SectionMapping],
    *,
    sample_interval_ms: int = 1000,
    gap_tolerance_ms: int = 1500,
    min_event_duration_ms: int = 2000,
) -> list[AnalysisEvent]:
    risky_observations = sorted(
        (observation for observation in observations if observation.is_risky),
        key=lambda observation: observation.video_time_ms,
    )
    section_list = sorted(sections, key=lambda section: section.start_time_ms)
    if not risky_observations:
        return []

    groups: list[list[JudgeObservation]] = []
    current_group: list[JudgeObservation] = [risky_observations[0]]

    for observation in risky_observations[1:]:
        previous = current_group[-1]
        gap = observation.video_time_ms - previous.video_time_ms
        if gap <= sample_interval_ms + gap_tolerance_ms:
            current_group.append(observation)
        else:
            groups.append(current_group)
            current_group = [observation]
    groups.append(current_group)

    events: list[AnalysisEvent] = []
    for group in groups:
        start_time_ms = group[0].video_time_ms
        end_time_ms = group[-1].video_time_ms + sample_interval_ms
        if end_time_ms - start_time_ms < min_event_duration_ms:
            if any(not observation.needs_human_review for observation in group):
                end_time_ms = start_time_ms + min_event_duration_ms
            else:
                continue

        section_start, section_end = resolve_event_section(start_time_ms, end_time_ms, section_list)
        max_risk = max((observation.risk_level for observation in group), key=lambda item: item.priority)
        summary = select_event_summary(group, max_risk)

        events.append(
            AnalysisEvent(
                video_id=group[0].video_id,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                section_start=section_start,
                section_end=section_end,
                risk_level=max_risk,
                summary=summary,
                needs_human_review=any(observation.needs_human_review for observation in group),
                source_observation_count=len(group),
            )
        )

    return events


def resolve_event_section(
    start_time_ms: int,
    end_time_ms: int,
    sections: list[SectionMapping],
) -> tuple[str, str]:
    if not sections:
        return UNKNOWN_SECTION, UNKNOWN_SECTION

    start_section = _section_at(start_time_ms, sections)
    end_section = _section_at(max(start_time_ms, end_time_ms - 1), sections)
    if start_section and end_section:
        return start_section.section_start, end_section.section_end

    best = _best_overlap(start_time_ms, end_time_ms, sections)
    if best is None:
        return UNKNOWN_SECTION, UNKNOWN_SECTION
    return best.section_start, best.section_end


def select_event_summary(group: list[JudgeObservation], max_risk: RiskLevel) -> str:
    candidates = [
        observation
        for observation in group
        if observation.risk_level is max_risk and observation.evidence
    ]
    if not candidates:
        candidates = [observation for observation in group if observation.evidence]
    if not candidates:
        return "지장수목 의심 이벤트"
    selected = max(candidates, key=lambda observation: observation.bamboo_likely)
    return selected.evidence


def _section_at(video_time_ms: int, sections: list[SectionMapping]) -> SectionMapping | None:
    for section in sections:
        if section.start_time_ms <= video_time_ms < section.end_time_ms:
            return section
    return None


def _best_overlap(
    start_time_ms: int,
    end_time_ms: int,
    sections: list[SectionMapping],
) -> SectionMapping | None:
    best_section: SectionMapping | None = None
    best_overlap = 0
    for section in sections:
        overlap = max(0, min(end_time_ms, section.end_time_ms) - max(start_time_ms, section.start_time_ms))
        if overlap > best_overlap:
            best_overlap = overlap
            best_section = section
    return best_section
