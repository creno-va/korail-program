"""A4 field report grouped by section with one evaluation per unique frame."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html import escape
from importlib import resources
from pathlib import Path
from unicodedata import normalize

from korail_program.core.event_merger import format_section_label
from korail_program.core.models import (
    AnalysisEvent,
    JudgeObservation,
    RiskLevel,
    SectionMapping,
)
from korail_program.core.timecode import format_timecode

_FONT_REGULAR = "PretendardGOV-PDF-Regular"
_FONT_SEMIBOLD = "PretendardGOV-PDF-SemiBold"
_UNKNOWN_SECTION_LABELS = {"구간 미확인", "미확인", "-", ""}
_RISK_LABELS = {
    RiskLevel.HIGH: ("경고", "#f04452"),
    RiskLevel.MEDIUM: ("주의", "#ff8a3d"),
    RiskLevel.LOW: ("관찰", "#00a878"),
    RiskLevel.NONE: ("이상 없음", "#6b7684"),
}


@dataclass(slots=True)
class _SectionGroup:
    video_id: int
    video_name: str
    section_label: str
    records: list[dict[str, object]]


@dataclass(slots=True)
class _ReportPage:
    video_name: str
    section_label: str
    records: list[dict[str, object]]
    continued: bool = False


def write_pdf_report(
    *,
    output_dir: Path,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
    sections: list[SectionMapping] | None = None,
    video_titles: list[str] | None = None,
) -> Path:
    """Write unique suspicious frames as a section-grouped vertical list."""

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - dependency is part of packaged app
        raise RuntimeError(
            "PDF 리포트 생성에 reportlab이 필요합니다. 앱을 다시 설치해 주세요."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "report.pdf"
    _register_fonts()

    document = canvas.Canvas(str(pdf_path), pagesize=A4, pageCompression=1)
    document.setTitle("전차선로 지장수목 분석 REPORT")
    document.setAuthor("전차선로 지장수목 분석")
    document.setCreator("Korail Analyzer")
    document.setSubject("영상 기반 전차선로 지장수목 분석 결과")

    unique_records = _unique_frame_records(suspicious_records)
    normalized_titles = _video_titles(video_titles, unique_records)
    section_groups = _group_records_by_section(
        unique_records,
        events=events,
        sections=sections or [],
    )
    report_pages = _build_report_pages(section_groups)
    section_labels = list(
        dict.fromkeys(
            group.section_label
            for group in section_groups
            if group.section_label not in _UNKNOWN_SECTION_LABELS
        )
    )
    analysis_time = datetime.now().astimezone().strftime("%Y.%m.%d %H:%M")

    for page_number, report_page in enumerate(report_pages, start=1):
        _draw_report_page(
            document,
            records=report_page.records,
            all_records=unique_records,
            section_label=report_page.section_label,
            section_video_name=report_page.video_name,
            section_continued=report_page.continued,
            video_titles=normalized_titles,
            video_count=video_count,
            sampled_frame_count=sampled_frame_count,
            failure_count=len(failures),
            section_labels=section_labels,
            analysis_time=analysis_time,
            page_number=page_number,
            total_pages=len(report_pages),
        )
        document.showPage()

    document.save()
    return pdf_path


def _register_fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_root = resources.files("korail_program.assets.fonts")
    font_files = {
        _FONT_REGULAR: "PretendardGOV-Regular.ttf",
        _FONT_SEMIBOLD: "PretendardGOV-SemiBold.ttf",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, file_name in font_files.items():
        if font_name in registered:
            continue
        with resources.as_file(font_root.joinpath(file_name)) as font_path:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def _draw_report_page(
    document,
    *,
    records: list[dict[str, object]],
    all_records: list[dict[str, object]],
    section_label: str,
    section_video_name: str,
    section_continued: bool,
    video_titles: list[str],
    video_count: int,
    sampled_frame_count: int,
    failure_count: int,
    section_labels: list[str],
    analysis_time: str,
    page_number: int,
    total_pages: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 18 * mm
    content_width = page_width - (margin * 2)

    title_y = page_height - (33 * mm)
    title_height = 14 * mm
    document.setFillColor(HexColor("#ecffff"))
    document.rect(margin, title_y, content_width, title_height, fill=1, stroke=0)
    document.setStrokeColor(HexColor("#4e7cff"))
    document.setLineWidth(1.4)
    document.line(margin, title_y, page_width - margin, title_y)
    document.line(
        margin,
        title_y + title_height,
        page_width - margin,
        title_y + title_height,
    )
    document.setFillColor(HexColor("#111111"))
    document.setFont(_FONT_SEMIBOLD, 22)
    document.drawCentredString(
        page_width / 2,
        title_y + (4.1 * mm),
        "전차선로 지장수목 분석 REPORT",
    )

    document.setFont(_FONT_REGULAR, 8)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawRightString(
        page_width - margin,
        title_y - (7 * mm),
        f"{page_number} / {total_pages}",
    )

    _draw_section_heading(document, x=margin, y=page_height - (66 * mm), text="분석현황")
    summary_rows = _summary_rows(
        analysis_time=analysis_time,
        video_titles=video_titles,
        video_count=video_count,
        section_labels=section_labels,
        records=all_records,
    )
    summary_y = page_height - (78 * mm)
    for index, (label, value) in enumerate(summary_rows):
        _draw_summary_row(
            document,
            x=margin + (4 * mm),
            y=summary_y - (index * 10 * mm),
            label=label,
            value=value,
            max_width=content_width - (8 * mm),
        )

    _draw_section_heading(document, x=margin, y=page_height - (119 * mm), text="분석사진")
    _draw_frame_list(
        document,
        x=margin,
        top_y=page_height - (128 * mm),
        width=content_width,
        height=132 * mm,
        records=records,
        section_label=section_label,
        video_name=section_video_name,
        continued=section_continued,
    )

    _draw_korail_logo(document, x=margin, y=17 * mm, max_width=42 * mm, max_height=8 * mm)
    footer_parts = [f"샘플 프레임 {sampled_frame_count}개"]
    if failure_count:
        footer_parts.append(f"처리 실패 {failure_count}건")
    document.setFillColor(HexColor("#8b95a1"))
    document.setFont(_FONT_REGULAR, 7.5)
    document.drawRightString(
        page_width - margin,
        18 * mm,
        " · ".join(footer_parts),
    )


def _draw_section_heading(document, *, x: float, y: float, text: str) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    document.setStrokeColor(HexColor("#333333"))
    document.setLineWidth(0.8)
    document.rect(x, y - (3.8 * mm), 4.8 * mm, 4.8 * mm, fill=0, stroke=1)
    document.setFillColor(HexColor("#111111"))
    document.setFont(_FONT_SEMIBOLD, 16)
    document.drawString(x + (8 * mm), y - (3.1 * mm), text)


def _summary_rows(
    *,
    analysis_time: str,
    video_titles: list[str],
    video_count: int,
    section_labels: list[str],
    records: list[dict[str, object]],
) -> list[tuple[str, str]]:
    video_summary = _summarize_values(video_titles, fallback=f"분석 영상 {video_count}개")
    rows = [
        ("분석일시", analysis_time),
        ("분석영상", video_summary),
    ]
    if section_labels:
        rows.append(("OCR 추정 구간", _summarize_values(section_labels)))
    rows.append(("탐지결과", _risk_count_text(records)))
    return rows


def _draw_summary_row(
    document,
    *,
    x: float,
    y: float,
    label: str,
    value: str,
    max_width: float,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    document.setFillColor(HexColor("#333333"))
    document.setFont(_FONT_REGULAR, 11)
    document.drawString(x, y, "○")
    document.setFont(_FONT_SEMIBOLD, 10.5)
    document.drawString(x + (8 * mm), y, f"{label} :")
    value_x = x + (39 * mm)
    document.setFont(_FONT_REGULAR, 10.5)
    document.drawString(
        value_x,
        y,
        _fit_text(
            value,
            font_name=_FONT_REGULAR,
            font_size=10.5,
            max_width=max_width - (39 * mm),
        ),
    )


def _draw_frame_list(
    document,
    *,
    x: float,
    top_y: float,
    width: float,
    height: float,
    records: list[dict[str, object]],
    section_label: str,
    video_name: str,
    continued: bool,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    banner_height = 10 * mm
    document.setFillColor(HexColor("#edf6ff"))
    document.roundRect(
        x,
        top_y - banner_height,
        width,
        banner_height,
        2.5 * mm,
        fill=1,
        stroke=0,
    )
    document.setFillColor(HexColor("#3182f6"))
    document.roundRect(
        x,
        top_y - banner_height,
        3 * mm,
        banner_height,
        1.5 * mm,
        fill=1,
        stroke=0,
    )

    display_section = section_label or "구간 미확인"
    if continued:
        display_section = f"{display_section} (계속)"
    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 10.5)
    document.drawString(x + (7 * mm), top_y - (6.7 * mm), f"분석 구간  {display_section}")
    if video_name:
        document.setFillColor(HexColor("#6b7684"))
        document.setFont(_FONT_REGULAR, 8)
        document.drawRightString(
            x + width - (4 * mm),
            top_y - (6.4 * mm),
            _fit_text(
                video_name,
                font_name=_FONT_REGULAR,
                font_size=8,
                max_width=65 * mm,
            ),
        )

    if not records:
        document.setFillColor(HexColor("#f7f8fa"))
        document.roundRect(
            x,
            top_y - height,
            width,
            height - banner_height - (4 * mm),
            3 * mm,
            fill=1,
            stroke=0,
        )
        document.setFillColor(HexColor("#8b95a1"))
        document.setFont(_FONT_REGULAR, 10)
        document.drawCentredString(
            x + (width / 2),
            top_y - banner_height - ((height - banner_height) / 2),
            "이 구간에서 탐지된 프레임이 없습니다.",
        )
        return

    row_gap = 4 * mm
    rows_top = top_y - banner_height - (4 * mm)
    row_height = (height - banner_height - (8 * mm) - row_gap) / 2
    for index, record in enumerate(records):
        row_top = rows_top - (index * (row_height + row_gap))
        _draw_frame_row(
            document,
            x=x,
            top_y=row_top,
            width=width,
            height=row_height,
            record=record,
        )


def _draw_frame_row(
    document,
    *,
    x: float,
    top_y: float,
    width: float,
    height: float,
    record: dict[str, object],
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth

    observation = record.get("observation")
    if not isinstance(observation, JudgeObservation):
        raise TypeError("PDF frame record requires a JudgeObservation")

    bottom_y = top_y - height
    image_width = 77 * mm
    capture_path = Path(str(record.get("capture_path") or record.get("frame_path") or ""))
    _draw_cropped_image(
        document,
        capture_path=capture_path,
        x=x,
        y=bottom_y + (1.5 * mm),
        width=image_width,
        height=height - (3 * mm),
    )

    risk_label, risk_color = _RISK_LABELS[observation.risk_level]
    content_x = x + image_width + (7 * mm)
    content_width = width - image_width - (7 * mm)

    document.setFillColor(HexColor(risk_color))
    badge_width = max(14 * mm, stringWidth(risk_label, _FONT_SEMIBOLD, 8.5) + (7 * mm))
    document.roundRect(
        content_x,
        top_y - (8 * mm),
        badge_width,
        6.5 * mm,
        3.25 * mm,
        fill=1,
        stroke=0,
    )
    document.setFillColor(HexColor("#ffffff"))
    document.setFont(_FONT_SEMIBOLD, 8.5)
    document.drawCentredString(
        content_x + (badge_width / 2),
        top_y - (5.7 * mm),
        risk_label,
    )

    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 11)
    document.drawString(
        content_x + badge_width + (4 * mm),
        top_y - (6.3 * mm),
        f"{format_timecode(observation.video_time_ms)} 프레임",
    )

    video_name = _fit_text(
        _normalize_pdf_text(record.get("video_name", "영상")),
        font_name=_FONT_REGULAR,
        font_size=8,
        max_width=content_width,
    )
    document.setFillColor(HexColor("#8b95a1"))
    document.setFont(_FONT_REGULAR, 8)
    document.drawString(content_x, top_y - (14 * mm), video_name)

    document.setFillColor(HexColor("#4e5968"))
    document.setFont(_FONT_SEMIBOLD, 8.5)
    document.drawString(content_x, top_y - (22 * mm), "판단 근거")
    _draw_paragraph(
        document,
        text=observation.evidence or "판단 근거 없음",
        x=content_x,
        top_y=top_y - (26 * mm),
        width=content_width,
        max_height=height - (29 * mm),
        font_size=8.5,
        leading=11.5,
    )

    document.setStrokeColor(HexColor("#d1d6db"))
    document.setLineWidth(0.45)
    document.line(x, bottom_y, x + width, bottom_y)


def _draw_cropped_image(
    document,
    *,
    capture_path: Path,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    document.setFillColor(HexColor("#f2f4f6"))
    document.rect(x, y, width, height, fill=1, stroke=0)
    try:
        image = ImageReader(str(capture_path))
        source_width, source_height = image.getSize()
        scale = max(width / source_width, height / source_height)
        draw_width = source_width * scale
        draw_height = source_height * scale
        document.saveState()
        try:
            clip = document.beginPath()
            clip.rect(x, y, width, height)
            document.clipPath(clip, stroke=0, fill=0)
            document.drawImage(
                image,
                x + ((width - draw_width) / 2),
                y + ((height - draw_height) / 2),
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        finally:
            document.restoreState()
    except Exception:  # noqa: BLE001
        document.setFillColor(HexColor("#8b95a1"))
        document.setFont(_FONT_REGULAR, 8.5)
        document.drawCentredString(
            x + (width / 2),
            y + (height / 2),
            "캡처 이미지를 불러올 수 없습니다.",
        )


def _draw_paragraph(
    document,
    *,
    text: str,
    x: float,
    top_y: float,
    width: float,
    max_height: float,
    font_size: float,
    leading: float,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    normalized_text = _normalize_pdf_text(text).strip()
    if len(normalized_text) > 190:
        normalized_text = normalized_text[:189].rstrip() + "…"
    normalized_text = "<br/>".join(escape(line) for line in normalized_text.splitlines())
    paragraph = Paragraph(
        normalized_text,
        ParagraphStyle(
            "CaptureEvidence",
            fontName=_FONT_REGULAR,
            fontSize=font_size,
            leading=leading,
            textColor=HexColor("#333d4b"),
            splitLongWords=True,
            spaceAfter=0,
        ),
    )
    _, paragraph_height = paragraph.wrap(width, max_height)
    paragraph.drawOn(document, x, top_y - min(paragraph_height, max_height))


def _draw_korail_logo(
    document,
    *,
    x: float,
    y: float,
    max_width: float,
    max_height: float,
) -> None:
    from reportlab.lib.utils import ImageReader

    logo_resource = resources.files("korail_program.assets.branding").joinpath(
        "korail-logo.png"
    )
    with resources.as_file(logo_resource) as logo_path:
        image = ImageReader(str(logo_path))
        source_width, source_height = image.getSize()
        scale = min(max_width / source_width, max_height / source_height)
        document.drawImage(
            image,
            x,
            y,
            width=source_width * scale,
            height=source_height * scale,
            preserveAspectRatio=True,
            mask="auto",
        )


def _risk_count_text(records: list[dict[str, object]]) -> str:
    counts = Counter(
        observation.risk_level
        for record in records
        if isinstance((observation := record.get("observation")), JudgeObservation)
    )
    labels = [
        f"{_RISK_LABELS[risk][0]} {counts[risk]}건"
        for risk in (RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW)
        if counts[risk]
    ]
    return ", ".join(labels) if labels else "의심 지장수목 없음"


def _summarize_values(values: list[str], *, fallback: str = "-") -> str:
    normalized = [value for value in values if value]
    if not normalized:
        return fallback
    if len(normalized) <= 2:
        return ", ".join(normalized)
    return f"{normalized[0]}, {normalized[1]} 외 {len(normalized) - 2}개"


def _matching_event(
    events: list[AnalysisEvent], observation: JudgeObservation
) -> AnalysisEvent | None:
    return next(
        (
            event
            for event in events
            if event.video_id == observation.video_id
            and event.start_time_ms <= observation.video_time_ms < event.end_time_ms
        ),
        None,
    )


def _matching_section(
    sections: list[SectionMapping], observation: JudgeObservation
) -> SectionMapping | None:
    return next(
        (
            section
            for section in sections
            if section.video_id == observation.video_id
            and section.start_time_ms <= observation.video_time_ms < section.end_time_ms
        ),
        None,
    )


def _unique_frame_records(
    suspicious_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Keep one conservative evaluation for each video timestamp."""

    selected: dict[tuple[int, int], dict[str, object]] = {}
    for record in suspicious_records:
        observation = record.get("observation")
        if not isinstance(observation, JudgeObservation):
            continue
        key = (observation.video_id, observation.video_time_ms)
        current = selected.get(key)
        if current is None or _record_score(record) > _record_score(current):
            selected[key] = record
    return sorted(selected.values(), key=_record_sort_key)


