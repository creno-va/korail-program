# Korail 지장수목 분석 프로그램

철도 주행 영상을 샘플링해 전차선로 주변 지장수목 후보와 역명 표지를 로컬 비전 모델로 판정하고, 검수용 캡처와 PDF 리포트를 만드는 PySide6 데스크톱 앱입니다.

Windows/macOS 설치본에는 Python 실행 파일, FFmpeg/FFprobe, Ollama 런타임이 포함됩니다. OpenAI API 키나 별도 Ollama 설치는 필요하지 않습니다. AI 모델 파일은 설치본에 넣지 않고 앱의 `로컬 AI 모델` 모달에서 사용자가 선택해 내려받습니다.

## 로컬 모델

앱은 PC의 OS, CPU, RAM, GPU/VRAM, 모델 저장 여유 공간을 표시하고 실행 가능한 추천 모델을 목록 최상단에 배치합니다.

| 모델 | 용량 | 용도 |
|---|---:|---|
| `qwen3-vl:2b` | 약 1.9GB | 저사양·빠른 1차 판정 |
| `qwen3-vl:4b` | 약 3.3GB | 기본 균형, 한국어 OCR |
| `qwen3-vl:8b` | 약 6.1GB | GPU 기반 정밀 판정 |
| `gemma4:e2b` | 약 7.2GB | Gemma 4 경량 옵션 |
| `gemma4:e4b` | 약 9.6GB | Gemma 4 균형 옵션 |
| `gemma4:12b` | 약 7.6GB | 워크스테이션 정밀 옵션 |

다운로드 모델은 사용자 데이터의 `KorailAnalyzer/ollama/models`에 보관되므로 앱 업데이트 후에도 유지됩니다. 앱 전용 Ollama 서버는 `127.0.0.1:11435`를 사용하고 클라우드 모델 호출은 비활성화합니다.

Qwen과 Gemma 4에는 각각 별도의 프롬프트·샘플링 하네스가 적용됩니다. 두 하네스 모두 이미지 입력과 JSON Schema 출력으로 VQA 판정과 역명 OCR을 분리 실행합니다.

## 개발 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,packaging]"
.\.venv\Scripts\korail-analyzer-gui.exe
```

소스 실행에서는 시스템 Ollama를 사용할 수 있습니다. 앱과 같은 포트·모델 폴더를 쓰려면 다음 환경을 설정하고 서버를 실행합니다.

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\KorailAnalyzer\ollama\models"
ollama serve
```

CLI 예시:

```powershell
.\.venv\Scripts\korail-analyzer.exe analyze-videos . `
  --out output\analysis `
  --model qwen3-vl:4b `
  --ollama-url http://127.0.0.1:11435 `
  --interval-sec 15 `
  --min-report-risk low
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

## 설치 마법사 빌드

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_windows.ps1
```

macOS:

```sh
sh scripts/package_macos.sh
```

패키징 스크립트는 공식 Ollama 릴리즈와 FFmpeg를 준비하고 앱의 `runtime/` 아래에 복사합니다. Windows 빌드는 `ollama.exe`뿐 아니라 `lib/ollama` runner DLL과 `llama-server.exe`가 모두 있는지 검증합니다.

상세 설계는 [docs/README.md](docs/README.md)를 참고하세요.
