# Korail 지장수목 분석 프로그램

전방 주행 영상에서 전차선로 주변 지장수목, 특히 대나무 의심 구간을 자동 분석하고 캡처와 리포트로 정리하는 Windows 오프라인 프로그램입니다.

## 초기 개발 방향

- Python CPython 기반
- GUI는 PySide6(Qt Widgets)
- 패키지/환경 관리는 uv 우선 검토, 현재 로컬 설치는 `.venv` + pip editable install
- YOLO 학습 없이 Gemma 4 12B Unified 로컬 멀티모달 LLM으로 프레임 VQA judge 수행
- 역명/위치 판독은 PaddleOCR + 역명 사전 보정으로 분리
- 분석 결과는 SQLite, 캡처 이미지, PDF/Excel 리포트로 저장

## 실행

현재 레포에는 `.venv`가 구성되어 있고 앱이 editable install 되어 있습니다.

GUI 실행:

```powershell
.\scripts\run_gui.cmd
```

직접 실행:

```powershell
.\.venv\Scripts\korail-analyzer-gui.exe
```

테스트:

```powershell
.\scripts\test.cmd
```

PowerShell 스크립트를 선호하는 경우 실행 정책에 따라 다음처럼 실행할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui.ps1
```

처음부터 다시 설치해야 하는 경우:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## 문서

- [문서 인덱스](./docs/README.md)
- [프로젝트 결정 사항](./docs/decisions.md)
- [사용자 플로우](./docs/user-flow.md)
- [분석 파이프라인 설계](./docs/pipeline-design.md)
- [개발 환경 및 배포 방향](./docs/dev-env-and-packaging.md)

## 다음 작업 후보

1. 샘플 영상 기준 OCR ROI 확정
2. Gemma judge 프롬프트와 JSON schema 작성
3. 콘솔 PoC 구조 생성
4. PySide6 화면 와이어프레임 작성
5. SQLite 스키마 초안 작성
