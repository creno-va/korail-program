# 분석 파이프라인 설계

## 개요

분석은 두 개의 독립 파이프라인으로 나눈다.

```text
영상 파일
 -> 프레임 추출
 -> [A] OCR 파이프라인
 -> [B] Gemma Judge 파이프라인
 -> 타임코드 기준 병합
 -> 이벤트 생성
 -> 캡처/DB/리포트
```

분리 원칙:

- OCR은 위치/역명 판독만 담당한다.
- Gemma judge는 지장수목/대나무 위험 판정만 담당한다.
- 두 결과는 타임코드로만 병합한다.
- 한쪽 실패가 전체 분석 실패로 번지지 않도록 한다.
- 기본 설치판은 같은 `gemma4:12b` 로컬 모델을 서로 다른 프롬프트로 호출해 judge와 OCR을 분리한다.
- PaddleOCR은 Python 네이티브 의존성이 있는 선택형 고속 OCR 백엔드로만 둔다.

## A. OCR 파이프라인

목적:

- 영상 화면의 운행 위치/역명 오버레이를 읽는다.
- 타임코드별 역명 또는 구간 매핑 테이블을 만든다.

입력:

- 원본 영상
- OCR 샘플링 fps
- 위치 표시부 ROI
- 노선별 역명 사전

처리 단계:

```text
1. OCR 대상 프레임 추출
2. 위치 표시부 ROI crop
3. 이미지 전처리
4. 기본 VLM OCR 실행
5. 역명 사전 fuzzy matching
6. 전후 프레임 기반 보간
7. 타임코드-역명/구간 테이블 생성
```

전처리 후보:

- grayscale
- contrast enhancement
- threshold
- denoise
- 2x 또는 3x resize

OCR 관측값 예시:

```json
{
  "video_id": 1,
  "video_time_ms": 754000,
  "raw_text": "몽탄역",
  "station_name": "몽탄역",
  "confidence": 0.93,
  "roi": [20, 680, 420, 760],
  "method": "vlm-ocr"
}
```

보정 규칙:

- 역명 사전에 없는 텍스트는 fuzzy match 후보로 둔다.
- confidence가 낮으면 이전/다음 안정 인식값으로 보간한다.
- 일정 시간 이상 역명이 유지되면 안정 상태로 본다.
- 역명 변화 지점은 구간 경계 후보로 기록한다.

출력:

```json
{
  "video_id": 1,
  "start_time_ms": 720000,
  "end_time_ms": 850000,
  "section_start": "일로역",
  "section_end": "몽탄역",
  "confidence": 0.88
}
```

## B. Gemma Judge 파이프라인

목적:

- 프레임에서 전차선로 주변 지장수목/대나무 의심 상황을 판정한다.
- 위험도와 판단 근거를 구조화한다.

모델:

- Gemma 4 12B Unified Q4
- 로컬 실행
- 외부 통신 없음

입력:

- 원본 프레임
- 필요 시 전차선로 중심 ROI crop
- 고정 judge prompt

처리 단계:

```text
1. Judge 대상 프레임 추출
2. 프레임 품질 검사
3. 원본 프레임 또는 ROI 생성
4. Gemma 4 VQA 호출
5. JSON 응답 검증
6. 실패 응답 재시도
7. 연속 프레임 이벤트 병합
```

Judge prompt 요구사항:

- 반드시 JSON만 출력
- 위험도는 "상", "중", "하", "없음" 중 하나
- 판단 근거는 한 문장
- 불확실하면 needs_human_review를 true로 설정
- 전차선로 근접 여부를 별도 필드로 출력

Judge 출력 예시:

```json
{
  "video_id": 1,
  "video_time_ms": 754000,
  "has_tree": true,
  "bamboo_likely": 0.78,
  "near_catenary": true,
  "risk_level": "상",
  "bbox_hint": [920, 180, 1240, 620],
  "evidence": "우측 전차선로 주변에 대나무형 수목 군락이 근접해 보임",
  "needs_human_review": false
}
```

위험도 초안:

- 상: 수목이 전차선로와 겹치거나 매우 근접해 침범 가능성이 큼
- 중: 수목이 전차선로 주변 경고 범위에 접근함
- 하: 수목이 보이나 전차선로와 거리가 있음
- 없음: 지장수목 의심 없음

후처리:

- 같은 위험도가 연속으로 감지되면 하나의 이벤트로 병합
- 짧은 단발 탐지는 needs_human_review로 둔다.
- 이벤트 대표 프레임은 시작/중간/끝에서 선정

## 병합 파이프라인

입력:

- OCR 구간 테이블
- Judge 관측값 또는 이벤트 후보

처리:

```text
1. Judge 이벤트의 start_time_ms/end_time_ms 계산
2. OCR 구간 테이블에서 해당 시간대 구간 조회
3. 가장 많이 겹치는 구간을 대표 구간으로 선택
4. 구간 경계에 걸치면 시작 구간과 끝 구간을 함께 기록
5. 최종 이벤트 저장
```

최종 이벤트 예시:

```json
{
  "video_id": 1,
  "start_time_ms": 754000,
  "end_time_ms": 782000,
  "section_start": "일로역",
  "section_end": "몽탄역",
  "risk_level": "상",
  "summary": "대나무형 수목 군락이 우측 전차선로 주변에 근접해 보임",
  "capture_count": 4,
  "review_status": "미확인"
}
```

## 처리 성능 전략

초기 기본값:

- OCR: 30초 간격 기본 샘플링
- Judge: 10초 간격 기본 샘플링
- 이벤트 병합 최소 길이: 2초
- 대표 캡처: 이벤트당 3장

장시간 영상 최적화:

- 빠른 모드: Judge 20초 간격
- 정밀 모드: Judge 5초 간격
- ROI crop을 활용해 입력 이미지 크기 축소
- 모델 서버는 프로세스 재사용
- 프레임 파일은 분석 후 필요한 캡처만 보존

## 검증 지표

초기 PoC에서 가장 중요한 지표:

- false negative: 실제 위험 구간을 놓친 비율
- false positive: 오탐 비율
- OCR station accuracy: 역명 인식 정확도
- event merge quality: 같은 사건이 여러 건으로 쪼개지는 정도
- processing speed: 영상 1시간당 처리 시간

## 실패 처리

OCR 실패:

- 구간 미확인으로 저장
- 보간 시도
- 수동 구간 입력 허용

Judge 실패:

- 재시도
- 반복 실패 시 판정 실패로 저장
- 분석 전체는 계속 진행

모델 서버 실패:

- 분석 시작 전 health check
- 분석 중 실패 시 현재 파일 중단 후 대기열 유지
