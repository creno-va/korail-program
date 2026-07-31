"""Printable PDF report with one suspicious frame per page."""

from __future__ import annotations

from html import escape
from importlib import resources
from pathlib import Path

from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel
from korail_program.core.timecode import format_timecode

_FONT_REGULAR = "PretendardGOV-PDF-Regular"
_FONT_SEMIBOLD = "PretendardGOV-PDF-SemiBold"


def write_pdf_report(
    *,
    output_dir: Path,
    video_count: int,
    sampled_frame_count: int,
    suspicious_records: list[dict[str, object]],
    events: list[AnalysisEvent],
    failures: list[dict[str, object]],
) -> Path:
    """Write a PDF where every suspicious frame occupies exactly one page."""

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
    document.setTitle("지장수목 의심 프레임 분석 리포트")
    document.setAuthor("전차선로 지장수목 분석")

    total_pages = len(suspicious_records)
    if suspicious_records:
        for page_number, record in enumerate(suspicious_records, start=1):
            _draw_frame_page(
                document,
                record=record,
                events=events,
                page_number=page_number,
                total_pages=total_pages,
                video_count=video_count,
                sampled_frame_count=sampled_frame_count,
                failure_count=len(failures),
            )
            document.showPage()
    else:
        _draw_empty_page(
            document,
            video_count=video_count,
            sampled_frame_count=sampled_frame_count,
            event_count=len(events),
            failure_count=len(failures),
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


def _draw_frame_page(
    document,
    *,
    record: dict[str, object],
    events: list[AnalysisEvent],
    page_number: int,
    total_pages: int,
    video_count: int,
    sampled_frame_count: int,
    failure_count: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth

    page_width, page_height = A4
    margin = 15 * mm
    content_width = page_width - (margin * 2)

    observation = record.get("observation")
    if not isinstance(observation, JudgeObservation):
        raise TypeError("PDF frame record requires a JudgeObservation")
    event = _matching_event(events, observation)
    video_name = _fit_text(
        str(record.get("video_name", "영상")),
        font_name=_FONT_SEMIBOLD,
        font_size=11,
        max_width=content_width - (58 * mm),
    )

    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 18)
    document.drawString(margin, page_height - (18 * mm), "지장수목 의심 프레임")

    page_text = f"{page_number} / {total_pages}"
    document.setFont(_FONT_REGULAR, 9)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawRightString(page_width - margin, page_height - (17.5 * mm), page_text)

    meta_y = page_height - (28 * mm)
    document.setFont(_FONT_SEMIBOLD, 11)
    document.setFillColor(HexColor("#333d4b"))
    document.drawString(margin, meta_y, video_name)
    time_text = format_timecode(observation.video_time_ms)
    time_x = margin + stringWidth(video_name, _FONT_SEMIBOLD, 11) + (5 * mm)
    document.setFont(_FONT_REGULAR, 10)
    document.setFillColor(HexColor("#6b7684"))
    document.drawString(time_x, meta_y, time_text)
    _draw_risk_chip(
        document,
        risk_level=observation.risk_level,
        right_x=page_width - margin,
        center_y=meta_y + (1.5 * mm),
    )

    image_x = margin
    image_y = 138 * mm
    image_width = content_width
    image_height = 112 * mm
    document.setFillColor(HexColor("#f2f4f6"))
    document.roundRect(image_x, image_y, image_width, image_height, 8, fill=1, stroke=0)

    capture_path = Path(str(record.get("capture_path") or record.get("frame_path") or ""))
    try:
        image = ImageReader(str(capture_path))
        source_width, source_height = image.getSize()
        scale = min(image_width / source_width, image_height / source_height)
        draw_width = source_width * scale
        draw_height = source_height * scale
        document.drawImage(
            image,
            image_x + ((image_width - draw_width) / 2),
            image_y + ((image_height - draw_height) / 2),
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:  # noqa: BLE001
        document.setFont(_FONT_REGULAR, 10)
        document.setFillColor(HexColor("#8b95a1"))
        document.drawCentredString(
            page_width / 2,
            image_y + (image_height / 2),
            "캡처 이미지를 불러올 수 없습니다.",
        )

    section = f"{event.section_start} ~ {event.section_end}" if event is not None else "구간 미확인"
    review_status = event.review_status.value if event is not None else "미확인"
    detail_y = 124 * mm
    _draw_label_value(
        document,
        x=margin,
        y=detail_y,
        label="구간",
        value=section,
        max_width=118 * mm,
    )
    _draw_label_value(
        document,
        x=page_width - margin - (48 * mm),
        y=detail_y,
        label="검수",
        value=review_status,
    )

    document.setFont(_FONT_SEMIBOLD, 10)
    document.setFillColor(HexColor("#333d4b"))
    document.drawString(margin, 108 * mm, "판단 근거")
    _draw_paragraph(
        document,
        text=observation.evidence or "판단 근거 없음",
        x=margin,
        top_y=101 * mm,
        width=content_width,
        max_height=54 * mm,
    )

    footer_text = (
        f"분석 영상 {video_count}개  ·  샘플 프레임 {sampled_frame_count}개"
        f"  ·  의심 프레임 {total_pages}개  ·  처리 실패 {failure_count}건"
    )
    document.setFont(_FONT_REGULAR, 8)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawString(margin, 14 * mm, footer_text)


def _draw_empty_page(
    document,
    *,
    video_count: int,
    sampled_frame_count: int,
    event_count: int,
    failure_count: int,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 20 * mm
    document.setFillColor(HexColor("#191f28"))
    document.setFont(_FONT_SEMIBOLD, 20)
    document.drawString(margin, page_height - (24 * mm), "지장수목 분석 리포트")

    document.setFillColor(HexColor("#f2f4f6"))
    document.roundRect(
        margin,
        page_height - (108 * mm),
        page_width - (margin * 2),
        58 * mm,
        10,
        fill=1,
        stroke=0,
    )
    document.setFillColor(HexColor("#333d4b"))
    document.setFont(_FONT_SEMIBOLD, 14)
    document.drawCentredString(
        page_width / 2,
        page_height - (76 * mm),
        "의심 프레임이 없습니다.",
    )
    summary = (
        f"분석 영상 {video_count}개  ·  샘플 프레임 {sampled_frame_count}개  ·  "
        f"이벤트 {event_count}건  ·  처리 실패 {failure_count}건"
    )
    document.setFont(_FONT_REGULAR, 10)
    document.setFillColor(HexColor("#6b7684"))
    document.drawCentredString(page_width / 2, page_height - (88 * mm), summary)


def _draw_risk_chip(document, *, risk_level: RiskLevel, right_x: float, center_y: float) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth

    background, foreground = {
        RiskLevel.HIGH: ("#feecef", "#d33b4c"),
        RiskLevel.MEDIUM: ("#fff4e5", "#b25d00"),
        RiskLevel.LOW: ("#e8f8f2", "#008f6a"),
        RiskLevel.NONE: ("#f2f4f6", "#6b7684"),
    }[risk_level]
    text = risk_level.value
    chip_width = stringWidth(text, _FONT_SEMIBOLD, 9) + (7 * mm)
    chip_height = 7 * mm
    chip_x = right_x - chip_width
    chip_y = center_y - (chip_height / 2)
    document.setFillColor(HexColor(background))
    document.roundRect(chip_x, chip_y, chip_width, chip_height, chip_height / 2, fill=1, stroke=0)
    document.setFillColor(HexColor(foreground))
    document.setFont(_FONT_SEMIBOLD, 9)
    document.drawCentredString(chip_x + (chip_width / 2), chip_y + (2.2 * mm), text)


def _draw_label_value(
    document,
    *,
    x: float,
    y: float,
    label: str,
    value: str,
    max_width: float | None = None,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm

    document.setFont(_FONT_REGULAR, 9)
    document.setFillColor(HexColor("#8b95a1"))
    document.drawString(x, y, label)
    document.setFont(_FONT_SEMIBOLD, 10)
    document.setFillColor(HexColor("#333d4b"))
    fitted_value = (
        _fit_text(
            value,
            font_name=_FONT_SEMIBOLD,
            font_size=10,
            max_width=max_width,
        )
        if max_width is not None
        else value
    )
    document.drawString(x, y - (6 * mm), fitted_value)


def _draw_paragraph(
    document,
    *,
    text: str,
    x: float,
    top_y: float,
    width: float,
    max_height: float,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    normalized = text.strip()
    if len(normalized) > 420:
        normalized = normalized[:419].rstrip() + "…"
    normalized = "<br/>".join(escape(line) for line in normalized.splitlines())
    paragraph = Paragraph(
        normalized,
        ParagraphStyle(
            "FrameEvidence",
            fontName=_FONT_REGULAR,
            fontSize=10,
            leading=16,
            textColor=HexColor("#4e5968"),
            splitLongWords=True,
            spaceAfter=0,
        ),
    )
    _, paragraph_height = paragraph.wrap(width, max_height)
    paragraph.drawOn(document, x, top_y - min(paragraph_height, max_height))


def _matching_event(
    events: list[AnalysisEvent], observation: JudgeObservation
) -> AnalysisEvent | None:
    return next(
        (
            event
            for event in events
            if event.video_id == observation.video_id
            and event.start_time_ms <= observation.video_time_ms <= event.end_time_ms
        ),
        None,
    )


def _fit_text(text: str, *, font_name: str, font_size: float, max_width: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth

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
