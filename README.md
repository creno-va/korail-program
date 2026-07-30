# Korail 지장수목 분석 프로그램

전방 주행 영상에서 전차선로 주변 지장수목 후보 구간을 오프라인으로 분석하고, 검수용 캡처와 리포트로 정리하는 Python 데스크톱 프로그램입니다.

현재 저장소는 GUI 작업대와 분석 파이프라인 골격을 먼저 구축한 초기 구현입니다. 실제 Gemma/PaddleOCR/FFmpeg 실행 어댑터는 다음 단계에서 연결합니다.

## 기술 방향

- Python 3.11+ CPython
- GUI: PySide6, Qt Widgets
- 디자인: Pretendard GOV 폰트, Material Design Icons, grayscale + success/warning/error 상태색
- 프레임 judge: 로컬 멀티모달 LLM(Gemma 계열) 기반 VQA
- 역명/OCR: PaddleOCR + 역명 사전 보정
- 결과 저장: SQLite, 캡처 이미지, PDF/Excel 리포트

## 실행

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\run_gui.cmd
```

테스트:

```powershell
.\scripts\test.cmd
```

PowerShell 스크립트를 선호하면 다음처럼 실행할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

설치부터 Ollama 모델 다운로드까지 한 번에 진행하려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

### macOS

```sh
python3 --version
sh scripts/bootstrap.sh
sh scripts/run_gui.sh
```

테스트:

```sh
sh scripts/test.sh
```

`python3`가 3.11 미만이면 Homebrew, pyenv 등으로 Python 3.11 이상을 먼저 설치하세요.

설치부터 Ollama 모델 다운로드까지 한 번에 진행하려면:

```sh
sh scripts/install_macos.sh
```

## 루트 영상 배치 분석

프로젝트 루트에 있는 `mp4`, `avi`, `mov`, `mkv` 영상을 일정 간격으로 샘플링하고, 로컬 Gemma VLM으로 전차선/가공전차선 주변 지장수목 의심 프레임을 판정합니다.

Windows:

```powershell
.\scripts\analyze_root_videos.cmd
```

macOS:

```sh
sh scripts/analyze_root_videos.sh
```

기본값:

- 모델: `gemma3:4b`
- 샘플링 간격: 10초
- 리포트 포함 기준: `중간` 이상
- 산출물: `output/analysis.../report.html`, `report.md`, `observations.json`, `events.json`, `captures/`

간격을 바꾸려면:

```powershell
$env:KORAIL_INTERVAL_SEC=5
.\scripts\analyze_root_videos.cmd
```

## 문서

- [문서 인덱스](./docs/README.md)
- [프로젝트 결정 사항](./docs/decisions.md)
- [사용자 플로우](./docs/user-flow.md)
- [분석 파이프라인 설계](./docs/pipeline-design.md)
- [개발 환경 및 배포 방향](./docs/dev-env-and-packaging.md)

## 다음 구현 후보

1. GUI 작업 큐와 실제 분석 worker 연결
2. FFmpeg/OpenCV 프레임 추출 실행 경로 통합
3. Gemma judge 호출 어댑터 연결
4. PaddleOCR ROI 및 역명 사전 보정 연결
5. SQLite 저장과 PDF/Excel 리포트 생성
