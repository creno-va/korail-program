"""In-app Ollama model installation and selection dialog."""

from __future__ import annotations

import re

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.widgets import ActionButton, StatusChip
from korail_program.judge.ollama_client import OllamaApiError, test_ollama_connection
from korail_program.model_catalog import (
    ModelOption,
    SystemProfile,
    normalize_model_tag,
    ordered_model_options,
    recommend_model,
    recommended_reason,
    system_profile_details,
    system_profile_label,
)
from korail_program.runtime import list_installed_ollama_models, ollama_process_environment

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3})%")


class ModelSettingsDialog(QDialog):
    model_selected = Signal(str)

    def __init__(
        self,
        *,
        current_model: str,
        installed_models: set[str],
        profile: SystemProfile,
        ollama_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_model = current_model
        self.installed_models = set(installed_models)
        self.profile = profile
        self.ollama_path = ollama_path
        self.recommended = recommend_model(profile)
        self._process: QProcess | None = None
        self._pending_model: str | None = None
        self._state_chips: dict[str, StatusChip] = {}
        self._select_buttons: dict[str, ActionButton] = {}
        self._install_buttons: dict[str, ActionButton] = {}
        self.setWindowTitle("로컬 AI 모델")
        self.setMinimumSize(720, 720)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("로컬 AI 모델 설치 및 선택")
        title.setObjectName("SectionTitle")
        self.current_chip = StatusChip(self.current_model, "primary")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.current_chip)
        root.addLayout(header)

        profile_card = QFrame()
        profile_card.setObjectName("ModelCard")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(16, 16, 16, 16)
        profile_layout.setSpacing(7)
        profile_top = QHBoxLayout()
        profile_title = QLabel("현재 컴퓨터 사양")
        profile_title.setObjectName("CardTitle")
        profile_top.addWidget(profile_title)
        profile_top.addStretch(1)
        profile_top.addWidget(StatusChip(system_profile_label(self.profile), "neutral"))
        profile_text = QLabel("\n".join(system_profile_details(self.profile)))
        profile_text.setObjectName("PanelText")
        profile_text.setWordWrap(True)
        reason = QLabel(recommended_reason(self.profile, self.recommended))
        reason.setObjectName("PanelText")
        reason.setWordWrap(True)
        profile_layout.addLayout(profile_top)
        profile_layout.addWidget(profile_text)
        profile_layout.addWidget(reason)
        root.addWidget(profile_card)

        scroll = QScrollArea()
        scroll.setObjectName("CardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("CardListContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        for option in ordered_model_options(self.profile):
            content_layout.addWidget(self._model_card(option))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        progress_card = QFrame()
        progress_card.setObjectName("ModelCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(14, 12, 14, 12)
        self.progress_label = QLabel("모델을 설치하면 다운로드 진행률이 여기에 표시됩니다.")
        self.progress_label.setObjectName("Tiny")
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        root.addWidget(progress_card)

        footer = QHBoxLayout()
        refresh_button = ActionButton("설치 상태 새로고침", icon_name="refresh")
        refresh_button.clicked.connect(self._refresh_installed_models)
        close_button = ActionButton("닫기", icon_name="close")
        close_button.clicked.connect(self.reject)
        footer.addWidget(refresh_button)
        footer.addStretch(1)
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _model_card(self, option: ModelOption) -> QFrame:
        card = QFrame()
        card.setObjectName("ModelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        name = QLabel(option.name)
        name.setObjectName("CardTitle")
        state = StatusChip("", "neutral")
        self._state_chips[option.tag] = state
        top.addWidget(name)
        top.addWidget(StatusChip(option.tier, "neutral"))
        if option.tag == self.recommended.tag:
            top.addWidget(StatusChip("사양 추천 · 최상단", "success"))
        top.addWidget(state)
        top.addStretch(1)

        vram = (
            f" / 권장 VRAM {option.recommended_vram_gb}GB"
            if option.recommended_vram_gb is not None
            else ""
        )
        meta = QLabel(
            f"{option.tag} / 다운로드 {option.size_label} / 최소 RAM {option.min_ram_gb}GB{vram}"
        )
        meta.setObjectName("Tiny")
        description = QLabel(option.description)
        description.setObjectName("PanelText")
        description.setWordWrap(True)

        actions = QHBoxLayout()
        actions.addStretch(1)
        select_button = ActionButton("사용", icon_name="check")
        select_button.clicked.connect(lambda tag=option.tag: self._select(tag))
        install_button = ActionButton("설치", icon_name="download-outline")
        install_button.clicked.connect(lambda tag=option.tag: self._install(tag))
        self._select_buttons[option.tag] = select_button
        self._install_buttons[option.tag] = install_button
        actions.addWidget(select_button)
        actions.addWidget(install_button)

        layout.addLayout(top)
        layout.addWidget(meta)
        layout.addWidget(description)
        layout.addLayout(actions)
        self._refresh_card(option.tag)
        return card

    def _is_installed(self, tag: str) -> bool:
        target = normalize_model_tag(tag)
        return any(normalize_model_tag(item) == target for item in self.installed_models)

    def _refresh_card(self, tag: str) -> None:
        installed = self._is_installed(tag)
        selected = normalize_model_tag(tag) == normalize_model_tag(self.current_model)
        chip = self._state_chips[tag]
        if installed and selected:
            chip.setText("사용 중")
            chip.set_tone("primary")
        elif installed:
            chip.setText("설치됨")
            chip.set_tone("success")
        else:
            chip.setText("미설치")
            chip.set_tone("neutral")
        self._select_buttons[tag].setEnabled(installed and not selected and not self._is_busy())
        self._install_buttons[tag].setText("재설치" if installed else "설치")
        self._install_buttons[tag].setEnabled(not self._is_busy())

    def _refresh_all_cards(self) -> None:
        for tag in self._state_chips:
            self._refresh_card(tag)
        self.current_chip.setText(self.current_model)

    def _select(self, tag: str) -> None:
        if not self._is_installed(tag):
            QMessageBox.information(self, "모델 설치 필요", "사용하기 전에 모델을 설치하세요.")
            return
        self.current_model = tag
        self.model_selected.emit(tag)
        self._refresh_all_cards()

    def _install(self, tag: str) -> None:
        if self._is_busy():
            return
        option = next(item for item in ordered_model_options(self.profile) if item.tag == tag)
        if (
            self.profile.free_disk_gb is not None
            and self.profile.free_disk_gb < option.size_gb * 1.2
        ):
            QMessageBox.warning(
                self,
                "저장 공간 부족",
                f"{option.name} 설치에는 약 {option.size_label}가 필요합니다. "
                f"현재 여유 공간은 {self.profile.free_disk_gb:.1f}GB입니다.",
            )
            return

        process = QProcess(self)
        self._process = process
        self._pending_model = tag
        process.setProgram(self.ollama_path)
        process.setArguments(["pull", tag])
        process.setProcessEnvironment(_process_environment())
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_pull_output)
        process.errorOccurred.connect(self._handle_pull_error)
        process.finished.connect(self._handle_pull_finished)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(f"{option.name} 다운로드 준비 중…")
        self._refresh_all_cards()
        process.start()

    def _read_pull_output(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        cleaned = _ANSI_RE.sub("", text).replace("\r", "\n")
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return
        message = lines[-1]
        matches = _PERCENT_RE.findall(cleaned)
        if matches:
            percent = max(0, min(100, int(matches[-1])))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
        self.progress_label.setText(message[-180:])

    def _handle_pull_error(self, error: QProcess.ProcessError) -> None:
        if self._process is None:
            return
        error_message = self._process.errorString()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"모델 설치 실행 실패: {error_message}")
        if error == QProcess.ProcessError.FailedToStart:
            self._pending_model = None
            self._process = None
            self._refresh_all_cards()
            QMessageBox.warning(self, "모델 설치 실행 실패", error_message)

    def _handle_pull_finished(self, exit_code: int, _exit_status=None) -> None:
        model = self._pending_model
        self._pending_model = None
        self._process = None
        self.progress_bar.setRange(0, 100)
        if exit_code == 0 and model:
            self.installed_models.add(model)
            self.current_model = model
            self.model_selected.emit(model)
            self.progress_bar.setValue(100)
            self.progress_label.setText(f"{model} 설치 완료 · 현재 분석 모델로 선택했습니다.")
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText(
                "모델 설치에 실패했습니다. Ollama 로그와 네트워크를 확인하세요."
            )
            QMessageBox.warning(self, "모델 설치 실패", self.progress_label.text())
        self._refresh_all_cards()

    def _refresh_installed_models(self) -> None:
        try:
            test_ollama_connection()
        except OllamaApiError as exc:
            QMessageBox.warning(self, "Ollama 연결 실패", str(exc))
            return
        self.installed_models = list_installed_ollama_models(self.ollama_path)
        self._refresh_all_cards()
        self.progress_label.setText(
            f"설치된 로컬 모델 {len(self.installed_models)}개를 확인했습니다."
        )

    def _is_busy(self) -> bool:
        return self._process is not None

    def reject(self) -> None:
        if self._is_busy():
            QMessageBox.information(
                self, "다운로드 진행 중", "모델 설치가 끝난 뒤 창을 닫아주세요."
            )
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._is_busy():
            QMessageBox.information(
                self, "다운로드 진행 중", "모델 설치가 끝난 뒤 창을 닫아주세요."
            )
            event.ignore()
            return
        super().closeEvent(event)


def _process_environment() -> QProcessEnvironment:
    env = QProcessEnvironment.systemEnvironment()
    for key, value in ollama_process_environment().items():
        env.insert(key, value)
    return env
