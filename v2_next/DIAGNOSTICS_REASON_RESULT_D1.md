# D1 진단 제외 사유 결과

최종 후보·현장 결과 및 9월 29일 승인은 [D1_CANDIDATE_RESULT.md](D1_CANDIDATE_RESULT.md),
[D1_FIELD_RESULT.md](D1_FIELD_RESULT.md), [D1_PROMOTION_DECISION.md](D1_PROMOTION_DECISION.md)에 있다.
아래 HEAD·미커밋·미실행·미승인 표기는 코드 시험 완료 당시 상태로 보존한다.

2026-09-23. **D1 로컬 코드 보완·검증 완료. 현재 장비 설정 검증과 운영 승격은 미완료.**

> 후속 실제 장비 조회: 같은 날 16:07–16:12 KST, 설정 14개 일치와 모델 표기 차이를 확인했다.
> 전체 설정 승인/comparator 검증은 미완료다. 상세 결과와 새 후보의 승인 범위는
> `SPOT_SETTINGS_COMPARISON_D1.md`를 따른다. 아래 코드 시험 단계의 증거는 그대로 보존했다.

## 기준과 보존

- 기준: fetch한 `origin/master` = `501d26245f14d7a4325048f17616a431cca1e7e7`.
- 별도 worktree 브랜치: `codex/temperature-diagnostics-reason-d1-20260923`. HEAD는 기준과 동일하며 변경은 미커밋이다.
- 원래 `codex/temperature-history-p2-20260922` / `1cd48e6457637e97ca77787c0744579cc1479dfb`의 수정 3개·untracked 38개를 보존했다. 41개 파일의 SHA256과 status/branch/HEAD 재확인이 모두 일치했다.
- 코드 시험 단계에는 commit/push/PR/merge/후보 빌드/설치/배포 및 실제 장비 접속을 수행하지 않았다.
  후속 단계에서 실제 장비 웹 UI만 읽었으며 설정·승인 값·운영 앱은 변경하지 않았다.

## 변경 내용과 호환성

기존 production eligibility 함수는 상세 사유를 이미 반환했지만 under-range 행의 evidence는
모두 `diagnostics_missing_or_stale`로 표시했다. 이제 `diagnostics_excluded_<reason>`으로 기록한다.

| 실제 제외 사유 | 새 행 evidence |
| --- | --- |
| 정책상 원인 판정 제외 | `diagnostics_excluded_fact_only` |
| 이전 poll 소속 | `diagnostics_excluded_previous_poll` |
| 진단 age 초과 | `diagnostics_excluded_stale` |
| capture 없음 | `diagnostics_excluded_capture_missing` |
| 필수 진단 필드 읽기 실패 | `diagnostics_excluded_required_field_failed` |

나머지 기존 상세 사유도 같은 형식으로 기록한다. gate 순서와 기존 primary reason 선택
(alarm→signal), 진단 재료가 있는 입력만 suppression으로 집계하는 범위는 유지한다.
원시 진단값/capture 상태를 변경하지 않는다. 위 5개 제외만 있는 표본은 Temperature blank,
under_range, cause=unknown, confidence=0을 유지한다. eligible 진단의 기존 원인 판정도 유지한다.
외부에서 주입한 제외 라벨은 제거하고 현재 판정에 따라 기록한다.

evidence 의미 변경을 `temperature-operational-v6`로 표시한다. CSV 열과 schema 버전은 그대로다.
validator는 v6에서 모호한 기존 라벨·미등록 사유·충돌하는 복수 primary reason을 거부하며,
v5의 기존 라벨과 provenance/unsupported-cause 안전 검사를 유지한다.
동일 열의 이전 rule 파일이나 rule을 알 수 없는 유데이터 파일에는 append하지 않고 별도
rule suffix 파일을 사용한다. 이전 CSV/sidecar 바이트를 보존하며 충돌 target은 쓰기를 거부한다.

## 수정 파일

