# Korail 지장수목 분석 프로그램

전방 주행 영상에서 전차선로 주변 지장수목 후보 구간을 오프라인으로 분석하고, 검수용 캡처와 리포트로 정리하는 데스크톱 프로그램입니다.

Windows 납품판은 Python 개발 환경이 없는 PC에서도 설치 마법사만으로 실행되도록 PyInstaller 앱, Ollama standalone 런타임, FFmpeg/FFprobe를 함께 포함합니다. 사용자는 앱 안의 `모델 설치` 버튼으로 `qwen2.5vl:3b`를 내려받은 뒤 바로 분석을 시작합니다.

## 기술 방향

- Python 3.11+ CPython
- GUI: PySide6, Qt Widgets
- 디자인: Pretendard GOV 폰트, Material Design Icons, grayscale + success/warning/error 상태색
- 프레임 judge: 로컬 멀티모달 LLM(`qwen2.5vl:3b`) 기반 VQA
- 역명/OCR: 기본 VLM OCR(`qwen2.5vl:3b`) + 선택형 역명 사전 보정
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

소스 체크아웃 상태에서 설치부터 Ollama 모델 다운로드까지 한 번에 진행하려면:

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

소스 체크아웃 상태에서 설치부터 Ollama 모델 다운로드까지 한 번에 진행하려면:

```sh
sh scripts/install_macos.sh
```

## 루트 영상 배치 분석

지정한 경로의 `mp4`, `avi`, `mov`, `mkv` 영상을 일정 간격으로 샘플링하고, 로컬 Gemma VLM으로 전차선/가공전차선 주변 지장수목 의심 프레임을 판정합니다.

Windows:

```powershell
.\scripts\analyze_root_videos.cmd
```

macOS:

```sh
sh scripts/analyze_root_videos.sh
```

기본값:

- 모델: `qwen2.5vl:3b`
- 샘플링 간격: 10초
- 리포트 포함 기준: `중간` 이상
- 산출물: `output/analysis.../report.html`, `report.md`, `observations.json`, `events.json`, `captures/`

간격을 바꾸려면:

```powershell
$env:KORAIL_INTERVAL_SEC=5
.\scripts\analyze_root_videos.cmd
```

루트의 샘플 영상은 테스트 데이터로 `tests/data/videos/`에 둡니다. 영상 파일은 대용량이라 git에는 포함하지 않습니다.

## GitHub Release 설치

릴리즈 페이지에서 설치 스크립트 하나만 내려받아 실행할 수 있습니다.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

macOS:

```sh
sh install_macos.sh
```

릴리즈 설치 스크립트는 최신 릴리즈 소스를 내려받고, 앱 설치, FFmpeg/Ollama 준비, `qwen2.5vl:3b` 모델 설치를 순서대로 진행합니다.

## Windows 설치 마법사 빌드

Windows 납품용 실행파일과 설치 마법사는 PyInstaller + Inno Setup으로 생성합니다.

```powershell
.\scripts\package_windows.cmd
```

산출물:

- `dist/KorailAnalyzer/KorailAnalyzer.exe`
- `dist/installer/KorailAnalyzerSetup-<version>.exe`

설치 마법사에는 Ollama standalone runtime과 FFmpeg/FFprobe가 포함됩니다. 사용자는 별도 Python/Ollama/FFmpeg 설치 없이 설치 마법사만 실행하면 되고, 앱의 `모델 설치` 버튼으로 `qwen2.5vl:3b` 모델 다운로드를 진행합니다. 역명 OCR도 기본값으로 같은 로컬 VLM을 사용하므로 별도 OCR 패키지 설치가 필요 없습니다.

자세한 내용은 [패키징 문서](./docs/packaging.md)를 참고하세요.

## 문서

- [문서 인덱스](./docs/README.md)
- [프로젝트 결정 사항](./docs/decisions.md)
- [사용자 플로우](./docs/user-flow.md)
- [분석 파이프라인 설계](./docs/pipeline-design.md)
- [개발 환경 및 배포 방향](./docs/dev-env-and-packaging.md)

## 구현 상태

- GUI 대기열, 영상별 분석 로그, 이벤트 카드, 상세 패널
- 앱 내 Qwen2.5-VL 모델 설치
- FFmpeg 간격 샘플링
- 로컬 VLM 프레임 judge
- 로컬 VLM 역명 OCR 및 구간 매핑
- HTML/Markdown 리포트와 캡처 이미지 생성