def _record_score(record: dict[str, object]) -> tuple[int, int, int]:
    observation = record.get("observation")
    if not isinstance(observation, JudgeObservation):
        return (-1, 0, 0)
    return (
        observation.risk_level.priority,
        int(bool(record.get("capture_path"))),
        len(observation.evidence or ""),
    )


def _record_sort_key(record: dict[str, object]) -> tuple[int, int]:
    observation = record.get("observation")
    if not isinstance(observation, JudgeObservation):
        return (0, 0)
    return (observation.video_id, observation.video_time_ms)


def _group_records_by_section(
    records: list[dict[str, object]],
    *,
    events: list[AnalysisEvent],
    sections: list[SectionMapping],
) -> list[_SectionGroup]:
    grouped: dict[tuple[int, str], _SectionGroup] = {}
    for record in records:
        observation = record.get("observation")
        if not isinstance(observation, JudgeObservation):
            continue
        section = _matching_section(sections, observation)
        event = _matching_event(events, observation) if section is None else None
        if section is not None:
            section_label = format_section_label(section.section_start, section.section_end)
        elif event is not None:
            section_label = format_section_label(event.section_start, event.section_end)
        else:
            section_label = "구간 미확인"
        video_name = _normalize_pdf_text(record.get("video_name", "영상")).strip() or "영상"
        key = (observation.video_id, section_label)
        group = grouped.get(key)
        if group is None:
            group = _SectionGroup(
                video_id=observation.video_id,
                video_name=video_name,
                section_label=section_label,
                records=[],
            )
            grouped[key] = group
        group.records.append(record)
    return list(grouped.values())


