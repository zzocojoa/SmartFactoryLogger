# V1_legacy 기반 구현 필요 기능 정리

## 목적
V1_legacy에 존재하는 핵심 기능을 기준으로 V2에 이관/구현해야 할 항목을 정리한다.

## 확인 범위 (V1_legacy)
- 데이터 수집/통신: `v1_legacy/src/modules/extruder.py`, `v1_legacy/src/modules/ls_plc.py`, `v1_legacy/src/modules/spot.py`
- 처리/상태: `v1_legacy/src/modules/logic_processor.py`, `v1_legacy/src/modules/schemas.py`
- 로깅/저장: `v1_legacy/src/modules/logger.py`
- 실행/안정성: `v1_legacy/src/main.py`
- 설정/구성: `v1_legacy/src/config.py`, `v1_legacy/src/settings_gui.py`
- UI/시각화: `v1_legacy/src/gui.py`, `v1_legacy/src/modules/graph_view.py`, `v1_legacy/src/modules/threshold_gui.py`, `v1_legacy/src/modules/ui_components.py`, `v1_legacy/src/modules/ui_utils.py`

## 구현 필요 기능 (우선순위 기준)
### P0 (운영 안정성/데이터 보존)
- 단일 인스턴스 락 및 스테일 락 처리  
  - 근거: `v1_legacy/src/main.py` (app.lock 생성/검증/정리)
- 전역 예외 처리 및 크래시 로그 기록  
  - 근거: `v1_legacy/src/main.py` (exception_hook, crash.log)
- CSV 자동 저장 + 버퍼링 + 회전(DAILY/BILLET)  
  - 근거: `v1_legacy/src/modules/logger.py` (buffer, rotation, cycle split)
- 로그 경로/스냅샷 경로 유효성 검사 및 AppData fallback  
  - 근거: `v1_legacy/src/modules/logger.py`, `v1_legacy/src/config.py`
- 통신 재시도/백오프/스킵 로직  
  - 근거: `v1_legacy/src/modules/extruder.py`, `v1_legacy/src/modules/ls_plc.py`
- 데이터 검증(범위/형식) 및 소프트 처리  
  - 근거: `v1_legacy/src/modules/schemas.py`
- 사이클/Die ID 로직 및 상태 영속화  
  - 근거: `v1_legacy/src/modules/logic_processor.py`

### P1 (현장 운영/UX 핵심)
- 상태바(Running/Warning/Disconnected) + 재연결/진단 UI  
  - 근거: `v1_legacy/src/modules/ui_components.py`
- 알림 센터(경고/에러 이력)  
  - 근거: `v1_legacy/src/modules/ui_components.py`
- 설정 UI (IP/Port, 로그 경로, AutoSave, Cycle Split, Snapshot, Password)  
  - 근거: `v1_legacy/src/settings_gui.py`, `v1_legacy/src/gui.py`
- 그래프(Time Series) 뷰 + 범례/커서/임계값 라인  
  - 근거: `v1_legacy/src/modules/graph_view.py`
- 임계값 설정 UI + config.ini 저장  
  - 근거: `v1_legacy/src/modules/threshold_gui.py`, `v1_legacy/src/modules/graph_view.py`
- 그래프 스냅샷 저장  
  - 근거: `v1_legacy/src/modules/graph_view.py`
- SPOT 카메라 뷰 + 크로스헤어 오버레이 + 포커스/액추에이터 제어  
  - 근거: `v1_legacy/src/gui.py`
- 토스트/툴팁 기반 운영 알림  
  - 근거: `v1_legacy/src/modules/ui_utils.py`

### P2 (구성/배포 편의)
- config.ini 이관/백업/복구/인코딩 탐지  
  - 근거: `v1_legacy/src/config.py`
- 안전한 설정 저장(임시 파일 + pending 처리)  
  - 근거: `v1_legacy/src/config.py`
- 시작 스크립트 및 배포 패키징  
  - 근거: `v1_legacy/start.bat`, `v1_legacy/start.sh`, `v1_legacy/SmartFactoryLogger.spec`

