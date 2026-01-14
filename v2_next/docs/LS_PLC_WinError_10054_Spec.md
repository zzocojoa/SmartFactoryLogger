# LS PLC WinError 10054 디버깅 명세서 (Specification)

## 1. 개요 (Overview)

본 명세서는 LS PLC에서 발생하는 `[WinError 10054]` (Connection Reset by Peer)
에러의 원인 규명을 위한 **정밀 로깅 및 모니터링 기능** 구현 요구사항을
정의합니다. 심층 분석(Deep Dive) 결과, **메인 루프의 Blocking으로 인한 LS PLC
유휴 타임아웃(Idle Timeout)**이 가장 유력한 원인으로 지목되었습니다.

## 2. 요구사항 (Requirements)

### 2.1 기능적 요구사항

1. **루프 지연(Loop Latency) 감지**:
   - 메인 데이터 수집 루프(`server_entry.py` 또는 `real_driver.py`)가 한 번
     실행되는 데 걸리는 시간을 측정해야 한다.
   - 설정된 임계값(예: 1.0초)을 초과하는 경우, 경고(WARNING) 로그를 남겨야 한다.
   - 로그 내용에는 **소요 시간**과 **지연이 발생한 시점**이 포함되어야 한다.
2. **SPOT 연결 시간 측정**:
   - `SPOT` 카메라 통신(`_read_spot`)이 오래 걸리는지 별도로 측정하여, 0.5초
     이상 소요 시 경고 로그를 남겨야 한다.
3. **로그 파일 분리 (옵션)**:
   - 디버깅 로그가 기존 로그와 섞여 가독성을 해치지 않도록, 필요하다면
     태그(`[LATENCY]`)를 명확히 달거나 별도 파일로 관리를 고려한다. (현재는
     태그로 충분)

### 2.2 비기능적 요구사항

1. **성능 영향 최소화**: 시간 측정 로직 (`time.time()`) 추가가 시스템 성능에
   영향을 주어서는 안 된다.
2. **운영 환경 안전성**: 로깅 중 예외가 발생하더라도 메인 루프는 멈추지 않아야
   한다.

## 3. 아키텍처 (Architecture)

### 3.1 변경 대상 컴포넌트

- `backend/services/real_driver.py`:
  - `read_data()` 메서드 내부에 타이머를 추가하여 각 단계(Extruder, LS, SPOT)별
    소요 시간을 측정한다.
- `backend/services/plc_service.py` (또는 `server_entry.py`):
  - `read_data()` 호출 전체의 주기를 모니터링한다.

### 3.2 로깅 포맷 (Proposed Log Format)

```text
[WARNING] [Latency] Main loop took 1.25s (Threshold: 1.0s). Breakdown:
  - Extruder: 0.01s
  - LS PLC: 0.01s
  - SPOT: 1.20s (!!!)
  - Processing: 0.03s
```

## 4. 데이터 모델 (Data Model)

- DB 스키마 변경 없음.
- 로그 파일(`logs/system/system.log`)에 텍스트 데이터만 추가됨.

## 5. 테스트 전략 (Test Strategy)

1. **지연 시뮬레이션 (Mock Test)**
   - `read_data()` 내부에 `time.sleep(1.5)`를 강제로 넣어, Latency Warning
     로그가 남는지 확인한다.
2. **실환경 모니터링 (Production Monitor)**
   - 배포 후 실제 운영 환경에서 `logs/system/system.log`를 관측하여,
     `[WinError 10054]` 발생 직전에 Latency Warning이 있는지 상관관계를
     분석한다.

---

**작성일**: 2026-01-14 **작성자**: Antigravity AI
