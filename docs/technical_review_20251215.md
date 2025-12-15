# 스마트 팩토리 로거 (SmartFactoryLogger) 기술 및 실무 분석 보고서

**작성일**: 2025-12-15\
**작성자**: Antigravity (AI Intelligent Assistant)

## 1. 총평 (Executive Summary)

본 프로젝트는 **알루미늄 압출 공정의 디지털 화(Digitalization)**를 위한 핵심
미들웨어로, 현장의 이종 설비(PLC, 압출기, 온도 센서) 데이터를 통합하여 **데이터
자산화**를 수행하는 우수한 실무 프로젝트입니다.

단순한 데이터 수집을 넘어, **생산 로직(Die/Cycle 감지)**을 소프트웨어 레벨에서
처리하고, 현장 작업자를 위한 **실시간 시각화(GUI)** 및 **안정성(Crash Dump,
State Recovery)**까지 고려된 "준 상용화(Production-grade)" 수준의 아키텍처를
갖추고 있습니다.

---

## 2. 아키텍처 및 코드 품질 분석 (Technical Analysis)

### 2.1 아키텍처 (Architecture)

- **Producer-Consumer 패턴 적용**: 데이터 수집(Producer)과 저장/표시(Consumer)가
  `Queue`를 통해 완벽히 분리되어 있어, UI가 멈추더라도 데이터 수집은 끊기지 않는
  구조입니다.
- **병렬 IO 처리**: `ThreadPoolExecutor`를 사용하여 3개의 이종 장비(LS PLC,
  Extruder, Spot)와 동시에 통신함으로써, **0.2초(200ms)라는 빠른 수집 주기**를
  안정적으로 보장합니다. 단일 스레드로 순차 호출했다면 달성하기 어려운
  성능입니다.

### 2.2 안정성 및 예외 처리 (Reliability)

- **Global Exception Hook**: `sys.excepthook`을 오버라이딩하여 프로그램 크래시
  시 `crash.log`를 남기도록 설계되었습니다. 현장에서 원인을 알 수 없이 꺼지는
  문제를 추적할 수 있는 매우 실무적인 기능입니다.
- **State Persistence**: `modules/logic_processor.py`에서 `state.json`을 통해
  프로그램 재시작 시에도 이전 작업(Die ID, Counter)을 기억하고 복구합니다. 이는
  정전이나 윈도우 업데이트 등으로 인한 재부팅 상황에서 **데이터 연속성**을
  보장합니다.

### 2.3 프로토콜 구현 (Protocol Implementation)

- **LS PLC (XGT)**: `modules/ls_plc.py`는 최적화된 **Multi-Block Read** 방식을
  사용하여, 여러 주소를 한 번의 패킷으로 읽어옵니다. 이는 통신 부하를 줄이는
  훌륭한 접근입니다.
- **Extruder**: `modules/extruder.py`는 `D0020`, `B1502` 등 주소가 코드 내부에
  하드코딩되어 있습니다. 유지보수 측면에서 아쉬운 점입니다.

### 2.4 배포 및 운영 환경 (Deployment & Environment)

- **포터블 실행 파일 (Portable Executable)**: PyInstaller를 통해 빌드된 `.exe`
  파일은 타 컴퓨터로 이식되어 별도의 Python 설치 없이 독립적으로 실행 중입니다.
- **설정 파일 관리 (Configuration)**: 타겟 운영 컴퓨터에는 `config.ini` 파일이
  함께 배포되어 있어, 현장별 IP 주소나 포트 설정 등을 유연하게 관리하고
  있습니다.

---

## 3. 실무적 제언 및 개선 사항 (Recommendations)

현장 도입 시 발생할 수 있는 리스크를 줄이고 확장성을 확보하기 위해 다음 사항을
제안합니다.

### 3.1 설정의 외부화 (Externalization)

현재 `extruder.py` 내부의 `get_data` 메서드에 직접 기술된 메모리 주소(`D0020`,
`D1500` 등)를 `config.json` 또는 `mapping.yaml` 형태의 외부 설정 파일로 분리해야
합니다. 설비 교체나 PLC 메모리 맵 변경 시 **코드 수정 없이 설정 파일 변경만으로
대응**할 수 있어야 진정한 유연성을 가집니다.

### 3.2 데이터 관리의 고도화 (Database Transition)

현재의 CSV 파일 로깅 방식은 데이터 생성/백업에는 유리하나, **과거 데이터 조회나
분석**에는 한계가 있습니다. 파일 크기가 커지면 검색 속도가 느려집니다.

- **제안**: 로컬에 경량 DB인 **SQLite**를 도입하거나, 시계열 데이터에 특화된
  **InfluxDB** (또는 TimescaleDB) 도입을 고려할 시점입니다.

### 3.3 단위 테스트 도입 (Unit Testing)

네트워크 통신 코드는 현장 장비 없이는 테스트가 어렵습니다.

- **제안**: `modules/tests` 폴더에 가상(Mock) 서버를 만들어, 장비가 연결되지
  않은 상태에서도 패킷 파싱 로직이 정상 작동하는지 검증하는 **단위 테스트(Unit
  Test)** 코드를 작성할 것을 권장합니다.

---

## 4. 결론 (Conclusion)

이 프로젝트는 **현장 데이터 수집의 모범 사례(Best Practice)**에 가깝게
구현되었습니다. 특히 **동시성 제어(Concurrency)**와 **장애 대응(Fault
Tolerance)** 로직이 잘 구현되어 있어, 당장 현장에 배포하여 운영하더라도 큰 문제
없이 가동될 것으로 판단됩니다. 위에서 언급한 '설정 분리'만 보완한다면 상용
솔루션과 견주어도 손색없는 품질입니다.