## 구현 백로그 (작업 항목)
현황 표기 기준: 구현 / 부분 구현 / 미구현 (V2 코드 기준)

### P0 (운영 안정성/데이터 보존)
- [x] 단일 인스턴스 락 + 스테일 락 정리 + 종료 시 락 해제 (현황: 구현)
- [x] 전역 예외 처리 + system.log/crash.log 회전 기록 (현황: 구현)
- [x] CSV 자동 저장 서비스(버퍼/배치 플러시/DAILY·BILLET 회전/AutoSave) (현황: 구현)
- [x] 로그/스냅샷 경로 유효성 검사 + AppData fallback + 권한 오류 안내 (현황: 구현)
- [x] 통신 안정화 포팅(merge/split 읽기 전환, IO 오류 후 skip/backoff) (현황: 구현)
- [x] 데이터 검증(범위/형식) Soft 처리 및 None 전파 (현황: 구현)
- [x] Die ID/Billet Cycle ID 계산 + state.json 영속화 + API 필드 추가 (현황: 구현)

### P0 상세 작업 순서 및 ETA
기준: 1인 개발, 병행 없음, 1일=8시간 기준 추정
1) 현황 점검 및 요구사항 확정 (0.5일)
   - V2 데이터 모델/API 필드 확정, 로그/저장 경로 정책 확인
2) 단일 인스턴스 락 + 종료 시 해제 처리 (0.5일)
   - app.lock 생성/검증/스테일 삭제 로직 이식
3) 전역 예외 처리 + 크래시 로그 기록 (0.5일)
   - FastAPI/서비스 스레드 예외 캡처 및 crash.log 기록
4) CSV 로깅 서비스 구축 (2.0일)
   - 버퍼링/배치 플러시/AutoSave
   - DAILY/BILLET 회전 및 Cycle 조건 적용
5) 로그/스냅샷 경로 유효성 + 권한 오류 안내 (0.5일)
   - AppData fallback 및 PermissionError 메시지 경로
6) 통신 안정화 포팅 (1.5일)
   - merge/split 읽기 전환
   - IO 오류 후 skip/backoff 및 재연결 정책
7) 데이터 검증(Soft Validation) 도입 (1.0일)
   - 범위 초과/형식 오류 시 None 처리 및 경고 로그
8) Die ID/Billet Cycle ID + state.json 영속화 (1.0일)
   - 카운터 기반 로직 이식, API 필드 확장
예상 합계: 약 7.5일

### P0 산출물 및 검증 기준
- 단일 인스턴스 락: app.lock 생성/삭제 확인, 중복 실행 차단, 스테일 락 자동 정리
- 전역 예외 처리: 강제 예외 발생 시 crash.log 생성, system.log 기록, 종료 시 리소스 정리 확인
- CSV 로깅: 헤더 포함 파일 생성, AutoSave on/off 반영, DAILY/BILLET 회전 조건 검증
- 경로 유효성: 비정상 경로 시 AppData fallback, 권한 오류 시 사용자 안내/로그 기록
- 통신 안정화: IO Error 후 backoff·skip 동작, 재연결 성공 시 정상 수집 복귀
- 데이터 검증: 범위 밖 값 None 처리, 정상 값 유지, 검증 실패 시 경고 로그
- Die/Billet ID: 카운터 변화에 따른 ID 갱신, 재시작 후 state.json 복원, API 필드 노출 확인

### P1 (현장 운영/UX 핵심)
- [x] 상태바: Running/Warning/Disconnected + 레이턴시 표시 + 수동 재연결/진단 (현황: 구현)
- [x] 알림 센터: 경고/에러 이력 누적 및 표시 (현황: 구현)
- [x] 설정 UI + API: IP/Port/로그경로/AutoSave/Cycle/Snapshot/Password 관리 (현황: 구현)
- [ ] 타임 시리즈 그래프: 다중 채널/범례 토글/커서/실시간 버퍼 (현황: 미구현)
- [ ] 임계값 설정 UI + 그래프 임계값 라인 표시 (현황: 미구현)
- [ ] 그래프 스냅샷 저장(설정된 경로 반영) (현황: 미구현)
- [ ] SPOT 카메라 보조 기능(외부 링크 버튼, 툴팁/토스트) (현황: 부분 구현 - 카메라/포커스만)
- [ ] 토스트/툴팁 기반 운영 알림 (현황: 미구현)

