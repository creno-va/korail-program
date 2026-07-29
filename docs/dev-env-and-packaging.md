# 개발 환경 및 배포 방향

## Python 런타임

기본 런타임은 CPython이다.

권장:

- Python 3.11 또는 3.12
- 64-bit
- Windows 11 기준 개발 및 테스트

PyPy는 사용하지 않는다.

이유:

- PyPy는 패키지 매니저가 아니라 Python 구현체다.
- PyTorch, PaddleOCR/PaddlePaddle, OpenCV, PySide6, CUDA 의존성은 CPython 호환성이 가장 중요하다.
- 납품 프로그램에서는 JIT 성능보다 네이티브 확장 호환성과 패키징 안정성이 더 중요하다.

## 패키지 관리

권장: uv

초기 명령 예시:

```powershell
uv init
uv add pyside6 opencv-python pydantic sqlalchemy openpyxl reportlab
uv add --dev pytest ruff mypy
```

주의:

- PyTorch CUDA wheel은 대상 PC의 CUDA/드라이버 기준으로 별도 설치 스크립트를 둔다.
- PaddleOCR/PaddlePaddle도 GPU/CPU 환경에 따라 설치 명령을 분리한다.
- Gemma 모델 파일은 pip dependency로 넣지 않고 별도 모델 디렉터리로 관리한다.

## 예상 프로젝트 구조

```text
korail-program/
  pyproject.toml
  uv.lock
  README.md
  docs/
  src/
    korail_program/
      app/
        main_window.py
        widgets/
      core/
        video_probe.py
        frame_extractor.py
        event_merger.py
      ocr/
        paddle_ocr_engine.py
        station_matcher.py
      judge/
        gemma_client.py
        prompts.py
        response_schema.py
      db/
        models.py
        repository.py
      reports/
        pdf_report.py
        excel_report.py
      workers/
        analysis_worker.py
      config/
        settings.py
  tests/
  assets/
    ffmpeg/
    models/
    report_templates/
```

## 로컬 모델 실행 방식

초기 후보:

```text
PySide6 앱
 -> localhost 모델 서버 호출
 -> Gemma 4 12B 응답
```

모델 서버 후보:

- llama.cpp server
- Ollama
- vLLM

초기 PoC에서는 설치와 API 호출이 쉬운 방식을 우선한다. 납품 단계에서는 모델 파일, 실행 바이너리, 설정 파일을 함께 패키징한다.

## GUI 설계 기준

프레임워크:

- PySide6
- Qt Widgets

필수 화면:

- 영상 대기열
- 분석 진행률/로그
- 결과 목록
- 이벤트 상세 보기
- 캡처 뷰어
- 설정 화면
- 이력 조회
- 리포트 내보내기

백그라운드 작업:

- UI thread에서는 무거운 작업 금지
- 분석 작업은 QThread 또는 QProcess로 분리
- FFmpeg, OCR, Judge 호출은 취소 가능한 작업 단위로 관리

## Windows 패키징

초기 납품 방식:

- PyInstaller one-folder
- Inno Setup 또는 NSIS 설치 프로그램

one-folder를 우선하는 이유:

- 모델 파일과 FFmpeg 포함이 쉬움
- 대용량 CUDA/OCR 의존성 문제를 추적하기 쉬움
- one-file보다 첫 실행 지연이 적음

포함 산출물:

- app executable
- Python runtime dependency bundle
- FFmpeg binary
- OCR model files
- Gemma model files 또는 모델 서버 실행 파일
- 기본 설정 파일
- 역명 사전
- 리포트 템플릿
- 라이선스 고지

## 설치 후 디렉터리 예시

```text
C:\Program Files\Korail Obstruction Analyzer\
  KorailAnalyzer.exe
  runtime\
  bin\
    ffmpeg.exe
  models\
    gemma4\
    paddleocr\
  templates\
  licenses\

C:\ProgramData\Korail Obstruction Analyzer\
  config\
  db\
  captures\
  reports\
  logs\
```

## 오프라인 요구사항

원칙:

- 분석 중 외부 통신 금지
- 모델 다운로드는 설치/납품 전 완료
- 실행 중 자동 업데이트 없음
- 로그에 원본 영상 경로는 저장하되 원본 영상 복사는 하지 않음
- 캡처, 리포트, DB만 산출물로 저장

## 개발 단계

### 1단계: 콘솔 PoC

- 영상 1개 입력
- FFmpeg 프레임 추출
- PaddleOCR ROI 판독
- Gemma judge JSON 출력
- CSV/JSON 결과 저장

### 2단계: 데스크톱 MVP

- PySide6 영상 대기열
- 분석 시작/중지
- 진행률 표시
- 결과 목록
- 캡처 뷰어
- SQLite 저장

### 3단계: 리포트/검수

- PDF/Excel 리포트
- 수동 검수 상태
- 이벤트 수정
- 이력 조회

### 4단계: 납품 패키징

- 설치 프로그램
- 모델/FFmpeg 포함
- 오프라인 실행 검증
- 샘플 영상 기준 성능 리포트