| 파일 | 목적 |
| --- | --- |
| `backend/FacilityData/temperature_operational.py` | 상세 사유 evidence 및 rule v6 |
| `backend/FacilityData/repository.py` | 서로 다른 rule의 행 혼합 방지 |
| `scripts/validate_csv_v2_shadow.py` | v6 evidence 검사와 v5 안전 계약 유지 |
| `backend/tests/test_temperature_diagnostics_reason.py` | 신규 10개 시험; production service/writer/validator 호출 |
| `backend/tests/test_temperature_operational.py` | 기존 cause 검사를 유지하고 evidence 기대값 갱신 |
| `backend/tests/test_csv_v2_4_operational_contract.py` | fact_only 출력 계약 갱신 |
| `backend/tests/test_real_plc.py` | metadata rule 기대값 갱신 |
| `.gitignore` | 신규 테스트가 상위 ignore 규칙에 숨지 않도록 예외 추가 |
| `DIAGNOSTICS_REASON_PROGRESS_D1.md`, 본 문서 | 실행 경과·결과·남은 단계 |

## 검증 결과

실행 디렉터리는 새 worktree의 `v2_next`다. 기존 venv의 Python/설치된 의존성만 재사용하고,
새 production 모듈을 import했다. APPDATA/SFL_CONFIG_PATH는 격리 경로, V2_MODE는 MOCK이다.
외부 I/O는 기존 시험의 모의 transport·임시 파일을 사용한다. 전체 명령·환경·시간·종료코드는
각 `*-command.json`, 마지막 F01 환경변수는 `private-fixture-environment.json`에 있다.

| 검사 | 실제 결과 | 증거 파일 |
| --- | --- | --- |
| 기존 코드의 D1 실패 재현 | 6개 시험, 12 assertion 실패, 오류 0 | `d1-before-fixture-corrected.log` |
| 기존 동일 열/rule append 재현 | 1개 시험 실패 | `d1-rule-rollover-before.log` |
| 직접 관련 회귀 1차 | 203개 통과, exit 0 | `d1-after-r1.log` |
| 전체 backend 1차 | 834개 실행, 실패 0, skip 1 | `backend-full.log` |
| 최종 전체 backend + F01 | **836개 통과, 실패 0, skip 0**, 175.005초, exit 0 | `backend-full-final-with-f01.log` |
| 기준 코드와 합성 입력 비교 | **5,200건**, evidence 외 모든 decision 필드 동일, exit 0 | `baseline-comparison-r2.json` |
| backend Ruff E9/F821 | 통과, exit 0 | `backend-lint-final.log` |
| 변경 validator Ruff E9/F821 | 통과, exit 0 | `validator-lint-final.log` |
| 저장소 mypy 대상 8개 파일 | 통과, exit 0 | `backend-typecheck.log` |
| NSIS 준비/시작 추적/closeout/signature/workflow 자체검사 | 5종 통과, 모두 exit 0 | `qa-*-command.json` |
| diff 공백·신규 파일·원래 작업 보존 | 통과 | `final-review.json`, `original-preservation.json` |

최종 suite는 `python -m unittest discover -v -s backend/tests`로 실행했다. F01 원본 SHA256은
`bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4`이며 hash assertion을 포함해 통과했다.
기존 G/T/C/L1/P2·service·repository 통합 시험을 포함한다. 새 10개 시험을 full suite 로그에서 확인했다.
5,200건 비교는 정상/under-range/over-range/stale/source_error/unknown/startup과
cache 허용·TTL 만료, comparator/phase 및 13개 suppression reason을 포함한다.

실패/재시도도 원문으로 보존했다. 최초 fixture의 alarmstatus 타입 오류는 시험 입력만 수정한 뒤
실패를 재현했다. QA 초기는 호스트 PS7 module path와 별도 worktree의 js-yaml 탐색 문제로 실패했고,
native PS5.1 module path·기존 node_modules를 **자식 프로세스 환경에서만** 지정한 후 통과했다.
validator 추가 lint의 첫 호출은 지원하지 않는 CLI 옵션으로 exit 2였으며 올바른 isolated 호출로 통과했다.
첫 differential의 상태 fixture는 sentinel/enum 우선순위 때문에 일부 의도한 상태에 도달하지 않아,
r2에서 상태별 assertion과 올바른 입력을 추가했다. 최종 근거는 r2다. 안전 assertion은 삭제하지 않았다.

