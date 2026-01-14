# LS PLC WinError 10054 (원격 연결 끊김) 원인 분석 및 대응 가이드

## 1. 개요

- **증상**: LS PLC와 통신 중 간헐적으로
  `[WinError 10054] 현재 연결은 원격 호스트에 의해 강제로 끊겼습니다` 에러 발생.
- **영향**: 통신이 일시적으로 단절되나, `RealPLCDriver`의 자동 재연결 로직에
  의해 즉시 복구됨. (Downtime: 1~7초 내외)

## 2. 발생 원인 분석 (Root Cause Analysis)

`10054` 에러(Connection Reset by Peer)는 내 컴퓨터(Client)가 아니라
**상대방(PLC)이 연결을 끊었을 때** 발생합니다.

### 2.1 가설 1: PLC 측의 유휴 타임아웃 (Idle Timeout) [유력]

- **상황**: Backend 프로그램이 다른 무거운 작업(예: DB 저장, SPOT 카메라 연결
  시도 등)으로 인해 잠시 멈췄을 때 발생할 수 있습니다.
- **설명**: PLC는 보통 "일정 시간(예: 3초) 동안 패킷이 없으면 연결을 끊는다"는
  보호 설정이 있습니다. Backend가 0.2초마다 요청을 보내다가 순간적으로 3초 이상
  멈추면, PLC는 소켓을 닫아버립니다. 그 직후 Backend가 다시 패킷을 보내면 PLC는
  "난 이미 닫았는데?"라며 `RST` 패킷을 보내고, 이것이 `10054` 에러가 됩니다.
- **근거**: `observability_snapshot`을 보면 `SPOT` 타임아웃 오류(timed out)
  직후에 `LS PLC` 오류가 발생하는 경향이 있는지 확인해 볼 필요가 있습니다.
  (하나의 스레드가 블로킹되어 전체 루프가 지연됨)

### 2.2 가설 2: 동시 접속자 수 초과 (Connection Limit)

- **상황**: 엔지니어링 툴(XG5000), HMI, 또는 다른 수집기가 동시에 접속을 시도할
  때.
- **설명**: LS PLC(XGT 모듈)는 TCP 접속 허용 개수가 제한적(보통 4~16개)입니다.
  허용 범위를 넘어서면 기존 접속을 끊어버릴 수 있습니다.

### 2.3 가설 3: 물리적 네트워크 불안정

- **상황**: 랜 케이블 노후화, 스위칭 허브의 전원 불안정.
- **설명**: 물리적 링크가 잠깐 끊어지면 TCP 연결이 리셋됩니다.

## 3. 검증을 위한 로그 수집 계획 (Action Plan)

정확한 원인을 파악하기 위해 다음 정보가 필요합니다.

### 3.1 Python 정밀 로그 (Loop Latency Log)

- **목적**: 에러 발생 직전에 우리 프로그램이 "멍 때리고(Blocking)" 있었는지
  확인.
- **방법**: 메인 루프(`server_entry.py` 또는 `real_driver.py`)에 루프 소요
  시간(Loop Duration)을 기록.
- **코드 예시**:
  ```python
  # pseudo code
  start = time.time()
  read_data()
  duration = time.time() - start
  if duration > 1.0:
      logger.warning(f"Loop blocked for {duration:.2f}s!")
  ```

### 3.2 Wireshark 패킷 캡처 (Network Level)

- **목적**: 누가 먼저 끊었는지(RST 패킷의 주체) 확인.
- **방법**:
  1. 서버 PC에 Wireshark 설치.
  2. 필터: `ip.addr == 192.168.10.220 && tcp`
  3. 에러 발생 시점의 패킷 분석. PLC 쪽에서 `RST, ACK`가 먼저 오는지 확인.

## 4. 즉시 적용 가능한 튜닝 (Recommendations)

로그 수집 전이라도 시도해 볼 수 있는 조치는 다음과 같습니다.

1. **SPOT 타임아웃 줄이기**: 현재 `DRIVER_TIMEOUT=0.5s`이지만, `config.py`의
   `SPOT_TIMEOUT`도 확인하여, SPOT 연결 지연이 LS PLC 통신 주기를 방해하지
   않도록 해야 합니다. (`real_driver.py`에서 `_spot_http_client` 타임아웃 확인)
2. **재연결 백오프 완화**: 현재 에러 발생 시 재연결이 빠르게 이루어지고
   있으므로, 현재의 자동 복구 로직(`_backoff_ls`)은 적절합니다.

---

**작성일**: 2026-01-14 **작성자**: Antigravity AI
