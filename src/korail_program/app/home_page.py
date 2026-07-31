"""Three-step landing page for the video analysis workflow."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from korail_program.app.widgets import ActionButton, ProgressTrack


class WorkflowHomePage(QFrame):
    """Present the upload, analysis, and report workflow as three steps."""

    upload_requested = Signal()
    analysis_requested = Signal()
    report_requested = Signal()
    detail_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HomePage")
        self._build_ui()
        self.set_workflow_state(has_video=False, has_report=False, selected_file=None)

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(56, 48, 56, 28)
        page_layout.setSpacing(28)

        content = QWidget()
        content.setObjectName("HomeContent")
        content.setMinimumWidth(1000)
        content.setMaximumWidth(1120)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(32)

        title = QLabel("전차선로 지장수목 분석")
        title.setObjectName("HomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)

        steps = QHBoxLayout()
        steps.setSpacing(20)

        self.selected_file_label = QLabel("선택된 영상 없음")
        self.selected_file_label.setObjectName("HomeFileName")
        self.selected_file_label.setWordWrap(True)
        self.upload_button = ActionButton(
            "영상 업로드",
            icon_name="upload",
            tone="primary",
        )
        self.upload_button.clicked.connect(self.upload_requested)
        upload_step, upload_number = self._build_step(
            number=1,
            description="분석할 영상 파일을 선택해 작업 목록에 등록합니다.",
            button=self.upload_button,
            extras=(self.selected_file_label,),
        )

        self.analysis_button = ActionButton(
            "분석",
            icon_name="play-circle-outline",
        )
        self.analysis_button.clicked.connect(self.analysis_requested)
        self.progress = ProgressTrack()
        analysis_step, analysis_number = self._build_step(
            number=2,
            description="선택한 영상을 AI로 분석하고 진행 상태를 확인합니다.",
            button=self.analysis_button,
            extras=(self.progress,),
        )

        self.report_button = ActionButton(
            "보고서",
        )
        self.report_button.clicked.connect(self.report_requested)
        report_step, report_number = self._build_step(
            number=3,
            description="탐지 프레임을 페이지별로 정리한 PDF를 저장합니다.",
            button=self.report_button,
        )

        self._step_frames = (upload_step, analysis_step, report_step)
        self._step_numbers = (upload_number, analysis_number, report_number)
        steps.addWidget(upload_step, stretch=1)
        steps.addWidget(analysis_step, stretch=1)
        steps.addWidget(report_step, stretch=1)
        content_layout.addLayout(steps)

        page_layout.addStretch(1)
        page_layout.addWidget(content, alignment=Qt.AlignmentFlag.AlignHCenter)
        page_layout.addStretch(1)

        self.detail_button = ActionButton(
            "자세히 보기",
            icon_name="arrow-right",
            small=True,
        )
        self.detail_button.setFixedWidth(136)
        self.detail_button.clicked.connect(self.detail_requested)
        page_layout.addWidget(
            self.detail_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

    @staticmethod
    def _build_step(
        *,
        number: int,
        description: str,
        button: ActionButton,
        extras: tuple[QWidget, ...] = (),
    ) -> tuple[QFrame, QLabel]:
        step = QFrame()
        step.setObjectName("HomeStep")
        step.setProperty("stepState", "pending")
        step.setMinimumHeight(310)
        step_layout = QVBoxLayout(step)
        step_layout.setContentsMargins(24, 24, 24, 24)
        step_layout.setSpacing(18)

        number_label = QLabel(str(number))
        number_label.setObjectName("HomeStepNumber")
        number_label.setProperty("stepState", "pending")
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setFixedSize(38, 38)

        description_label = QLabel(description)
        description_label.setObjectName("HomeStepDescription")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        button.setProperty("homeStep", True)
        button.setFixedHeight(60)

        step_layout.addWidget(number_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        step_layout.addWidget(description_label)
        for extra in extras:
            step_layout.addWidget(extra)
        step_layout.addStretch(1)
        step_layout.addWidget(button)
        return step, number_label

    def set_progress(self, value: int, tone: str) -> None:
        self.progress.setValue(value)
        self.progress.set_tone(tone)

    def set_progress_tone(self, tone: str) -> None:
        self.progress.set_tone(tone)

    def set_analysis_action(
        self,
        *,
        text: str,
        icon: str,
        tone: str,
        tooltip: str,
        enabled: bool,
    ) -> None:
        self.analysis_button.setText(text)
        self.analysis_button.set_icon(icon)
        self.analysis_button.set_tone(tone)
        self.analysis_button.setToolTip(tooltip)
        self.analysis_button.setEnabled(enabled)

    def set_workflow_state(
        self,
        *,
        has_video: bool,
        has_report: bool,
        selected_file: str | None,
    ) -> None:
        if not has_video:
            states = ("active", "pending", "pending")
        elif not has_report:
            states = ("complete", "active", "pending")
        else:
            states = ("complete", "complete", "active")

        for frame, number, state in zip(
            self._step_frames,
            self._step_numbers,
            states,
            strict=True,
        ):
            self._set_step_state(frame, state)
            self._set_step_state(number, state)

        self.selected_file_label.setText(selected_file or "선택된 영상 없음")
        self.upload_button.set_tone("neutral" if has_video else "primary")
        self.report_button.set_tone("primary" if has_report else "neutral")
        self.report_button.setEnabled(has_report)

    @staticmethod
    def _set_step_state(widget: QWidget, state: str) -> None:
        widget.setProperty("stepState", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
