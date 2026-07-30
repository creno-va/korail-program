# 개발 환경 및 배포 방향

## Python 기준

기본 런타임은 CPython입니다.

권장:

- Python 3.11 또는 3.12
- 64-bit 런타임
- Windows 11 기준 검수
- macOS 개발 실행 지원

PyPy는 사용하지 않습니다.

이유:

- PySide6, OpenCV, PaddleOCR/PaddlePaddle, PyTorch 계열 패키지 호환성은 CPython이 가장 안정적입니다.
- 납품 프로그램은 JIT 성능보다 패키징 안정성, 드라이버 호환성, 장애 추적 가능성이 더 중요합니다.

## 설치 및 실행

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\run_gui.cmd
.\scripts\test.cmd
```

### macOS

```sh
python3 --version
sh scripts/bootstrap.sh
sh scripts/run_gui.sh
sh scripts/test.sh
```

macOS에서 `python3`가 3.11 미만이면 Homebrew 또는 pyenv로 Python 3.11 이상을 설치합니다.

## 스크립트 구성

| 파일 | 플랫폼 | 역할 |
| --- | --- | --- |
| `scripts/run_gui.cmd` | Windows | GUI 실행 |
| `scripts/run_gui.ps1` | Windows | PowerShell GUI 실행 |
| `scripts/test.cmd` | Windows | unittest 실행 |
| `scripts/test.ps1` | Windows | PowerShell 테스트 실행 |
| `scripts/bootstrap.sh` | macOS/Linux | `.venv` 생성 및 editable install |
| `scripts/run_gui.sh` | macOS/Linux | GUI 실행 |
| `scripts/test.sh` | macOS/Linux | unittest 실행 |
| `scripts/install_windows.ps1` | Windows | Python 앱 설치, FFmpeg/Ollama 설치 시도, Gemma 모델 pull |
| `scripts/install_macos.sh` | macOS | Python 앱 설치, FFmpeg/Ollama 설치 시도, Gemma 모델 pull |
| `scripts/analyze_root_videos.cmd` | Windows | 루트 영상 배치 분석 |
| `scripts/analyze_root_videos.ps1` | Windows | PowerShell 루트 영상 배치 분석 |
| `scripts/analyze_root_videos.sh` | macOS/Linux | 루트 영상 배치 분석 |

## 현재 프로젝트 구조

```text
korail-program/
  pyproject.toml
  README.md
  docs/
  scripts/
  src/
    korail_program/
      app/
        main.py
        main_window.py
        widgets.py
        theme.py
        fonts.py
        icons.py
      core/
      db/
      judge/
      ocr/
  tests/
```

## 로컬 모델 실행 방식

초기 구조:

```text
PySide6 GUI
  -> analysis worker
  -> FFmpeg/OpenCV frame extraction
  -> Gemma multimodal judge
  -> PaddleOCR station OCR
  -> SQLite/report outputs
```

현재 구현된 배치 분석 경로:

```text
korail-analyzer analyze-videos
  -> 루트 또는 지정 경로 영상 검색
  -> FFmpeg로 N초 간격 프레임 추출
  -> Ollama Gemma VLM에 이미지 VQA 요청
  -> JSON schema 검증
  -> 의심 프레임 captures/ 복사
  -> HTML/Markdown/JSON 리포트 생성
```

기본 모델은 `gemma4:12b`입니다. 설치 스크립트와 앱 내 모델 설치 버튼은 모두 이 모델을 기준으로 동작합니다.

GitHub Release용 standalone 설치 자산:

- `release/install_windows.ps1`
- `release/install_macos.sh`

이 두 파일은 repo를 미리 clone하지 않아도 최신 릴리즈 소스를 다운로드한 뒤 앱 설치와 `gemma4:12b` 모델 pull까지 수행합니다.

모델 서버 후보:

- llama.cpp server
- Ollama
- vLLM

초기 PoC에서는 설치와 API 호출이 쉬운 방식을 우선합니다. 납품 단계에서는 모델 파일, 실행 바이너리, 설정 파일을 설치 패키지에 함께 묶습니다.

## Windows 패키징

초기 납품 방식:

- PyInstaller one-folder
- Inno Setup 또는 NSIS 설치 프로그램

one-folder를 우선하는 이유:

- 대용량 모델과 FFmpeg 포함이 쉽습니다.
- CUDA/OCR 의존성 문제를 추적하기 쉽습니다.
- one-file보다 첫 실행 지연이 작습니다.

포함 산출물:

- 앱 실행 파일
- Python runtime dependency bundle
- FFmpeg binary
- OCR model files
- Gemma model files 또는 로컬 모델 서버 실행 파일
- 기본 설정 파일
- 역명 사전
- 리포트 템플릿
- 라이선스 고지

## macOS 실행 범위

현재 macOS 지원은 개발 및 데모 실행 범위입니다.

- `sh scripts/bootstrap.sh`로 동일 소스 설치
- `sh scripts/run_gui.sh`로 PySide6 GUI 실행
- macOS notarization, `.dmg`, `.app` 배포는 아직 범위 밖

필요 시 이후 단계에서 PyInstaller `.app` 빌드와 notarization 절차를 별도 문서로 분리합니다.

## 오프라인 요구사항

원칙:

- 분석 중 외부 통신 금지
- 모델 다운로드는 설치 또는 납품 전에 완료
- 실행 중 자동 업데이트 없음
- 로그에는 원본 영상 경로만 저장하고 원본 영상 복사는 하지 않음
- 캡처, 리포트, DB만 산출물로 저장

## 개발 단계

### 1단계: 콘솔 PoC

- 영상 1개 입력
- FFmpeg 프레임 추출
- PaddleOCR ROI 추론
- Gemma judge JSON 출력
- CSV/JSON 결과 저장

### 2단계: 데스크톱 MVP

- PySide6 영상 대기열
- 분석 시작/중지
- 파일별 진행 로그
- 결과 목록
- 캡처 뷰어
- SQLite 저장

### 3단계: 리포트 및 검수

- PDF/Excel 리포트
- 수동 검수 상태
- 이벤트 수정
- 이력 조회

### 4단계: 납품 패키지

- 설치 프로그램
- 모델/FFmpeg 포함
- 오프라인 실행 검증
- 샘플 영상 기준 성능 리포트
