# 개발 환경 및 배포 방향

## 기본 환경

- Python: CPython 3.11+
- GUI: PySide6
- 영상 처리: FFmpeg/FFprobe
- VQA/OCR: OpenAI GPT API
- 패키징: PyInstaller, Inno Setup, macOS pkg/dmg

## 개발 설치

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\run_gui.cmd
```

macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
sh scripts/run_gui.sh
```

## Secret 설정

분석에는 `OPENAI_API_KEY`가 필요하다.

허용 경로:

- OS 사용자 환경변수
- `.env` 또는 `.env.local`
- 앱의 `API 설정` 창

Windows helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_openai_key.ps1 -ApiKey "sk-..."
```

macOS helper:

```sh
sh scripts/set_openai_key.sh "sk-..."
```

## 파이프라인 실행 방식

```text
PySide6 GUI / CLI
 -> FFmpeg frame sampling
 -> OpenAI Responses API frame judge
 -> OpenAI Responses API station OCR
 -> event merge
 -> HTML/Markdown/JSON report
```

기본 모델은 `gpt-5.6-terra`다. 환경변수 또는 CLI의 `--model` 옵션으로 바꿀 수 있다.

## 배포 포함/제외

포함:

- PyInstaller 앱
- PySide6/Qt runtime
- FFmpeg/FFprobe
- Pretendard GOV fonts

제외:

- Ollama
- 로컬 VLM 모델 파일
- llama-server

## 릴리즈 빌드

Windows:

```powershell
.\scripts\package_windows.cmd
```

macOS:

```sh
sh scripts/package_macos.sh
```

GitHub Actions:

- `Build macOS installer` workflow
- `tag` 입력값으로 릴리즈 태그 지정
- `upload_to_release=true`일 때 생성된 pkg/dmg를 릴리즈 asset으로 업로드