### P1 상세 작업 순서 및 ETA
기준: 1인 개발, 병행 없음, 1일=8시간 기준 추정
1) UI 상태바/상태 판정 로직 확정 (0.5일)
   - 데이터 갱신 지연/경고/오프라인 기준 정의
2) 상태바 UI 확장 (0.5일)
   - 레이턴시, 상태 색상, 수동 재연결/진단 버튼
3) 알림 센터 구현 (1.0일)
   - 경고/에러 이력 큐, UI Drawer/모달
4) 설정 UI + API 구축 (1.5일)
   - IP/Port/로그 경로/AutoSave/Cycle/Snapshot/Password
5) 타임 시리즈 그래프 구현 (2.0일)
   - 다중 채널/범례 토글/커서/버퍼 유지
6) 임계값 설정 UI + 그래프 라인 연동 (1.0일)
   - 임계값 저장/불러오기, 표시 on/off
7) 그래프 스냅샷 저장 (0.5일)
   - 저장 경로 유효성/권한 처리
8) SPOT 보조 기능 추가 (0.5일)
   - 외부 링크 버튼, 툴팁/토스트
9) 토스트/툴팁 운영 알림 정리 (0.5일)
   - 경고/오류/성공 메시지 템플릿
예상 합계: 약 8.0일

### P1 산출물 및 검증 기준
- 상태바: 상태 전환(정상/경고/오프라인) 및 레이턴시 표시 확인
- 알림 센터: 에러/경고 발생 시 누적 및 조회 가능
- 설정 UI: 변경 저장/반영, 재시작 후 유지
- 그래프: 실시간 갱신, 범례 토글, 커서 hover 시 값 표기
- 임계값: 설정값 저장, 그래프 라인 표시/숨김 동작
- 스냅샷: 파일 생성/경로 유효성/권한 오류 안내
- SPOT 보조: 외부 링크 정상 동작, 툴팁/토스트 노출

### P2 (구성/배포 편의)
- [ ] config.ini 마이그레이션/백업/복구/인코딩 자동 감지 (현황: 부분 구현 - 인코딩 로드만)
- [ ] 안전 저장(임시 파일 + pending 처리) 및 실패 안내 (현황: 미구현)
- [ ] 시작 스크립트/패키징/운영 문서 갱신 (현황: 미구현)

### P2 상세 작업 순서 및 ETA
기준: 1인 개발, 병행 없음, 1일=8시간 기준 추정
1) config.ini 마이그레이션/백업/복구 설계 (0.5일)
   - 버전/백업 정책, 자동 복구 플로우 정의
2) 인코딩 자동 감지/표준화 (0.5일)
   - UTF-8 BOM 생성/로드, CP949 fallback
3) 안전 저장(임시 파일 + pending) 구현 (0.5일)
   - 쓰기 실패 시 pending 파일 및 안내
4) 시작 스크립트/배포 패키징 정리 (0.5일)
   - 실행/업데이트 절차 문서화
예상 합계: 약 2.0일

### P2 산출물 및 검증 기준
- config.ini 마이그레이션: 기존 파일 유지 + 자동 백업 생성 확인
- 인코딩 처리: 메모장/파이썬에서 정상 표시, 깨짐 없음
- 안전 저장: 쓰기 실패 시 pending 생성 및 사용자 안내
- 배포 문서: 실제 실행 절차 기준으로 재현 가능

## 비고
- 위 항목은 V1_legacy 코드에서 확인된 기능 기준이다.  
- V2에 이미 구현된 기능은 중복 이관에서 제외하면 된다.  
