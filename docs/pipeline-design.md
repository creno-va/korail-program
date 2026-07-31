# 분석 파이프라인 설계

## 개요

```text
영상 파일
 -> 프레임 샘플링
 -> [A] GPT OCR 파이프라인
 -> [B] GPT VQA Judge 파이프라인
 -> 타임코드 기준 병합
 -> 이벤트 생성
 -> 캡처/JSON/HTML 리포트 생성
```

분리 원칙:

- OCR은 역명, 노선, 위치 텍스트 판독만 담당한다.
- Judge는 전차선로 주변 지장수목/대나무 위험 후보 판정만 담당한다.
- 두 결과는 타임코드 기준으로만 병합한다.
- OCR 실패가 전체 분석 실패로 번지지 않게 한다.
- GPT API 호출 실패가 반복되면 분석을 중단하고 리포트에 원인을 남긴다.

## A. GPT OCR 파이프라인

목적:

- 영상 프레임 안의 역명, 노선, 위치 텍스트를 판독한다.
- 선택적 역명 사전과 fuzzy matching으로 표기를 보정한다.

입력:

- 샘플 프레임
- OCR 샘플링 간격
- 노선/역명 힌트
- 선택적 역명 사전

처리:

1. OCR 대상 프레임 추출
2. GPT vision OCR 프롬프트 호출
3. JSON 응답 검증
4. 역명 사전 fuzzy matching
5. 타임코드별 역명/구간 후보 생성

출력 예시:

```json
{
  "video_id": 1,
  "video_time_ms": 754000,
  "raw_text": "못골역",
  "station_name": "못골역",
  "confidence": 0.93,
  "method": "gpt-vlm-ocr"
}
```

## B. GPT VQA Judge 파이프라인

목적:

- 프레임에서 전차선로 주변 지장수목 또는 대나무 위험 후보를 판정한다.
- 위험도, 근접 여부, 근거 문장, 검수 필요 여부를 구조화한다.

기본 모델:

- `gpt-5.6-terra`

선택 모델:

- `gpt-5.6-sol`
- `gpt-5.6-luna`
- `gpt-4.1-mini`

처리:

1. Judge 대상 프레임 추출
2. 프레임 크기 제한 적용
3. OpenAI Responses API에 `input_text` + `input_image` 호출
4. JSON 응답 파싱 및 검증
5. 위험도 기준 이상 프레임을 capture로 복사
6. 연속 의심 프레임을 하나의 이벤트로 병합

Judge 출력 예시:

```json
{
  "has_tree": true,
  "bamboo_likely": 0.78,
  "near_catenary": true,
  "risk_level": "high",
  "bbox_hint": [920, 180, 1240, 620],
  "evidence": "오른쪽 전차선로 주변 수목이 급전선 방향으로 근접해 보임",
  "needs_human_review": false
}
```

## 리포트 생성

리포트에는 다음을 포함한다.

- 분석 대상 영상 수
- 샘플링 프레임 수
- OCR 관측 수
- 의심 캡처 수
- 병합 이벤트 수
- 처리 실패 원인
- 이벤트별 타임코드, 위험도, 근거, 캡처 이미지
