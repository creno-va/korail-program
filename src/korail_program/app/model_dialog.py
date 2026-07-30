"""Custom model selection dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from korail_program.app.widgets import ActionButton, StatusChip, horizontal_divider
from korail_program.model_catalog import (
    MODEL_OPTIONS,
    ModelOption,
    SystemProfile,
    recommend_model,
    system_profile_label,
)


class ModelSettingsDialog(QDialog):
    model_selected = Signal(str)
    install_requested = Signal(str)

    def __init__(
        self,
        *,
        current_model: str,
        installed_models: set[str],
        profile: SystemProfile,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_model = current_model
        self.installed_models = installed_models
        self.profile = profile
        self.recommended = recommend_model(profile)
        self.setWindowTitle("모델 설정")
        self.setMinimumSize(620, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("모델 설정")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(StatusChip(system_profile_label(self.profile), "neutral"))
        root.addLayout(header)
        root.addWidget(horizontal_divider())

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
        for option in MODEL_OPTIONS:
            content_layout.addWidget(self._model_card(option))
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = ActionButton("닫기", icon_name="close")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _model_card(self, option: ModelOption) -> QFrame:
        card = QFrame()
        card.setObjectName("ModelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        name = QLabel(option.name)
        name.setObjectName("CardTitle")
        top.addWidget(name)
        top.addWidget(StatusChip(option.tier, "neutral"))
        if option.tag == self.recommended.tag:
            top.addWidget(StatusChip("사양 추천", "success"))
        if option.tag == self.current_model:
            top.addWidget(StatusChip("선택됨", "warning"))
        if option.tag in self.installed_models:
            top.addWidget(StatusChip("설치됨", "success"))
        else:
            top.addWidget(StatusChip("미설치", "neutral"))
        top.addStretch(1)

        meta = QLabel(
            f"{option.tag} / {option.size_label} / RAM {option.min_ram_gb}GB 이상"
        )
        meta.setObjectName("Tiny")
        description = QLabel(option.description)
        description.setObjectName("PanelText")
        description.setWordWrap(True)

        actions = QHBoxLayout()
        actions.addStretch(1)
        select_button = ActionButton("사용", icon_name="check")
        select_button.setEnabled(option.tag in self.installed_models)
        select_button.clicked.connect(lambda tag=option.tag: self._select(tag))
        install_button = ActionButton("설치", icon_name="download-outline")
        install_button.clicked.connect(lambda tag=option.tag: self._install(tag))
        actions.addWidget(select_button)
        actions.addWidget(install_button)

        layout.addLayout(top)
        layout.addWidget(meta)
        layout.addWidget(description)
        layout.addLayout(actions)
        return card

    def _select(self, tag: str) -> None:
        self.model_selected.emit(tag)
        self.accept()

    def _install(self, tag: str) -> None:
        self.install_requested.emit(tag)
        self.accept()