def _build_report_pages(groups: list[_SectionGroup]) -> list[_ReportPage]:
    pages: list[_ReportPage] = []
    for group in groups:
        for index in range(0, len(group.records), 2):
            pages.append(
                _ReportPage(
                    video_name=group.video_name,
                    section_label=group.section_label,
                    records=group.records[index : index + 2],
                    continued=index > 0,
                )
            )
    return pages or [
        _ReportPage(video_name="", section_label="구간 미확인", records=[])
    ]


def _video_titles(
    video_titles: list[str] | None,
    suspicious_records: list[dict[str, object]],
) -> list[str]:
    candidates: list[object] = list(video_titles or [])
    if not candidates:
        candidates.extend(record.get("video_name") for record in suspicious_records)
    normalized_titles = [_normalize_pdf_text(value).strip() for value in candidates]
    return list(dict.fromkeys(title for title in normalized_titles if title))


def _normalize_pdf_text(value: object) -> str:
    if isinstance(value, bytes):
        for encoding in ("utf-8", "cp949", "latin-1"):
            try:
                return normalize("NFC", value.decode(encoding))
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")

    text = normalize("NFC", str(value or ""))
    if text and not any("가" <= character <= "힣" for character in text):
        try:
            repaired = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        else:
            if any("가" <= character <= "힣" for character in repaired):
                text = repaired
    return text


def _fit_text(text: str, *, font_name: str, font_size: float, max_width: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = _normalize_pdf_text(text)
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "…"
    available = max_width - stringWidth(ellipsis, font_name, font_size)
    fitted: list[str] = []
    for character in text:
        candidate = "".join((*fitted, character))
        if stringWidth(candidate, font_name, font_size) > available:
            break
        fitted.append(character)
    return "".join(fitted).rstrip() + ellipsis
