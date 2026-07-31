"""GPT vision model catalog and lightweight environment summary."""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelOption:
    tag: str
    name: str
    tier: str
    size_label: str
    min_ram_gb: int
    recommended_vram_gb: int | None
    description: str


@dataclass(frozen=True, slots=True)
class SystemProfile:
    ram_gb: float | None = None
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None


MODEL_OPTIONS: tuple[ModelOption, ...] = (
    ModelOption(
        tag="gpt-5.6-terra",
        name="GPT-5.6 Terra",
        tier="기본 추천",
        size_label="정확도/비용 균형",
        min_ram_gb=0,
        recommended_vram_gb=None,
        description=(
            "전차선로 지장수목 VQA의 기본 모델입니다. 반복 프레임 분석에서 "
            "정확도와 처리 비용의 균형이 가장 좋도록 설정합니다."
        ),
    ),
    ModelOption(
        tag="gpt-5.6-sol",
        name="GPT-5.6 Sol",
        tier="최고 정확도",
        size_label="정밀 검토",
        min_ram_gb=0,
        recommended_vram_gb=None,
        description=(
            "의심 프레임이 많거나 리포트 품질을 우선해야 할 때 사용합니다. "
            "속도와 비용보다 판정 안정성을 우선하는 옵션입니다."
        ),
    ),
    ModelOption(
        tag="gpt-5.6-luna",
        name="GPT-5.6 Luna",
        tier="저비용",
        size_label="빠른 예비 분석",
        min_ram_gb=0,
        recommended_vram_gb=None,
        description=(
            "대량 영상을 빠르게 훑는 예비 분석용 옵션입니다. 이벤트 후보를 먼저 "
            "좁힌 뒤 Terra나 Sol로 재확인하는 흐름에 적합합니다."
        ),
    ),
    ModelOption(
        tag="gpt-4.1-mini",
        name="GPT-4.1 mini",
        tier="호환",
        size_label="Legacy API",
        min_ram_gb=0,
        recommended_vram_gb=None,
        description=(
            "기존 GPT-4.1 mini 기반 결과와 비교해야 할 때 남겨둔 호환 옵션입니다. "
            "신규 배포의 기본값은 GPT-5.6 Terra입니다."
        ),
    ),
)


def get_model_option(tag: str) -> ModelOption:
    for option in MODEL_OPTIONS:
        if option.tag == tag:
            return option
    return MODEL_OPTIONS[0]


def detect_system_profile() -> SystemProfile:
    ram_gb = _detect_ram_gb()
    gpu_name, gpu_vram_gb = _detect_nvidia_gpu()
    return SystemProfile(ram_gb=ram_gb, gpu_name=gpu_name, gpu_vram_gb=gpu_vram_gb)


def recommend_model(profile: SystemProfile) -> ModelOption:
    return get_model_option("gpt-5.6-terra")


def system_profile_label(profile: SystemProfile) -> str:
    ram = f"RAM {profile.ram_gb:.0f}GB" if profile.ram_gb else "RAM 확인 불가"
    if profile.gpu_name and profile.gpu_vram_gb:
        return f"{ram} / {profile.gpu_name} {profile.gpu_vram_gb:.0f}GB / API 분석"
    if profile.gpu_name:
        return f"{ram} / {profile.gpu_name} / API 분석"
    return f"{ram} / API 분석"


def _detect_ram_gb() -> float | None:
    if platform.system().lower() == "windows":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024**3)
        return None

    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (pages * page_size) / (1024**3)
        except (OSError, ValueError):
            return None
    return None


def _detect_nvidia_gpu() -> tuple[str | None, float | None]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if result.returncode != 0:
        return None, None
    first_line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not first_line:
        return None, None
    parts = [part.strip() for part in first_line.split(",")]
    name = parts[0] if parts else None
    vram_gb: float | None = None
    if len(parts) > 1:
        try:
            vram_gb = float(parts[1]) / 1024
        except ValueError:
            vram_gb = None
    return name, vram_gb