Frontend/Electron suite와 후보 패키지 빌드는 실행하지 않았다. 해당 소스/CSV 열/API 타입 변경이 없고,
새 evidence 라벨의 frontend/main/preload 소비처도 없음을 검색했다. 패키지 검증은 새 후보 단계에 남긴다.
독립 검토는 수행하지 않았고, production diff·기존 gate·과거 rule 호환성·rollover를 자체 검토했다.

## SPOT 불일치의 확인 범위

이전 원본 캡처와 최근 120분 후보 metadata의 해시를 먼저 확인한 뒤 현재 production fingerprint
함수로 양쪽 fingerprint를 재계산했다. 이전 캡처의 다른 21개 필드를 고정하고 build commit만
v1.0.20의 `cd8cfa649203494cf087206cf656dc2197107ea1`로 바꾸면 저장된 승인 fingerprint가 재현된다.
최근 후보 `d254871f89c98154b4e32879e29601df78f7e159`의 22개 입력과 대조해도 차이는 build commit 하나다.

따라서 **해당 기록의 fingerprint_mismatch는 build identity 차이로 재현됐다.** 이 재구성은
실제 장비의 승인 시점 readback이 아니다. 현재 장비 설정 일치나 comparator 의미를 검증한 것으로
해석하지 않는다. `device_config_readback_status=not_supported`, effective operator/comparator verified=false를
유지했다. 설정·승인 fingerprint를 수정하지 않았다. 세부 비교는 `spot-attestation-comparison.json`에 있다.

## 위험과 다음 단계

- 위험: 중간. 진단 표시 변경이며 측정값·cause·안전 gate 변경은 없다. 부수 영향은 rule 경계의 CSV 분리다.
- 관측성: 정책 제외와 실제 missing/stale/필드 실패가 구분된다. 기존 집계와 raw 진단은 유지된다.
- 이관: 데이터 변환 없음. 이전 CSV/sidecar 유지. 파일 이름에 rule suffix가 추가될 수 있다.
- 실패 모드: rollover target도 호환되지 않으면 writer가 오류를 기록하고 append를 거부한다. 임의 덮어쓰기는 없다.
- 복귀: 아직 운영 변경은 없다. 향후 후보 복귀 시 검증된 원본 실행파일을 사용하고 새 수집 파일로 시작해 rule이 다른 파일에 구버전 writer가 append하지 않도록 한다.
- 한계: 실제 자정·OS 시계 보정·미종료·over-range 현장 시험과 새 D1 실행파일 시험은 미실행이다. 과거 120분 시험은 이전 실행파일의 근거다.

다음 단계는 **현재 SPOT 장비 설정을 승인 자료와 읽기 전용으로 대조하는 것**이다.
그 뒤 별도 승인 범위에서 D1 commit/EXE를 고정하고 패키지 검증·남은 현장 시험 또는 승인된 위험 수용을
구분해야 한다. D1 코드 완료를 운영 적용 승인으로 해석하지 않는다.

위 다음 단계는 코드 시험 완료 시점의 계획이다. 이후 실제 UI 대조 결과와 현재 다음 승인 단계는
`SPOT_SETTINGS_COMPARISON_D1.md`에 기록했다.

## 산출물 위치

로컬 `artifacts/temperature-diagnostics-reason-d1/`에 before/after 원문, 명령/환경,
`regression-matrix.json`, `full.diff`, `new-files-manifest.json`, `artifact-manifest.json`을 보존했다.
`artifacts/`는 원래 정책대로 ignore된다. 원문 로그는 private이므로 자동 공개하지 않으며,
신규 production 테스트와 보고서는 untracked 목록에 표시되는 것을 확인했다.
