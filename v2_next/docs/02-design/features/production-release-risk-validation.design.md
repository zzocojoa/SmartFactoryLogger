# 프로덕션 출시 리스크: 설계와 구현 착수

## 2026-10-26 최종 통합 판정 설계 적용

[승인 기록](../../V2/05_운영_배포/approved_final_disposition_20261026_c32.json)의 정확한 사건·실행·commit/installer에만 처분을 적용한다.
검산기는 승인된 제안의 바이트/해시, 보존 QA 원시 health3,602개, 같은 닫힌 실행의 설정/종료/CSV 소비자,
이미지 검사 결과·실제 종료 코드, VM/패키지·표시 근거를 결합한다. 기술 PASS와 승인 예외는 별도 필드로 보존한다.

최종 통합 QA가 수용 가능하고 서버 설치 바이트·일반 실행이 동일할 때만 정확한 commit에 새 태그를 등록한다.
기존 태그를 덮어쓰지 않고 원격 peeled commit까지 확인한 뒤 운영본/다음 롤백 기준을 갱신한다.
예: 다른 installer SHA·원시 증거 불일치·추가 요청 오류는 승인 문구로 면제하지 않고 승격을 차단한다.
과거 원문과 미확정/실패는 재작성하지 않는다. 현재 완료 결과는 [최종 보고서](../../04-report/production-release-risk-validation.report.md)를 따른다.
이전 장의 HOLD/promotion_allowed=false는 각 구성 요소의 당시 범위이며 최종 승인 처분과 구분한다.


## 2026-10-23 승인 정책의 구현 계약

[승인 정책](../../V2/05_운영_배포/approved_release_policy_20261023.md)이 아래 이전 미확정 성능/알람 조건에 우선한다. `qa_spot_temperature_v25.ps1`은 `-ReleasePolicyPath`와 `-ExpectedReleasePolicySha256`을 함께 받은 경우에만 해시로 확인한 C32 알람 제외 조건을 적용한다. 기본 호출은 기존 comparator 요구를 유지한다. 제외는 `scope_exclusions`에 기록하며 physical test는 NOT_TESTED다.

`approved_release_assessment.py`는 보존된 HTTP/수신 원본에 승인된 백분위·공백 기준을 적용한다. 최초/최종 요청, 시계·sequence·오류·측정 누락 검사는 유지한다. 화면 판정은 실제 표시와 새 프레임 대응 증거를 요구하며 load 또는 RAF만으로 PASS를 만들지 않는다. 개별 결과는 전체 출시 승격을 허용하지 않는다.

원시 FAIL/INCOMPLETE와 기존 도우미의 해시 결합 출력은 변경하지 않는다. 과거 자료 보류와 구버전 종료 제약의 처리는 별도 승인 정책/재평가 결과에 연결한다. 새 수치 때문에 설치본 재빌드나 완료된 120분 시험을 자동 반복하지 않는다.


## 2026-10-20 추가 검토: v2 관찰의 증거 공백

사용자의 재검토·추가 개선 요청에 따라 아래 누락을 보완한다.
기존 현장 원시 기록·FAIL·앞선 평가 파일은 수정하지 않는다.

- HTTP 마지막 시도 값을 명시하고, `response_finished_ns`가 있는 경우 요청 시작/응답 끝/
  처리 끝의 순서와 보고된 응답시간을 대조한다. 앞 요청 처리 끝보다 이른 다음 시작은
  비중첩 계약의 시계 오류로 기록하며 INCOMPLETE다. 누락된 끝값을 앞 값으로 채우지 않는다.
- 자원 조회 실패로 backend 행을 확보하지 못한 경우는 계측 INCOMPLETE다.
  실제 확보된 동일 PID의 생성 시각/실행 파일 불일치와 독립 process/health 결합 실패는 FAIL이다.
- 이미지 통신 기록이 없는 DOM load만으로 전체 관찰 COMPLETE를 선언하지 않는다.
  요청/응답/종료의 연결·시계, 관찰기 오류/소실, 창 구간을 검사한다.
  수집기 호스트의 event 수신 시각과 브라우저의 monotonic 시각을 섞어 간격을 계산하지 않는다.
- 브라우저 Resource Timing과 DOM load를 같은 페이지 시계로 기록하여
  load 간격, 응답 완료 간격, load 이후 다음 요청까지의 간격을 별도로 산출한다.
  이웃 사건의 시간차는 같은 이미지/프레임 대응이나 물리 표시 지연의 증명이 아니다.
  설정값 및 프레임 대응이 없으면 자동 계약 PASS를 만들지 않는다.
- 오류·누락·잘못된 시계·자원 조회 실패를 재현하는 회귀와 실제 Chromium fixture를 검사한다.
  기존 fact/CSV/이미지·종료 정산 검사의 실패 조건도 다시 확인한다.

## 2026-10-20 승인된 운영 관찰 계약 v2

이 절은 이후 운영 판정에서 아래 기존 200/500ms 단발 초과·250ms 고정 슬롯
무누락 조건보다 우선한다. 과거 수집기와 판정 함수의 기본 동작은 재현용으로 보존한다.

1. `field_operational_assessment.py`는 원시 HTTP 표본으로 요청 성공, 계측 완전성,
   초과 통계와 운영 적합성을 분리한다. 200/500ms는 비교 지표이며 새로운 허용치는 없다.
   시간 값·sequence·누락을 검사하고 연속 초과는 누락/오류에서 끊는다.
   측정되지 않은 UI·저장·공정 허용시간은 `NOT_EVALUATED`; 출시 HOLD는 유지한다.
2. `OperationalObservationSpec`와 `operational-observe` 요청은 명시적인 새 경로다.
   고정 health2초/data6초만 수집하며 이미지 요청을 합성하지 않는다.
   첫/마지막 health와 인증 control-health의 identity 검사는 유지하고 지연은 보존한다.
   지연만으로 identity binding을 실패시키지 않는다. 구 `observe`/timing 진단은 그대로다.
3. HTTP 응답 오류는 요청 FAIL, 기록 공백/취소/잘못된 시간은 계측 INCOMPLETE다.
   수집/검산 성공은 운영 성능 PASS가 아니다. 수집기 exit와 운영 판정을 별도 기록한다.
4. 화면 관찰기는 이미 열린 지정 페이지에 연결해 실제 이미지 요청과 `.camera-image`
   load/error 및 document 가시성/포커스를 기록한다. 요청/타이머를 교체하거나
   focus·visibility를 위조하지 않는다. 생성/종료 시 페이지나 앱을 닫지 않는다.
   수신/표시 간 정확한 대응이 없으면 이를 추정하지 않는다.
   headless fixture는 도구 검증용이며 실제 작업자 화면 검증으로 인정하지 않는다.
5. 전수 데이터 검증과 해시·프로세스 세대·설정·종료 정산은 유지한다.
   HTTP 관찰만으로 장치 샘플 무손실이나 저장 완전성을 선언하지 않는다.

검사 예: 250ms 성공 health는 초과1/요청PASS/운영NOT_EVALUATED, timeout은 요청FAIL,
이미지 고정 슬롯139누락은 계측INCOMPLETE/저장손실NOT_EVALUATED, 실제 화면에서
300ms 로드 후250ms 대기는 정상 제품 예약 방식으로 기록한다. 정상·오류·가려짐·
연속 지연·미측정과 기존 strict 계약의 회귀를 함께 확인한다.

구현·검사 범위와 남은 현장 조건:
[운영 판정 개정 보고서](../../04-report/production-release-risk-validation-operational-criteria-20261020.report.md).

## 2026-10-17 종료 검산의 읽기 크기 보완

고정 원본120분 자료의 로컬 재검산과300파일/2,400회 순서 균형 비교에서 작은 파일에
1MiB·16MiB 읽기 요청을 주는 비용을 확인했다. 원래 서버 timeout의 정확한 단계는 미확정이다.
보완 범위는 검증 도우미의 `stream_fact`와 `read_json`이며 제품의 수집/보존 정책은 유지한다.

- 한 번의 읽기는64KiB 이하로 고정한다. `stream_fact`는 처음으로 seek한 뒤 EOF까지
  모든 바이트를 해시하고 기존512MiB 상한을 유지한다.
- JSON은 기존 기본16MiB/호출별 limit을 유지하며, 초과 탐지를 위해 최대limit+1바이트만
  읽는다. 짧은 read를 EOF로 처리하지 않고 이어 읽으며 실제 EOF 또는 상한까지 확인한다.
  UTF-8은 청크를 결합한 뒤 기존 엄격 JSON 소비기로 처리한다. 결합 중 최대약2배의
  bounded buffer가 존재할 수 있으므로 청크는 파싱 전에 해제한다.
- 경로/reparse·파일 집합·동일성·SHA·중복 JSON 키·비유한 수 거부 및180초 제한은 유지한다.
  I/O 실패를 부분 결과의 성공으로 바꾸지 않는다.
- 수정 전/후 회귀는 작은 파일 읽기 요청,16MiB/512MiB 실제 경계, 짧은 read, EOF/오류,
  UTF-8 청크 경계, 기존 native 설치/관찰/종료·trace 소비자 범위를 검사한다.
- 원래120분 전체 corpus의 값/해시 및 실패 판정을 대조하고, 대형 payload 파일 처리량도
  확인한다. 같은 서버의 단계 계측 전에는 원래 timeout 원인이나 현장 개선 PASS로 판정하지 않는다.

02:30 KST 로컬 검증: 수정 전 11개 검사에서 실패4/오류2를 재현했고, 동일 검사 수정 후11개와
기존 영향 범위152개가 모두 exit0으로 통과했다. 원본→수정→수정→원본 순서의 전체 검산은
80.158/29.436/29.329/81.914초이며 70,076개 파일·모든 결과 값·원래 FAIL 판정이 일치한다.
1,899개/563,853,145bytes 설치본 구성 파일의 잠금·전체 해시·재검산도 네 실행 모두 통과했다.
실행 명령과 입력 환경은 `C:/Users/user/Desktop/SmartFactory/RB17_3f0ba68a`의
`native-affected/request.json`, `comparison-plan.json`, 각 `*-execution/terminal.json`에 보존했다.
독립 정산 `review.json` SHA256은 `cb5eaad6f60b6eb95c260031bf5a8263f5e31876b8ca8e9ad51a4dab11b25261`.
호스트·캐시 상태는 통제하지 않았으며 서버 개선 확인과 원래 timeout의 인과 판정은 미완료다.

동일 서버의 다음 진단은 기존 Python3.12.8 x64와 고정된 원본/보완 모듈11개씩을 사용한다.
운영 앱을 호출하거나 재시작하지 않고, 원래7200초 자료의 외부 고정 launcher/manifest/core
해시와 전체 component 결과를 대조한다. 설치본은 기존 잠금/전체 해시/재검산으로 확인한다.
모듈은 검증된 새 실행 폴더에 보존하고 새 결과 폴더만 생성한다. 원본은 수정하지 않는다.
기존 `Invoke-RunNative`의 suspended child/job 할당·종료·독립 시간 제한을 재사용하며,
각 진단600초는 원래 관찰의180초 finalization 제한을 변경하는 설정이 아니다.
payload-open/recheck, component별 검산, review-window, 마지막 recheck의 시작/종료를
각각 durable 파일로 남긴다. 중단 시 마지막 시작 기록을 보존하며 누락을 PASS로 처리하지 않는다.
원본/수정 순서의 관찰은 현재 호스트에서의 재검산 증거이며 과거 timeout의 인과 확정은 아니다.

03:20 KST 원본 서버 진단은600.147초 제한에서 중단됐고 `component-http`와
`review-window` 종료 기록이 없다. owned Job의 잔여 프로세스0과 동일 앱 세대·원본13개
해시를 확인했다. 실패 시 중단하는 기존 launcher에 따라 수정 코드 차례는 실행되지 않았다.
후속은 새 묶음의 `sfl-offline-replay-new-only-launch-v1`로 수정 코드만 실행한다.
원본 실패 launcher SHA와 정리 결과를 선행 조건으로 확인하고, 소스·입력·검사 및600초
진단 상한은 동일하게 유지한다. 기존 묶음/결과를 수정하거나 원본 코드를 재시도하지 않는다.

앞선 로컬 ABBA 검사는 자료 검산 뒤 설치본 잠금을 검사한 순서였다. 잠금을 유지하는
첫 추가 검산299.704초 뒤, 잠금 해제29.889초와 잠금 유지 재검산31.425초를 관찰했다.
잠금 유지만으로 첫 지연을 재현하지 못했으며 호스트/캐시 영향은 미통제다. 잠금 보호를
제거하는 제품 변경의 근거로 사용하지 않는다. 세 실행 모두 전체 결과는 원래 FAIL과 같다.

## 2026-10-17 03:39 KST — 1.0.30의 같은 요청 추적 준비

120분 health 초과2건의 HTTP/resource 대조는 이미 완료됐다. 같은 요청의 서버 내부
구간/ETW가 없으므로 당시 원인을 소급 확정하지 않는다. 기존 추적 진단은 1.0.29로
고정돼 있어 현재1.0.30을 거부한다. 제품을 재설치하지 않고 진단 도우미의 대상만 확장한다.

- 1.0.29/1.0.30의 등록된 commit과 각각의 payload SHA를 짝으로 검사한다.
  상위 request, spec, package, 설치 파일, health build/version, 설정 기준이 모두 일치해야 한다.
- candidate_commit을 생략한 과거 spec은1.0.29만 뜻한다.1.0.30은 명시해야 하며
  다른 후보/해시/런타임이 섞이면 수집 전 또는 해당 응답 검증에서 실패한다.
- 기존6초/최대900초 조건부 추적,200ms trigger,독립 감시·owned Job 정리,
  원본 보존·새 결과 경로·입력 잠금·출시HOLD를 유지한다.
- 검증은 양쪽 후보의 정상 결합,교차 후보/해시 거부,1.0.30의 세 trace schema,
  설치/설정 기준으로 전달되는 후보와 수집 전후 세대 변경 거부를 포함한다.
  frozen 실행 파일·서버 전달/현재 세대 요청·실제 추적은 이후 별도 증거가 필요하다.

작성일: 2026-10-10. 기준: `codex/production-release-risk-validation-20261010`,
`eb9af6f1398d588733f3f1884411e2612496d267`.
계획: [기준 플랜](../../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md).

정책 갱신: 2026-10-12 사용자는 인증서 없이 앞으로도 미서명으로 운영하도록 지시했다.
현재 대상은 최종 clean commit의 미서명 내부 운영 NSIS 설치본이다. 인증서/서명 담당자·서명 환경·
서명자·유효 서명·타임스탬프 요구를 제거하고 `NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY`로 기록한다.
실제 installer/앱은 `NotSigned`로 확인하며 서명 PASS를 만들지 않는다. 아래 R1~R5 기술 조건과
R6의 출처/무결성·설치/복구·현장 QA 조건은 유지한다. 과거 서명 조사·봉인 증거는 당시 기록이다.

## 1. 아키텍처와 확인된 상태

Electron이 FastAPI backend의 시작·정상 종료를 관리하고 React 화면이 HTTP API를 조회한다.
backend는 PLC·SPOT 수집, 온도 상태/설정 provenance, CSV logger,
observation/image fact와 종료 증거를 연결한다. SPOT 이미지 저장은 bounded queue와
단일 writer thread를 사용한다. 현재 후보는 정확한 clean commit/버전·태그에서 미서명으로 빌드하고
payload 출처·manifest/provenance·SHA256과 실제 `NotSigned` 상태를 검사한다.
기존 서명 workflow/검사기는 별도 서명 경로로 보존하며 이번 운영 후보의 실행 gate에서 제외한다.

착수 시 HEAD/master/origin/master는 모두 위 기준 commit이다. 기존 변경은 계획 문서와
PDCA 상태이며 제품 코드는 기준과 동일하다. 실제 운영본은 `541d701d…` / `08C061EE…`,
교체 전 이전본은 `4c97d4a…` / `D453C1D1…`이다. 소스 기준과 운영 설치본을 혼용하지 않는다.

원본 적용 후 검토에는 최초 timeout 원인 `UNCONFIRMED`, 첫 health `223.4887ms`,
과거 image drop 15건이 남아 있다. 최근 누락 0건·설정 보존·미서명 내부 승인은
R1~R6의 완료 증거가 아니다.

## 2. 여섯 항목의 책임과 완료 기준

사용자는 유지보수를 아무 때나 수행해도 된다고 승인했다. 실명 담당자·검토자와 승인 장비 프로파일은
Codex가 서버 기록에서 직접 확인한다. 2026-10-12 서버 연결이 복구돼 과거 Operator1 기록과 현재 fingerprint mismatch를 확인했다.
당시 아래 역할의 실제 지정과 승인 실장비 프로파일·최종 attestation은 미완료였다.

2026-10-12 후속 직접 답변 “모두 본인”으로 장비·운영 확인, QA, 릴리즈 판단 담당자를
모두 사용자 본인으로 확정했다. 위 문장의 역할 미지정은 당시 상태이며 현재 승인 실장비
프로파일·최종 attestation과 기술 QA는 계속 미완료다. Codex는 개발·회수·검증 실행을 담당한다.

| ID | 담당 역할 | 조치 사항 | 검증 방법 | 완료 기준 |
|---|---|---|---|---|
| R1 최초 timeout | Backend 엔지니어 / QA | 원본 요청 순서·서비스 세대·시간선 복원. 연결/응답/본문/JSON/서버 처리·잠금/파일 I/O 분리. 인과가 입증된 병목 수정 | 격리 환경의 작은/실제 규모 fact, 느린 디스크, 초기화 중 동시 health. 수정 전 실패/후 통과·계측 유무 비교 | 원본 사건과 일치하는 인과 증거 및 첫 요청 포함 재발 0. 부족하면 UNCONFIRMED/HOLD |
| R2 전체 성능 | 성능 QA / Backend·Frontend | 조건/도구 고정, 초기 시작 격리 10회·현장 3회, 1/3탭, 동시 저장, 전체 API·실제 화면·자원 수집 | health 2초 비중첩·data 6초, first/max/p50/p95/p99/timeout/error/연속 초과. 실제 이미지 load와 가시성 관찰. 자원 warmup120초·5초·300초·선호60/최소48표본·최소240초. 새 미서명 개선 후보 15분/120분 | 운영 관찰 계약 v2: 오류 FAIL, 부족한 계측 INCOMPLETE, 운영 허용시간 미정 NOT_EVALUATED. 200/500ms 초과는 진단 지표, 기존 값·FAIL 보존. 시작≤30초 등 나머지 계약 유지 |
| R3 장비 설정 | 장비/운영 담당 / 설정 엔지니어·QA | 승인 모델·모드·범위·방사율·LowSignal·comparator·통신 프로파일과 실제 화면/readback/파일 대조. 최종 build attestation | 임계값 미만/동일/초과, build·fingerprint·config_drift·runtime·동일 세대 종료 sidecar. not_supported는 실제 운영자 확인 | 필수 불일치/미확인0·drift0·동일 fingerprint·운영자 확인. fingerprint만으로 실장비 적합성을 선언하지 않음 |
| R4 전수 데이터 | 데이터 무결성 QA / 수집 엔지니어·운영 | 전체 과거/현재 CSV·metadata·fact·manifest·이미지·영수증 목록/해시와 일관된 사본 확보. 스키마별 검사와 전체 이미지 해시/디코딩·역참조·종료 delta | 기존 CSV validator 전체 규칙 + 이미지 실물 검사. streaming/index와 작은 동일 입력 대조, 시작/종료 목록·해시 비교 | 검사/분류100%·수량/바이트 정산·미분류0. 후보 손상/설명 없는 누락/불일치/미완료 종료0. 과거 실패 처리 결정 별도 |
| R5 과거 drop15 | SPOT 엔지니어 / 데이터 책임자·QA | 이전 build의 동일 drop 경로 대조, 크기 초과/큐 포화/worker 실패/정책 제외/retention 구분. 카운터·fact·로그·event 시간선 정산 | 격리 크기 경계/큐 포화/느린 저장/디스크 부족/권한 거부/정상 종료 drain. 원인별 회귀·새 정상 운전 | 과거15건의 원인·영향·복구 가능성·처리 결정 증거, 예방 회귀 통과·새 drop/저장 실패0·정상 종료. 과거 증거 부족이면 HOLD |
| R6 미서명 패키지/정식 QA | 릴리즈 책임자 / 보안·QA·운영 | 사용자 미서명 정책·버전/태그 재확인, 최종 clean commit 고정·미서명 빌드·전체 NSIS payload 추출, 동일 설치본으로 신규/업그레이드/재시작/복구/현장 QA | installer/Electron NotSigned, 요구 서명 판정 NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY, commit/tag/SHA256/payload/provenance. health/build/관련 도구 회귀 및 FINAL PASS·validator0·동일 세대 정상 종료 | 정확한 최종 미서명 설치본의 필수 소스/패키지/설치/복구/설정/성능/데이터/현장 QA 모두 통과. 인증서 부재는 HOLD 사유에서 제거, 미서명 운영 승인은 기술 QA를 대체하지 않음 |

구계약은 health 50ms 경고/200ms 실패, data 100/500ms였다. 2026-10-20 이후
200/500ms는 초과 통계를 보존하는 비교값이며 운영 판정은 문서 첫 절의 v2를 따른다.
SPOT 이미지 500ms 경고(실패 상한 미정), LCP 2500/4000ms, CLS 0.1/0.25는 유지한다.
아래 날짜별 과거 구현·검증의 strict 조건과 기록은 당시 계약의 이력이다.

## 3. 이번 로컬 구현의 입출력과 실패 조건

### 3.1 R1: writer 생성 잠금 분리

수정 전 확인된 코드 경로: `_get_spot_image_capture_writer` → constructor →
`_initialize_manifest_state` → 전체 fact 해시 + CSV 행 수 계산이
`_spot_image_capture_lock` 안에서 실행된다. 같은 잠금을 producer·종료 snapshot도 쓴다.
과거 서버 사건과의 인과는 아직 입증되지 않았지만, 느린 constructor가 종료 조회를
막는 현상은 격리 회귀로 증명할 수 있다.

- writer의 생성/재사용/설정 signature는 별도 `_spot_image_capture_writer_lock`으로 직렬화한다.
- 기존 상태 잠금은 counter·queue outcome·shutdown baseline의 atomic transition을 유지한다.
- 상태 잠금을 writer/file 잠금과 중첩하지 않는다. constructor·fact I/O·join을 상태 잠금 안에 넣지 않는다.
- constructor가 멈춰 있어도 memory-only shutdown snapshot을 읽을 수 있어야 한다.
- hash/row 검사·dedupe·manifest fail-closed·설정 경로 변경 계약을 유지한다.
- 이 수정만으로 최초 `/api/spot/config`의 동기 fact scan이나 200ms 성능이 해결됐다고 하지 않는다.

2026-10-12 추가 보완은 설정 조회에만 대기 없는 manifest snapshot을 사용한다.
서버에서 회수한 fact의 4,091,827행 prefix가 과거 metadata의 SHA256과 정확히 일치했고,
격리 HTTP 시험에서 같은 입력으로 첫 5초 timeout과 약 20초 초기화를 재현했다.
이는 원본 서버 사건의 인과를 확정하는 로그와 구분한다.

- `/api/spot/config`는 writer를 생성하지 않으며 생성 중인 writer/file 잠금을 기다리지 않는다.
- 미생성·생성 중·다른 경로·파일 잠금 사용 중이면 `fact_row_count=null`, `fact_sha256=null`,
  `fact_manifest_state_ready=false`로 미확인을 명시한다. 미확인을 0행/PASS로 해석하지 않는다.
- 이미 준비된 같은 설정의 writer는 파일 잠금을 즉시 얻을 때만 행 수·digest를 한 snapshot으로 읽는다.
  외부 크기 변경/읽기 오류는 digest를 미확인으로 만들고 기존 fail-closed 상태를 유지한다.
- 시작 metadata, worker, 종료 manifest의 기존 대기/전수 검사 경로는 유지한다.
  새 background initializer·hash 생략·retention 변경을 추가하지 않는다.
- 실제 HTTP 초기/초기화 중/완료 후의 제한된 세 표본은 전체 R2 성능 계약이나 서버 현장 PASS가 아니다.

### 3.2 R5: 원인별 drop 계수

- 기존 `dropped_count`와 별도로 `dropped_oversize_count`, `dropped_queue_full_count`를 추가한다.
- 각각 실제 크기 초과/QueueFull 분기에만 계수하고 health와 종료 snapshot에 노출한다.
- 정상 정책 제외·interval 제외·worker failure는 drop으로 계수하지 않는다.
- 정상 종료나 성공 저장은 과거 계수를 초기화하지 않는다. test reset만 기존 격리 방식으로 초기화한다.
- 기존 CSV/fact/manifest 스키마는 변경하지 않는다. 새 필드는 과거15건의 원인 소급 분류가 아니다.

### 3.3 R2: client 응답 시간과 관측 요약

- `Invoke-ReadOnlyEndpoint`에서 `Stopwatch`로 요청 시작부터 전체 본문 수신/오류 본문 처리까지 측정한다.
- 성공·HTTP 실패·timeout 모두 `client_elapsed_ms`를 raw envelope/raw index에 보존한다.
- JSON parsing·서버 내부 시간은 포함된 것으로 주장하지 않는다. 연결/TTFB 세분화는 후속 계측이다.
- health 원시 표본을 첫 값·최대·nearest-rank p50/p95/p99, error/timeout/미측정/200ms 초과 건수로 요약한다.
- 첫 실패를 제외하지 않고 필수 시간 누락/비정상 값은 NOT_MEASURED, HTTP 실패/시간 초과는 FAIL로 남긴다.
- 이 요약은 수집된 요청의 관측 판정이다. 기존 수집기의 주기/다중 endpoint 순서는 유지하며,
  정식 R2의 전용 2초 sampler·시작/화면/자원·15/120분 gate를 대체하지 않는다.
- sanitized image 상태에도 새 원인별 계수를 전달하고 CI QA selftest에 수집기를 등록한다.

### 3.4 R4: 선택 fact와 이미지 사본 실물 검사

- `scripts/validate_spot_image_files.py`는 선택 fact를 CSV streaming으로 읽고 이미지 SHA256/크기,
  모든 프레임의 디코딩, 기록된 MIME/치수를 확인한다. 기존 CSV 스키마 검사와 함께 사용한다.
- SQLite 인덱스로 ID/경로 중복과 전체 이미지 역참조를 확인한다. Windows 대소문자 별칭은 동일 파일로 정산한다.
- 이미지 폴더 전후 목록/stat/SHA256 및 fact 전후 identity/hash를 보존한다. 변경·누락·고아·불명 파일은 실패다.
- 경로 이탈·ADS·symlink/reparse를 거부하고 입력 밖의 새 결과 폴더만 허용한다. 기존 출력이나 원본을 덮어쓰지 않는다.
- `scope=copied_image_subtree_and_selected_fact`, `full_data_gate=NOT_EVALUATED`를 항상 기록한다.
  전체 snapshot 일관성·모든 CSV/metadata/manifest/영수증·시작/종료 delta의 R4 완료 판정은 별도다.
- 회귀 파일 `backend/tests/test_spot_image_file_validation.py`는 Windows 대소문자·해시/크기·디코딩·
  경로·누락·역참조·입력 보존·출력 재사용을 검사한다. 제품의 기존 저장/보존 스키마는 변경하지 않는다.

## 4. 검증 순서와 작업 경계

각 결함은 실패 회귀 1개 → 수정 → 해당 회귀 통과로 진행한다.
추가 경계: 동시 writer 요청 단일 생성, 생성 실패 후 재시도, 실제 fact 해시/행 수,
크기 상한 동일/초과·큐 포화·정책 제외, 정상 drain/과거 실패 보존,
첫 지연/200ms 경계/오류/timeout/누락·비정상 timing/본문 수신 계측.

최종 상태에서 관련 backend 모듈 검사, PowerShell 수집기 selftest,
`npm run health`, `npm --prefix frontend run build` 및 `git diff --check`를 실행하고
원시 출력과 종료 코드를 보존한다. 패키지/실장비/성능을 로컬 단위검사의 통과로 대체하지 않는다.

이번 착수는 로컬 소스·도구·문서 수정이다. 원본 증거·운영 설치본·장비 설정·서명 비밀·
기존 workflow 승인·rollback 기준은 유지한다. 유지보수 시간은 언제든 가능 승인을 적용한다. 현장 진입은 책임자/승인 프로파일과
정확한 후보 설치본이 준비된 후 기준 계획의 단계 순서를 따른다.

## 5. 후속 PDCA와 증거 양식

| 단계 | 실행 | 산출물과 종료 gate |
|---|---|---|
| Plan | 여섯 책임자/검토자·승인 프로파일·전체 데이터 범위·유지보수 시간 확정 | 원본 실패/운영본/복구 설치본 출처와 범위 고정 |
| Do | 이번 회귀/수정 + 원본 시간선 분석, 전체 사본 확보, R3/R4 도구 보완, 격리 장애 재현 | 수정 전후 증거·전수 입력 manifest·설정 attestation. 원인 미확정은 HOLD |
| Check 후보 | 최종 소스 검사 → 버전/태그 확인 → 정확한 clean commit의 미서명 빌드 → payload/출처/해시·NotSigned → 격리 설치/복구 | 동일 installer SHA256에 결합한 소스·패키지·설치·복구 결과 |
| Check 현장 | 조건/백업 확인 → 정상 종료·승인 설치/설정 → QA → 초기15분/canary120분 → 전체 새 데이터+delta | 동일 build/logger/fingerprint·성능·CSV/이미지·정상 종료, 여섯 DoD 통과 |
| Act | 실패 보완/영향 검사 재실행, QA/릴리즈 결정, 승격·적용 확인 후 기준 갱신 | 새 build/installer를 다음 rollback으로 등록. 이전본·실패 증거 보존 |

서버 자료는 실제 Desktop/SmartFactory의 새 실행 폴더와
`Z:/SmartFactory/YYYYMMDD/{send,return,records}`를 사용한다. Codex가 공유 전송과
Chrome 원격 데스크톱의 서버 최종 폴더 복사·절대경로/파일 확인까지 맡는다.
공유 업로드만으로 전달 완료라고 하지 않는다. 실제 서버 결함 주입/강제 종료/삭제/자동 rollback은 실행하지 않는다.

실행별 기록 예:

```text
run_id / 역할 담당자·검토자 / 승인 범위·유지보수 시간:
source commit / tool SHA256 / installer SHA256·NotSigned·태그 / 미서명 정책 근거:
signature_requirement: NOT_REQUIRED_BY_APPROVED_UNSIGNED_POLICY
입력 목록 SHA256 / 전체 파일·행·이미지·바이트 수 / 관측 조건:
service/logger 세대 / config fingerprint / 정상 종료 receipt:
R1~R6 각각: FACT 또는 INFERENCE / evidence 경로·해시 / PASS·FAIL·HOLD:
실행 명령 / stdout·stderr / exit_code / 미실행·미측정:
다음 조치 / 재개 조건 / 이전→새 rollback 기준과 적용 확인:
```

## 2026-10-13 이미지 저장 실패 로그의 식별 정보 보완

서버 cold 사본의 stderr에는 PID 12156 구간의 저장 실패 경고 16줄이 있지만
개별 시각·예외 종류·capture ID가 없다. 기존 Oct8 기록도 같은 경고를 확인했다.
이번 16개 orphan JPEG와 fact 시간 간격 대조는 관련성을 보강하며 실제 예외 원인은
여전히 미확정이다. 현재 코드에서도 `extra.error_type`이 기본 로그 형식에서 누락되므로
확인된 보완 범위는 실패 로그의 추적 가능성이다.

1. 기본 `StreamHandler`에서 실제 fact append 실패 후 다음 capture 성공을 재현한다.
2. 기존 경고 본문에 JSON으로 실패 시각, capture 시각/ID/SHA256/크기, service ID,
   실패 누계, writer 초기화/저장 단계, 예외 종류와 숫자 errno/winerror를 남긴다.
   원본 예외 문자열·URL·경로·이미지 본문·관측 스냅샷은 포함하지 않는다.
3. 큐 완료와 실패 누계의 원자성, 후속 capture 처리, 실패가 있는 정상 종료의 FAIL을
   유지한다. 잘못된 capture 시각 때문에 진단 기록이나 다음 처리가 중단되지 않아야 한다.
4. 수정 전 실패/수정 후 성공, 관련 회귀와 최종 `npm run health`를 실제 exit와 기록한다.

통과 기준은 회복 후에도 로그 하나로 실패한 고립 이미지 바이트를 식별할 수 있는 것이다.
저장 방식·자동 복구·서버 설치는 이 변경에 포함하지 않는다. R5 원인 판정은 HOLD다.

## 2026-10-13 현장 준비 패키지의 식별 계약

후보1.0.28/4cc7393e/8821746b와 현재 롤백541d701d/08C061EE를 동일 묶음에 보존한다.
`scripts/field-v1028/verify-field-package.ps1`은 외부 고정 manifest SHA와 전체 선언 파일의
잠긴 read handle로 정확한 목록·크기·SHA·미서명 상태·기존 payload/backend/QA 출처를 검사한다.
파일 경로와 실제 reparse, 변조된 버전/출처 및 승인 주장도 거부해야 한다.
성공 범위는 전달 패키지 확인이며 installed tree/현장 QA와 분리한다. 성공 시에도
설치·canary·승격 false/HOLD다. 자동 설치·HTTP·프로세스/설정 변경은 포함하지 않는다.
같은 잠긴 도구 바이트를 실행하는 launcher와 전체 현장 수집·판정은 후속 단계다.
정상2·부정16 실행과 서버 최종 경로/파일 존재 근거는
[패키지 보고](../../04-report/production-release-risk-validation-field-package-20261013.report.md)에 기록한다.

### 같은 잠금 바이트 실행과 결과 보존

`invoke-field-package-read.ps1`은 전달 검증기56144abd와 manifest58012882를 고정한다.
관리자 네이티브 PS5.1에서 새 결과 자식 폴더만 만들고 부모/패키지/운영본은 변경하지 않는다.
외부 고정 SHA의 bootstrap이 컨트롤러를 잠가 읽고, 컨트롤러의 새 자식 프로세스도 검증기를
잠금→길이/SHA 확인→동일 스트림 UTF-8 해석→ScriptBlock 실행 순서로 처리한다.
해시 뒤 `-File`로 경로를 다시 열어 실행하지 않는다. 부모와 자식의 입력 경로를 검사한다.
결과 ACL은 Administrators/SYSTEM 쓰기와 운영자 읽기이며 기존 경로·reparse·240자 초과를 거부한다.
stdout/stderr/구조화 결과/manifest를 새 파일로 쓰고 결과 경로·manifest SHA를 콘솔에 출력한다.
120초 상한은 이 도우미가 직접 만든 검증 자식에만 적용하며 앱 프로세스는 제어하지 않는다.
검증 기준: 정확한 바이트 실행, 변조/경로 거부, 실행 중 쓰기·삭제 잠금, 실패/timeout의 HOLD,
결과 원문·해시·새 경로/ACL·재실행 보존, 비관리자 무변경 거부다. 개발 PC 권한 치환 fixture와
실제 관리자 서버 실행을 구분하며, 후자가 끝나기 전 서버 hash 검증 완료로 표시하지 않는다.

### 현장 HTTP 계측의 독립 주기와 전체 응답 경계

`field_http_sampling.py`는 후속 현장 collector에서 사용할 loopback HTTP 수집 모듈이다.
health2초/data6초/image250ms 각각 단일 worker와 같은 monotonic 원점을 사용한다.
느린 이미지·본문 해석·결과 쓰기가 다른 endpoint의 예정 요청을 직렬로 막지 않는다.
각 worker는 요청을 겹치지 않게 하고 지나간 슬롯을 누락 기록으로 남긴다. 지연 뒤 burst로
과거 슬롯을 메우지 않는다. 첫 요청·최대·분위수·HTTP 실패·timeout·스케줄 지연을 보존한다.

연결·송신·헤더 대기·본문 수신과 JSON/JPEG 해석을 분리한다. socket의 각 blocking read에
단일 요청의 남은 deadline을 적용하여 조금씩 계속 들어오는 헤더/본문도 무한 대기하지 않는다.
전체 본문을 받지 못한 성공 상태 코드, 길이 부족, 잘못된 JSON/JPEG, 크기 상한 초과는 실패다.
부분 본문·원시 헤더·해시·실제 시각을 새 파일로 보존하고 같은 출력 경로를 재사용하지 않는다.
출력/메모리 예산 초과·worker 실패·수동 중단은 불완전 수집으로 기록한다.

이 모듈의 시험은 loopback fixture에서 독립 주기, 느린 헤더/본문의 전체 deadline, 누락 슬롯,
첫 실패 포함 요약, 중단, 파일 충돌과 원문 해시를 확인한다. 제품 실행/종료·장비 요청·설치는 없다.
실제 서버 실행 entrypoint는 아직 제공하지 않는다. 최종 build/프로세스/logger/fingerprint 결합,
보호된 결과 폴더·잠긴 배포 실행, resource/physical disk/web vitals/packet·정상 종료와 합쳐야
전체15분/120분 collector가 된다. HTTP 모듈 성공에도 전체 현장 gate는 NOT_EVALUATED/HOLD다.

요약은 단순한 배열 길이 대신 고유 sequence coverage를 확인한다. NaN/Infinity/음수/bool/null
시간값, 중복·누락 순번은 NOT_MEASURED이며 첫 실패 표본을 삭제하지 않는다. 정상6.2초
fixture의 기본 주기와 느린 이미지에 대한 독립성을 별도로 검사한다. 이 설계의 수집/쓰기
오버헤드는 최종 field collector의 실제 부하 검증에 포함하며 기존 보조 계측 결과로 대체하지 않는다.

### 5.5 프로세스·물리 디스크 및 같은 관찰 시작 시각

`field_resource_sampling.py`는 PID/create-time/exe로 루트를 고정하고 관찰된 자식별 CPU·메모리·
스레드·핸들·I/O를 읽는다. PhysicalDrive는 Windows 원시 DISK_PERFORMANCE와100ns 단위를
보존한다. host 전체 물리 디스크와 프로세스 I/O, RSS 합과 고유 물리 메모리를 구분한다.
구성 변경·읽기 실패·비정상 수치·카운터 감소·누락·중단은 유효 변화량이나 성능 PASS가 아니다.
기본5초·준비120초·관찰300초·최소48표본/240초와 최종 파일 경로240자 예산을 적용한다.
같은 future monotonic origin을 HTTP와 자원 worker에 전달하며 원문에 각자 기록한다.
동기 Windows 조회의 외부 watchdog은 현장 launcher 통합에서 필요하다.

[자원 수집 시험](../../04-report/production-release-risk-validation-resource-collector-20261013.report.md)의
개발 PC420초 관찰에서85/관찰61표본과 두 디스크를 확보했으나 HTTP health1/image17 슬롯이
누락됐다. fetch/해석 반환 후의 지연까지 좁혔으며 정확한 저장/스케줄링 원인은 미확정이다.
HTTP `writes.json`은 원시 파일별 open/write/flush/fsync/close 시간을 보존한다.
계측 추가가 누락 수정 또는 최종 통합/현장 QA 통과를 뜻하지 않는다. native API의 카운터
활성화 효과와 단위·범위·프로세스/장치 식별 한계도 보고서와 결과에 기록한다.

### 5.6 느린 원문 저장과 요청 주기의 분리

HTTP 응답/해석 뒤의 원문·JSON 저장은 하나의 전용 worker로 처리한다. 대기열 기본 한도는
256레코드·직렬화된 metadata+body64MiB이며 저장 중 레코드도 계산한다. 초과 시 수집을 실패로
중단하고 일부 미보존 슬롯을 PASS로 세지 않는다. 전체 body4GiB 예산도 별도로 유지한다.
요청 worker는 비중첩·원래 주기를 유지하며 밀린 요청을 연속 실행하지 않는다.
저장 worker가 body→metadata를 각각 flush/fsync/close한 뒤에만 해당 요청을 persisted로 센다.
수동 중단도 이미 수락한 자료를 배출한 뒤 FAIL을 기록한다. 저장 실패는 생성된 부분 파일의
실제 크기/해시·failed_write 표시와 오류를 보존하고 성공 판정을 차단한다.
대기/최대 적체·제출/저장/폐기 수·배출 시간·파일별 저장 시간을 분리한다. 아직 메모리에 있는
대기 자료는 내구성이 확정되지 않았으며 프로세스 손실 시 완전한 manifest가 성립하지 않는다.
동기 파일/드라이버 호출이 무기한 멈출 경우의 외부 watchdog은 현장 launcher 통합 조건이다.
검증과 실패 기록은 [저장 분리 보고](../../04-report/production-release-risk-validation-persistence-20261013.report.md)에 연결한다.

### 5.7 설치 파일과 관찰된 실행 식별값의 결합

`field_installation_binding.py`는 고정 reference SHA의 후보 payload 전체 기본 스트림과
clean provenance를 확인하고 read-sharing 핸들을 컨텍스트 종료까지 유지한다.
NSIS 추가 파일은 별도 출처의 정확한 크기/SHA가 있어야 허용한다. 경로·reparse·hardlink·
파일 집합·바이트 제한을 적용하며 종료 전 `recheck()`로 이름/ID/해시를 다시 대조한다.
OS의 PID/create-time/exe, main→backend 관계, IPv4/IPv6 listener 소유자를 health GET 앞뒤로
읽고 version/frozen/REAL/build, SPOT/CSV logger UUID를 결합한다. 모호함·권한 오류·
서비스 교체는 FAIL이다. raw body와 HTTP 계측을 보존하며 식별용 첫 GET도 전체 성능 판정에 포함한다.
이 구성요소의 PASS는 표본의 식별 범위이며 서버 전체/실행 메모리/표본 사이 무변경의 증거가 아니다.
최종 fingerprint·authenticated backend generation·watchdog·화면/packet/종료 경계와의
전체 collector 통합은 계속 필요하다. 개발 PC23시험, 실제 추출1814파일 및 기존15표본 파서
검증의 범위는 [식별 결합 보고](../../04-report/production-release-risk-validation-installation-binding-20261014.report.md)에 기록한다.

### 5.8 같은 관찰 구간과 계측 프로세스의 종료 범위

`field_observation.py`는 초기 설치/실행 식별 검사를 통과한 뒤 하나의 future monotonic 원점으로
HTTP·자원·OS 식별 조회를 각각 별도 프로세스에서 실행한다. 첫/마지막 식별용 health GET과
관찰 중 모든 health 본문에 같은 SPOT/logger UUID·build·backend 경로를 요구한다.
원문 manifest의 정확한 파일 집합·크기·SHA를 재검산하고 자원 표본마다 backend 식별값을 확인한다.
작업 종료 전에 설치 payload를 다시 검사한다. 짧은 개발 시험의 자원 범위는 NOT_MEASURED이며
420초 이상 관찰은 기존 준비120초/측정300초 coverage 조건도 만족해야 한다.

Windows 대기 함수 반환 뒤 monotonic deadline을 다시 확인하여 예정 시각 전 요청을 방지한다.
HTTP 요청과 동기 native 조회는 별도 Python 프로세스에 둔다. GIL을 유지한 native 호출350ms의
제어된 재현은 이전 thread 구조의 이미지4슬롯 누락과 새 구조의 누락0을 확인했다.
이 결과를 기존 서버 timeout/drop 또는 주입하지 않은 host 지연의 원인 확정으로 확대하지 않는다.

`field_windows_job.py`는 새 감독 자식의 생성 HANDLE을 이름 없는 Windows Job에 등록한 뒤
실행 gate를 연다. 기존 관찰 대상 앱은 Job에 넣지 않는다. 준비/최종화 예산은 각각 최대180초,
관찰은 최대7200초이며 finalizing 이벤트가 전체 deadline을 연장하지 않는다.
종료·시간 초과·감독 프로세스 손실 때 Job의 계측 자식만 정리하고 실제 앱은 계속 실행한다.
IPC 누락/과대 frame·해시 불일치·원문 손실·첫 health 지연·서비스 교체·중단은 FAIL/HOLD다.
부모의 결과 쓰기까지 감싸는 보호된 외부 launcher, generation/fingerprint, 화면/packet/정상 종료
증거와 실제 서버 설치/복구/15분/120분 QA는 여전히 필요하다. 이 API는 서버 실행 entrypoint가 아니다.

### 5.9 인증된 백엔드 세대의 시작·종료 경계

`field_generation_binding.py`는 잠긴 payload와 main/backend 경로를 확인한 후 OS 식별·listener를
대조한다. 선택한 backend의 환경 API에서 embedded 표시·control token·generation만 사용한다.
환경 사전 전체나 token/request header를 결과로 보존하지 않는다. 환경 조회 앞뒤와 GET 뒤의
OS 식별값을 대조하고 접근 거부·프로세스 변경·누락 값은 실패로 처리한다.
토큰을 보낼 수 있는 곳은 고정 `127.0.0.1:<확인한 포트>/api/control/health`의 GET뿐이다.
기존 전체 요청 deadline과 크기/JSON 제한을 사용하며 redirect는 따라가지 않는다.
응답에 토큰 원문·대소문자 변형·ASCII JSON unicode escape가 있으면 본문/헤더를 보존하지 않고 FAIL이다.
환경 조회 예외는 타입만 기록하여 provider가 포함한 민감 문자열의 전달을 막는다.

실제 후보 소스의 PID·32자리 generation·12자리 session·UTC 시작 시각 계약을 검사한다.
첫 인증 GET과 종료 인증 GET은 각각200ms 조건을 적용하며 같은 identity를 요구한다.
첫 인증 실패는 주기 관찰을 시작하지 않고, 종료 실패는 전체 관찰을 FAIL로 남긴다.
이 검사는 시작·종료 경계 표본이며 모든 중간 순간의 증거는 아니다. 장비 fingerprint/attestation,
보호된 외부 실행기·화면/packet·정상 종료/최종 delta·실제 현장 QA는 별도로 남는다.

### 5.10 최종 설정 기준과 runtime fingerprint의 경계 대조

2026-10-14 사용자 승인에 따라 `sfl-field-configuration-disabled-low-signal-v1` 기준을 추가한다.
기존 v1 기준의 comparator=true 조건은 유지한다. 추가 기준은 승인된 관찰 프로파일 SHA와
시험 순서 승인 SHA `6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685`,
Low Signal off, configured/effective comparator=false를 모두 요구한다. 다른 검사는 동일하다.
기준 JSON의 외부 고정 SHA를 먼저 검증하고, 해당 승인 SHA/전용 schema를 확인한 reader만
검증 범위를 담는 ReferenceSnapshot을 만든다. 장비 HTTP JSON의 추가 필드는 제한 모드를
선택할 수 없다. 이후 runtime·정상 종료 검사는 같은 기준 객체와 정확한 fingerprint를 대조한다.
결과에 DISABLED_LOW_SIGNAL_FIELD_TRIAL·physical NOT_TESTED·formal QA HOLD를 명시하며
수집/데이터 구성요소의 PASS를 정식 QA PASS로 확대하지 않는다. 기본 경로와 거부 검사를
함께 검증하고 설정 도우미의 한정 확인 경로도 같은 승인·미검증 상태에 결합한다.

최종 후보의 실제 attestation에서 작성한 설정 기준 JSON을 외부 SHA로 잠가 읽는다.
기준은 승인된 관찰 프로파일 기록의 SHA와 연결하고, USER_SELF의 최종 fingerprint/설정 SHA,
build·운영자 확인·UTC 시각·readback/comparator 상태를 포함한다. 현재 존재하는 운영본의
fingerprint_mismatch를 고치거나 승인 기록만으로 최종 기준을 자동 생성하지 않는다.
테스트용 기준과 실제 최종 기준은 구분하며 보호된 launcher가 실제 기준 SHA를 고정해야 한다.

`/api/spot/config`의 image 진단에서 제품 소스와 동일한22개 fingerprint 입력을 선택해
canonical JSON SHA256을 재계산한다. 필수 값/타입·프로파일의 소프트웨어 대응 필드·별칭을
검사하고 불일치·미검증·drift·기준 변경은 실패로 남긴다. 원문과 판정 이유를 보존한다.
설정 GET 앞뒤 OS 식별·같은 SPOT 서비스와 관찰 시작/종료의 고정 기준을 결합한다.
초기 실패는 주기 수집 전 중단하고 종료 실패는 관찰 전체를 FAIL로 남긴다.
설정 endpoint의 임의 성능 상한을 새로 만들지 않으며 기존 전체 요청 timeout을 적용한다.
이 검사는 API가 보고한 설정과 attest 정보의 무결성/일치다. 물리 장비 readback·comparator
실증·기준의 실제 승인 확인·정상 종료 metadata와의 최종 대조를 대신하지 않는다.

### 5.11 관찰 종료 health와 정상 종료 sidecar의 연결

관찰 마지막의 검증된 health 원문에서 build·logger UUID·schema·현재 CSV 파일명·마지막
sample 번호를 추출하고 원문 SHA와 함께 `shutdown-expectation.json`으로 보존한다.
필수 값 누락·잘못된 타입·경로·원문 해시 불일치는 관찰 실패다. 후속 보호된 실행기는
성공한 감독 결과와 이 파일의 해시를 연결해야 하며 파일 자체를 현장 승인으로 취급하지 않는다.

`field_shutdown_binding.py`는 이 기대값의 정확한 CSV/sidecar 이름만 읽는다. 최신 시각이나
glob의 첫 파일로 대체하지 않는다. 기본 스트림을 읽기 공유로 잠그고 크기·SHA·파일 식별을
전후 대조하며 pinned 최종 설정 기준도 함께 유지한다. sidecar 양쪽 build/logger, schema,
hardening, finalized=true, reason=shutdown, final sample>=관찰 sample 및 설정 fingerprint/
attestation을 검사한다. `persisted_at`은 마지막 저장 시각으로만 검증하며 종료 시각으로
해석하거나 관찰 이후여야 한다는 조건을 만들지 않는다.

성공 범위는 관찰 기대값과 종료 파일의 식별/설정 연결이다. 정상 종료 실제 수행/프로세스 소멸,
CSV 전체 행·fact/image 연결 검사는 별도다. PASS에도 field/full CSV/normal shutdown gate는
NOT_EVALUATED이고 release는 HOLD다. 앱 종료·설치·설정 변경은 이 모듈에 포함하지 않는다.
최종 caller는 이 결과의 파일 해시와 full validator가 읽은 바이트를 다시 결합해야 한다.

검증은 합성 기준과 native 파일 잠금, 누락/교차 logger·build·파일·sample·schema·미완료 종료,
설정 변조 및 실제 보존 I4/I5 후보 sidecar를 사용한다. 실제 기록의 미검증 attestation은 FAIL로
유지한다. 기존 CSV validator의 opt-in `--require-current-server-promotion-profile`은 특정
과거 운영값(comparator verified=false 포함)의 회귀 조건이다. 최종 QA 실제 호출처럼 일반
CSV 계약을 검사하고 별도의 최종 pinned attestation 조건을 적용하며 과거 상수는 바꾸지 않는다.

### 5.12 전체 CSV 계약과 JPEG 바이트 검사의 별도 실행 파일

기존 `validate_spot_image_files.py`를 후보4cc의 clean source와 잠긴 의존성 환경으로 패키징한다.
제품/설치본과 기존 CSV 검사기 바이트는 변경하지 않는다. frozen 실행의 `__file__` 해시 기록을
유지하기 위해 같은 원본 스크립트를 데이터로 동봉하고, 실행 결과의 tool SHA도 대조한다.
빌드 전후 전체 tracked source·의존성·installer SHA와 새 EXE provenance를 보존한다.

실제 보존 I4/I5 종료 사본의 이미지 subtree와 fact를 전수 검사한다. 외부에서 고정한 원본
목록/크기/SHA를 복사 전후 확인하며 같은 입력으로 Python과 EXE의 요약·판정을 비교한다.
복사본에만 이미지 누락·바이트 변조·fact와 SHA를 맞춘 디코딩 불가 파일·고립 파일·최종
manifest 불일치를 주입한다. 기존 CSV 검사기만 통과하는 이미지 오류와 별도 이미지 검사만
통과하는 manifest 오류를 보존한다. 두 결과를 함께 사용하며 어느 한 검사로 전체 QA를 대신하지 않는다.

이 단계는 도구 준비와 보존된 격리 후보 자료의 검증이다. 전체 운영 데이터/실제 장비/현장
승격 PASS가 아니다. CSV의 부가 fact 경로 소비 범위, 잠긴 입력과 결과/정상 종료의 연결,
보호된 실행기·서버 로컬 전달/실행 및 실제15분/120분 조건은 후속 통합에 남긴다.

구현 확인: portable 이미지 묶음의 서버 로컬 전달/파일 존재는 2026-10-14 r2 영수증으로
확인했다. 서버 로컬 해시·실행 및 보호된 통합 실행기 전달은 아직 미완료다.

### 5.13 CSV 검사기의 모든 데이터 입력 경로 결합

최종 종료 자료에서 선택한 v1/v2/metadata/관찰 fact/이미지 fact/최종 manifest와 선택적
posthoc fact/report를 외부 고정 목록의 SHA·크기에 대조하고 Windows 읽기 공유 핸들로 유지한다.
원본 metadata는 변경하지 않는다. 검사 전용 새 metadata는 posthoc의 fact_path/report_path만
잠긴 사본 경로로 바꾸며 원본·파생본 해시와 정확한 변경 목록을 보존한다. 그 외 모든 필드의
동등성을 확인한다. posthoc CLI override는 SHA/행 수 실패 조건을 완화하므로 사용하지 않는다.

선택적 fact가 외부 목록에 없고 원본 manifest가 row_count=0/sha256=null인 경우에만 부재를
허용한다. 잠긴 일반 파일을 부모로 하는 불가능한 자식 경로로 연결해 검사 중 파일 생성이나
부모 교체가 불가능함을 native Windows에서 검증한다. 값이 없는 fact 파일을 합성하지 않는다.
일치하지 않는 이름·미선언 파일·nonempty manifest·단독 linkage 파일·잘못된 JSON은 거부한다.
기존 CSV 도구가 강제하지 않는 linkage manifest의 report_sha256은 잠긴 report 바이트와 별도로 대조한다.

실제 고정 CSV EXE를 같은 잠금 구간 안에서 실행해 보존 I4/I5 사본, 외부 경로의 오염 파일,
선택적 fact의 올바른/잘못된 행 수·SHA, 최종 manifest 실패를 확인한다. context 종료 오류는
실행 exit0이어도 바이트 결합 PASS가 될 수 없다. 이 모듈은 CSV 입력/소비 경계만 담당한다.
이미지 바이트 검사·정상 종료·attestation·보호된 외부 실행기·최종 현장 QA는 함께 연결해야 한다.
`shutdown_csv_inputs`는 앞서 관찰한 종료 기대값과 고정 설정 기준을 같은 잠긴 원본 metadata에
적용한 뒤에만 명령을 노출한다. 실제 보존 attestation FAIL은 유지하고 합성 기준의 PASS와 구분한다.

### 5.14 종료 사본 CSV·이미지 검사와 자손 종료의 단일 흐름

CSV 입력 context와 동일 image fact를 사용해 전체 선택 이미지 subtree의 고정 목록을 대조하고
각 기본 스트림과 이미지 EXE를 읽기 공유로 잠근다. 이미지 도구의 실행 전후 inventory도
외부 고정 목록과 정확히 대조한다. 새 미선언 파일·누락·경로 교체·출력 불일치는 실패다.
선택 입력의 출처/승인과 서버 전체 snapshot 증명은 외부 실행기의 책임으로 유지한다.

두 고정 EXE는 새 gated worker를 Windows Job에 등록한 뒤 순차 실행한다. 원문 stdout/stderr,
실제 exit와 worker exit, Job 잔존/강제 종료 여부를 보존한다. 시간·출력 예산 초과나 자손 잔존은
FAIL이며 새 검사 자손만 정리한다. CSV·이미지 내용 검사와 두 입력 context 종료를 모두 통과한
뒤에만 선택한 종료 사본 검사 PASS를 기록한다. 실제 종료 기대값/최종 설정을 필수로 받는
상위 API와 데이터 소비 자체의 시험 API를 구분한다. 전체 현장/출시 gate는 계속 HOLD다.

보존 I4/I5 이미지133/199개와 CSV를 함께 실행하고, 누락/변조/고립 이미지·잘못된 manifest,
새 파일·잘못된 도구 출력·worker timeout/자손 잔존/감독자 손실을 검사한다. 기존 앱이나
운영 설정은 변경하지 않는다. 실제 현장 물리 attestation·보호된 launcher 통합은 별도로 남는다.

### 5.15 외부 고정 요청과 보호된 실행 진입점

관찰(900/7200초)과 종료 사본 QA를 명시한 request JSON을 외부 SHA로 고정해 읽는다.
기존 후보/도구 해시·UNSIGNED_INTERNAL 정책을 유지하며 요청 자체를 승인 근거로 해석하지 않는다.
원문 요청·단계 결과·최종 파일 목록/SHA를 새 결과 아래 보존한다. 오류/미완료를 PASS로 만들지 않는다.
frozen 실행은 multiprocessing.freeze_support를 적용하고 기존 Python API와 같은 조건으로 검증한다.

관리자 PS5.1 실행기는 새 결과 자식에만 보호 ACL을 만들고 운영자 읽기 권한을 보장한다.
고정 EXE·요청·동봉 파일을 잠근 뒤, EXE를 suspended 상태로 만들어 이름 없는 Job에 등록하고
나서 실행한다. PyInstaller bootstrap 자식도 포함하며 실제 앱은 Job에 넣지 않는다.
stdout/stderr를 새 파일로 저장하고 시간·출력·잔류 자손·실제 exit를 확인한다. 부모 손실 때도
검사 자손만 정리한다. 기존 부모 ACL·설치·설정·운영 데이터는 변경하지 않는다.
보호된 실행과 각 단계 결과를 실제 관찰→정상 앱 종료→전체 새 사본/QA로 연결하는 현장 절차는
별도 검증 대상이며 물리·UI/packet·승격 조건을 이 진입점의 PASS로 대신하지 않는다.

### 5.16 요청별 health 처리 구간의 선택적 계측

이 절은 최초 v1 계측의 범위다. 현장 연결에 사용할 현재 계약은 아래5.17의 native anchor를 포함한 v2다.

현장203.1356ms 표본은 기존500ms worker 로그에 남지 않으며 executor 대기와 event loop 복귀를
분리할 수 없다. `/health`의 기존 응답 본문·500ms 로그·200ms 실패 기준은 유지한다.
명시적인 로컬 진단 요청에만 `X-SFL-Health-Timing` 응답 헤더를 추가한다.

요청 조건은 `X-SFL-Health-Probe` 하나에 소문자32자리 hex ID, ASGI peer의 literal loopback IP,
Origin/Referer 헤더 부재다. 부적합한 진단 표시는 일반 health로 처리한다. 별도 인증 수단이나
외부 접근 통제를 대신하지 않는다. 전역 상태·파일 기록·장비 제어·추가 worker pool은 만들지 않는다.
요청마다 독립 객체를 쓰고 예외·취소 때 완료 헤더를 만들지 않는다.

예: 확인한 loopback `/health`에 `X-SFL-Health-Probe: 0123456789abcdef0123456789abcdef`를 보낸다.
수집기는 `fetch_sample(port, ENDPOINTS[0], health_probe_id=<새 uuid4 hex>)`로 지정하며,
응답 원문 헤더·본문·해시와 요청 ID를 보존한다. ID 미지정 시 기존 수집 동작을 유지한다.
수집기의 HTTP 성공은 timing 지원·정합성을 뜻하지 않는다. 해석 시 헤더가 정확히 하나인지,
v=1·probe_id 일치·clock·양의 정수 PID/TID·아래 모든 checkpoint의 단조 순서를 별도로 검증해야 한다.
누락되거나 다른 schema/ID인 자료를 시간0으로 채우거나 PASS로 해석하지 않는다.

| checkpoint 차이 | 포함하는 벽시계 구간 |
| --- | --- |
| worker_enter − submitted | executor 제출과 worker 시작 사이; 정확한 queue-only 시간은 아님 |
| plc_done − worker_enter | PLC health 조회 및 진입 계측 |
| runtime_done − plc_done | runtime 정보 조회와 경계 계측 |
| frontend_done − runtime_done | frontend 상태 조회와 경계 계측 |
| worker_exit − frontend_done | 기존 느린 응답 로그·payload 조합 등 나머지 worker 처리 |
| route_resume − worker_exit | worker 반환·future 전달·event loop 복귀 |

헤더는 v/probe_id/pid/loop_tid/worker_tid/clock/checkpoints로 구성하며,
checkpoint 순서는 route_enter, submitted, worker_enter, plc_done, runtime_done,
frontend_done, worker_exit, route_resume다. clock은 Python `perf_counter_ns`이고 단위는 ns다.
route_enter는 진단 요청 조건을 확인한 직후이므로 그 앞의 헤더 검사 시간도 포함하지 않는다.
고정 필드와 검증한 hex ID만 포함한다. 단계 사이 시간에는 OS scheduling·GIL/lock 대기·계측 비용이
포함될 수 있으므로 정확한 CPU 시간이나 특정 원인으로 자동 분류하지 않는다.
route_resume 뒤의 JSON 직렬화·middleware·socket 전송 및 route 진입 전 처리는 포함하지 않는다.
PID/TID만으로 세대를 확정하지 않으며 현장 적용 때 native 생성 식별자와 설치본 identity가 필요하다.
ETW QPC와 직접 같은 수치라고 가정하지 않고 같은 실행의 clock anchor와 trace coverage를 검증한다.

검증은 일반/잘못된/외부/브라우저 표시 요청, 동시 요청, 오류·취소, worker pool 포화,
각 처리 단계와 event loop 복귀 지연을 포함한다. 실제 loopback HTTP 시험은 장비 서비스 lifespan을
끄고 조회값을 격리해 수행한다. 이 변경은 새 제품 소스이며 기존4cc 설치본·고정 도우미를 수정하지 않는다.
실제 장비·frozen 설치본·현장 성능 검증과 배포는 별도이고 출시 HOLD는 유지한다.

### 5.17 health v2의 native 생성 식별자와 시계 연결

v1의 PID/TID 숫자만으로는 재사용을 판별할 수 없고 perf_counter_ns와 ETW QPC를 직접 같다고
해석할 수 없다. 명시적 진단 요청의 v2 헤더에 loop_begin/worker_begin/worker_end/loop_end
네 native anchor를 추가한다. 각 anchor는 현재 process/thread의 GetProcessTimes/GetThreadTimes
생성 FILETIME, PID/TID, QueryPerformanceCounter/Frequency와 그 호출 전후 perf_counter_ns다.
현재 process/thread pseudo-handle만 사용하며 새 handle·trace session·writer를 만들지 않는다.
일반 health에는 native 호출이 없다. native API 실패는 status=UNAVAILABLE와 오류 타입만 반환하고
health 본문/HTTP 성공 여부를 바꾸지 않는다. 진단의 완료 여부는 수집기에서 별도로 판정한다.

`field_health_timing.validate_health_sample(record, raw_body, probe_id=..., backend_pid=...,
backend_created_filetime=...)`의 입력 backend 세대는 외부에서 확인한 값이어야 한다.
응답 헤더의 PID/생성 시각을 그대로 기대값으로 복사하면 외부 세대 검증이 되지 않는다.
프로세스/설치본 선택·listener·세션·고정 payload 검사는 기존 외부 수집 흐름의 책임이다.
로컬 별도 프로세스 시험에서는 자식 PID와 WindowsProcessReader의 요청 전후 생성 FILETIME을 대조한다.

소비 검사는 원문 본문·헤더의 크기/SHA, 단일 timing 헤더(ASCII4096bytes 이하), 정확한 v2 필드,
중복 JSON key/비유한 수 거부, 소문자32자리 요청 ID, 정수 PID/TID/시각,8개 checkpoint 순서를 요구한다.
native 네 anchor의 process 생성 시각은 외부 기대값과 같아야 하고, loop/worker 각각 전후 thread
생성 시각이 같아야 한다. 각 anchor는 대응 처리 단계 안에 있어야 한다. collector의 기존 native
begin/end도 원본에서 다시 검증하며 결과에 적힌 CORRELATABLE_BOUNDARIES만 신뢰하지 않는다.

여섯 anchor 모두 같은 QPC frequency를 요구하고 각 대응점에서 얻은 offset 구간의 교집합을 구한다.
QPC 환산에는 정수 나눗셈의 보수적 floor/ceil을 사용한다. 교집합이 없거나 시간 순서가 뒤집히면
NOT_CORRELATABLE이며 stage 값·QPC 연결을 노출하지 않는다. 성공 이름은
REQUEST_AND_NATIVE_CLOCK_BOUND다. 정확한 CPU 시간, ETW coverage, 특정 지연 원인 또는 현장 QA PASS를
뜻하지 않는다. 이전 v1 원문은 보존하고 v2 소비기의 입력으로 재해석하지 않는다.

검증 예시: 유효한 요청을 복제해 worker_end의 thread 생성 FILETIME만 바꾸거나 QPC를 다른 epoch로
옮긴다. 헤더 SHA를 그 변형 바이트에 맞춰 갱신해도 각각 세대/clock 검사에서 거부돼야 한다.
같은 PID·TID를 적은 것, HTTP200, 해시 일치만으로 이 조건을 대신할 수 없다.
clock의 FILETIME은 생성 식별자이며 ETW event timestamp나 QPC의 epoch가 아니다.
native 조회 비용은 진단 요청의 경과 시간에 포함되고 worker_begin의 조회는 PLC 구간에 포함된다.
loop_end 조회와 헤더 직렬화 이후 전송 시간은8개 checkpoint 밖이다. 이 비용과 한계를 결과 해석에 유지한다.

근거: [Python3.12 시간 함수](https://docs.python.org/3.12/library/time.html#time.perf_counter),
[Windows GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes).
문서의 system-wide 성질만으로 과거 다른 실행을 연결하지 않고, 실제 같은 요청에서 수집한 native
대응점과 프로세스 생성 식별자를 확인한다. 최종 패키지와 현장 적용은 별도 검증한다.

### 5.18 1.0.29 교체의 새 전체 백업 생략 경로

2026-10-15 사용자는 진행에 무리가 없으면 새 백업 없이 진행하라고 지시했다.
4cc→acaf 제품 차이는 선택적 health 계측과 버전 변경이며 데이터 저장·설정 이관 코드는
변경되지 않았다. 동일 installer의 격리 업그레이드/복귀에서 설정·데이터 보존을 확인했다.
따라서 이번 교체에는 새 전체 데이터 사본을 만들지 않고 정상 종료 후 원본의 전후 검사를
사용한다. 기존 백업·복귀 installer·실패 증거는 보존한다. 이는 일반적인 백업 금지 정책,
데이터 손실의 무위험 보장 또는 전체 데이터 QA 완료가 아니다.

새 관찰 manifest는 두 운영 AppData 루트의 정확한 경로, 파일/폴더 목록, 기본·이름 있는
NTFS 데이터 스트림 길이/SHA256, 생성·수정 시각, 속성과 owner/group/DACL을 기록한다.
읽기 전용 파일 핸들·reparse 거부·파일 길이/메타데이터 재확인·주기적 cold guard를 유지한다.
manifest는 운영 루트 밖 새 보호 결과 폴더에 생성하고 외부 SHA256으로 결합한다.
원본 외에 복구 가능한 데이터 사본은 생성하지 않는다. manifest 검사는 변경을 발견할 뿐
손실 데이터를 복원하지 못하며, 백업 완료 상태나 기존 copy manifest로 표시하지 않는다.

실행 순서와 성공 조건:

1. 현재 native 실행 세대·health/build·scope를 확인하고 READY 후 기존 UI로 정상 종료한다.
2. 동일 세대 종료 영수증과 process/port 부재를 검토한다. 정상 종료가 확인되지 않으면 설치하지 않는다.
3. 닫힌 원본 manifest 작성·재검산을 완료한다. 내용/목록/추가 스트림/메타데이터 불일치는 HOLD다.
4. 새 request는 관찰 결과·manifest·정상 종료 검토·정확한 기존/후보 payload·복귀 installer를 결합한다.
   구 backup 필드를 가짜 값으로 채우거나 기존 copy 검사를 비활성화하지 않는다.
5. 설치 직전 manifest와 원본을 다시 대조하고 같은 installer를 한 번만 실행한다.
   설치 후 payload/등록/전체 원본 manifest를 확인한 뒤 일반 사용자 시작을 별도 수행한다.
   관찰 결과의 원래 시각은 변경하지 않는다. 사용자 입력 대기로 관찰 후 180분이 지난 경우에도
   검토된 종료 세대와 고정 manifest를 기준으로 내용·목록·스트림·메타데이터를 다시 전수 대조한다.
   이 재검산이 성공한 시점부터 단조 시계로 120초 이내에만 설치를 시작한다. 변경·cold guard 실패·
   재검산 후 지연은 설치 전 HOLD다. 미래 시각의 관찰 결과는 거부하며 오래된 기록만으로 설치하지 않는다.
6. 복사 공간은 예약하지 않지만 결과 manifest·설치 작업 공간과 운영 여유분은 검증한다.
   실제 NSIS 설치/복귀 및 합성 데이터 변조·추가·삭제·ADS·메타데이터 거부 시험을 수행한다.

새 관찰/설치 경로의 검증이 끝나기 전에는 서버 명령을 발행하지 않는다.
현장15분/120분, 물리 경계, 전체 데이터 오류 처리와 최종 운영 승격 조건은 유지한다.

### 5.19 새 빌드 첫 실행의 제한된 정상 종료 수집

`observe-health-runtime-close.ps1`는 1.0.29의 현재 logger·CSV·설정 원문 SHA를 외부 요청으로 고정한다.
서버/SID/관리자/PS5.1 x64, CIM 부모 관계, 실행 경로와 8000 listener를 확인하고,
각 프로세스의 native handle을 보유해 생성 FILETIME과 실제 종료 코드를 같은 OS 객체에서 얻는다.
health와 전후 OS 관찰이 일치할 때만 READY를 출력하고 최대 450초 동안 정상 UI 종료를 기다린다.
강제 종료·앱 시작·설치·설정 변경·전체 백업은 수행하지 않는다. 타임아웃·비정상 종료는 HOLD다.
정상 종료 뒤 process/port 부재, 설정 SHA 불변, 동일 logger/build의 finalized shutdown metadata를
확인한 후 현재 CSV(최대 128MiB)·metadata·설정과 영수증만 새 보호 결과 폴더에 보존한다.
기존 결과 덮어쓰기와 reparse 경로를 거부하며 운영 사용자의 읽기 접근을 유지한다.
이 단계는 파일 내용 QA·개별 저장 worker 종료 검토·새 build attestation을 대신하지 않는다.
검증 예: `powershell.exe -NoProfile -File scripts/field-v1028/test-health-runtime-close.ps1 -OutputParent <개발 검증 폴더>`.
실제 짧은 자식 프로세스의 exit 23을 포함한 로컬 native/계약 검사는 현장 정상 종료 통과와 구분한다.

2026-10-15 현장 보완: `HasExited`와 프로세스 handle의 signaled 상태는 같은 보장이 아니다.
대기 루프도 보유한 각 handle의 `WaitForExit(0)`으로 확인하고, 공통 450초 한도 안에서만 기다린다.
종료 코드가 먼저 보이는 합성 조건과 일부 handle 미종료·타임아웃 조건을 회귀 검사한다.
기존 고정 묶음은 보존하고 새 소스의 검증 결과로 이전 실행의 누락된 종료 코드를 복원하지 않는다.
`review_health_runtime_close.py`는 외부 result/request pin, 파일별 SHA·정확한 목록,
native 생성 시각·부모·포트·exit, CSV 연속 번호·logger·finalized metadata를 검토한다.
정상 result가 없으면 이 검토기를 성공 처리하지 않는다. 탐색기로 별도 회수한 CSV와 앱 종료
영수증 검토는 `native exit unverified`를 명시한 별도 범위로 남긴다.

### 5.20 1.0.29의 승인 설정 확인 기록 연결

1.0.29/acaf77d9는 설치·원본 보존 검토 후 기존 USER_SELF 승인 프로파일과 같은 canonical
settings hash를 보였다. build 식별자만 바뀐 fingerprint mismatch인 경우, 기존 제한된 현장
시험 승인과 실제 새 metadata/config SHA를 함께 고정해 네 attestation 필드를 갱신한다.
허용 build는 기존 4cc7393e와 새 acaf77d9 두 값으로 제한한다. 알 수 없는 build, 변경된
프로파일, 입력 hash 불일치, comparator/Low Signal 활성화는 계속 거부한다.
실행 전후 프로세스와 8000 listener 부재를 확인하며 기존 물리 경계 NOT_TESTED·정식 QA HOLD는
그대로다. 설정 파일 쓰기 복구용 사본만 보존하고 전체 백업·설치·자동 시작은 하지 않는다.
이 변경은 이전 실행의 OS exit 증거 누락을 해소하지 않으며 다음 실행의 native 관찰은 별도다.

### 5.21 재시작 후 독립된 native 실행 식별자 읽기

6초 health 진단의 요청은 재시작 이후의 실제 OS PID/생성 FILETIME과 부모·listener를 요구한다.
`observe-health-runtime-close.ps1 -IdentityOnly`는 5.19와 같은 서버·설정·logger·CSV·native
검사를 사용하고 현재 실행 식별자, health, 고정 설정 원문만 새 결과에 기록한 뒤 끝난다.
READY 출력·종료 대기·앱 종료·설정 쓰기·전체 백업은 하지 않는다. 결과는
`RUNNING_IDENTITY_CAPTURED_REQUIRES_REVIEW`이며 실제 exit 관찰은 false, 현장 QA는 미평가다.
독립 회수 검토 뒤에만 이 값으로 6초 진단 요청을 준비한다. 이전 실행의 식별자는 재사용하지 않는다.
검증 예: 같은 native 계약 테스트에서 읽기 결과의 hash/request 연결과 미종료 범위를 확인한다.

회수 후 `review_health_runtime_identity.py`는 콘솔 result SHA와 외부 request SHA를 요구한다.
정확한 5파일 목록·개별 SHA·설정 원문 pin·health build/logger/CSV를 확인하고 native 생성
FILETIME/UTC/초 값, CIM 생성 시각·부모·실행 경로, backend의 8000 listener를 대조한다.
성공은 `CAPTURED_NATIVE_RUNTIME_IDENTITY_VERIFIED`이며 관찰 시점의 식별자를 뜻한다.
현재 생존 여부는 `REQUIRES_EXECUTION_TIME_RECHECK`로 남기고 진단 실행기가 다시 검사한다.
이를 정상 종료·설정 승인·데이터 QA·현장 QA 통과로 올리지 않는다.

검토 예: `python scripts/field-v1028/review_health_runtime_identity.py --source <회수 폴더>
--result-sha256 <콘솔 SHA> --request-sha256 <전달한 요청 SHA> --launch-exit 0
--output <회수 폴더 밖 새 JSON>`을 한 줄로 실행한다. fixture/CLI 검사는
`test_review_health_runtime_identity.py`이며 실제 서버 결과 검토를 대신하지 않는다.

### 5.22 1.0.29 장기 관찰과 종료 데이터의 후보 식별 전달

6초 현장 진단 다음 단계의 900/7200초 관찰에는 같은 `acaf77d` 설치본을 사용한다.
도우미의 후보 식별을 명시적으로 전달하며 제품을 재빌드하지 않는다. 허용 후보는 기존
`CandidateIdentity`의 1.0.28/1.0.29 두 값뿐이다. 외부 요청의 commit, 관찰 spec의
`candidate_commit`, 고정 payload reference SHA가 일치해야 한다. 이전 1.0.28 요청은 spec의
새 필드가 없어도 같은 1.0.28 기본값으로 해석하며, 1.0.29 요청에서 필드 누락은 거부한다.

선택한 후보는 설치 payload·모든 health 원문·설정 기준·마지막 health에서 만드는 종료 기대값,
종료 metadata와 CSV 입력 잠금·검증기에 전달한다. host 진단도 같은 관찰 경로를 사용한다.
commit 문자열만 허용하거나 payload/설정/metadata에서 후보를 자동 추론하지 않는다.
각 단계의 hash, 정확한 파일 목록, 실행 세대, 처음/마지막 health의 200ms 조건, 시간 제한,
소유 프로세스 정리와 HOLD/미평가 gate는 유지한다. UI·packet·물리 시험도 별도 조건이다.

검증은 실제 격리 Python 프로세스와 loopback fixture를 사용해 두 후보의 관찰 및 종료
기대값을 확인하고, 후보 혼합·기준 SHA 혼합·잘못된 설정/metadata·느린 첫 health를 거부한다.
기존 관찰/runner/종료/CSV/닫힌 데이터 회귀도 실행한다. 이 검사는 합성 개발 검증이며
서버 전달·동일 설치본의 실제 15분/120분과 전체 데이터 QA를 대신하지 않는다.

6초 전용 `HealthCollectionSpec`은 기존처럼 1.0.29만 허용한다. 상위 spec의 새 필드가
기존 6초 요청을 깨뜨리지 않도록 이 전용 경로의 기본값은 1.0.29로 고정하고,
명시된 다른 후보는 수집 전에 거부한다. 기존 고정 요청 파일은 변경하지 않는다.

사용자가 32비트 PowerShell에서 시작해도 launcher는 `Sysnative`를 통해 64비트
Windows PowerShell 5.1을 선택한다. 64비트 시작 창에서는 `System32`를 사용한다.
패키지 시험에서 두 시작 창의 실제 실행·종료 코드와 잘못된 hash 거부를 확인한다.

### 5.23 GC 검사 비용을 줄이는 화면 이력 보관

같은 요청의 독립 CPU 스택 검산과 격리 재현 근거는
[2026-10-16 GC 진단](../../04-report/production-release-risk-validation-cpu-outlier-20261016.report.md)에 있다.
이는 자동 GC가 관찰된 요청에 크게 관여한 근거이며, 서버의 특정 객체나 모든 과거 지연의
원인을 확정하지 않는다. 실제 구현과 패키지·현장 검증을 거쳐 개선 효과를 판단한다.

`PLCService.history`는 각 항목의 timestamp_ms, sequence, recorded_monotonic과
공개 `FactoryData` JSON 문자열만 담는 내부 불변 record를 보관한다. 데이터 전체의
Pydantic 인스턴스·필드 set·중첩 가변 dict/list를 장기간 유지하지 않는다. JSON은 이미
생성된 published 모델의 기존 serializer에서 만든다. 바깥 record는 읽기 쉬운 NamedTuple로
구현하며 일반 tuple 시제품과 GC 추적 특성이 다르므로 최종 구현으로 비용을 재측정한다.

기록 시 published 모델은 지금처럼 timestamp/history identity를 붙여 반환한다. 원래 입력,
실시간 published 값과 CSV에 전달하는 모델·private freshness anchor는 변경하지 않는다.
보관 대상은 화면 history API가 공개하는 JSON 투영이다. 기존 Field(exclude=True) 내부
freshness 값과 PrivateAttr는 공개 응답에 넣지 않는다. CSV·원본 데이터 포맷 이관은 없다.

조회는 기존 lock 안에서 동일한 순서·조건으로 retention/UTC/cursor/limit과 응답 metadata를
결정하고 선택한 불변 record의 참조만 가져온다. lock을 해제한 뒤 JSON을 새 dict/list로
복원한다. 저장 시점에 이미 직렬화한 내부 값만 `FactoryData.model_construct`로 복원하여,
측정 값을 다시 정규화하는 validator를 재실행하지 않는다. 외부 파일·사용자 입력을 이
경로로 읽지 않는다. 각 조회는 독립된 객체를 반환하여 응답 객체 수정이 저장 이력을
바꾸지 않게 한다. 응답 모델·필드·API 경로·최대 limit는 그대로다.

1시간의 monotonic 만료와 정확한 경계, 36,000개 FIFO 한도, 같은 UTC의 별도 sequence,
UTC 역전, legacy latest-tail, cursor 페이지·gap/reset·retry, clear/restart identity를 유지한다.
메모리 collector는 같은 bounded sample을 고른 뒤 lock 밖에서 새 표현을 추정한다.
GC enable/threshold/freeze/주기 설정, health 200ms 한도와 온도 안전 기준은 바꾸지 않는다.

확인 예: 중첩 Computed/list/dict를 가진 값을 기록한 뒤 원본·published·첫 조회 응답을
수정해도 다음 조회 JSON은 기록 당시와 같아야 한다. 조회 복원 중 recorder를 실행해
lock 때문에 막히지 않는지, 동시에 clear해도 해당 응답의 metadata와 samples가 일관된지
검사한다. 기존 history/API/clock/CSV 회귀와 최종 전체 health 검사를 수행한다.
동일 소스·입력의 수정 전후 격리 프로세스에서 15,800개와 36,000개 보관, full GC,
기록 비용, 500/1,000개 및 최대 페이지 조회·직렬화 비용을 비교한다.
로컬 시험만으로 설치본이나 현장 15분/120분을 PASS로 표시하지 않는다.

첫 실제 구현 비교에서는 1,000개 조회·재직렬화가 약 11~16ms에서 66~81ms로 늘었다.
이 결과를 수용하고 끝내지 않는다. 페이지 선택은 단일 내부 함수로 유지하고, Python
호출자의 모델 반환 경로와 HTTP의 이미 직렬화된 JSON 결합 경로를 나눈다.
HTTP 경로는 각 record의 내부 serializer 출력과 정수 timestamp/sequence를 결합하고,
metadata는 표준 JSON encoder로 직렬화한다. 기존 응답 바이트·Content-Type·OpenAPI
응답 모델을 유지한다. 외부 JSON 문자열을 이 내부 저장소에 넣는 경로는 만들지 않는다.
`backend/app.py`의 이력 endpoint는 `asyncio.to_thread`로 페이지 선택·JSON 결합·UTF-8
인코딩을 수행하고 bytes Response를 반환한다. event loop 안에서 전체 이력을 모델로
재구성하거나 인코딩하지 않는다. 이 변경도 R2 병목 보완 범위이며 새 endpoint를 추가하지 않는다.

회귀 검사에는 HTTP/모델 경로의 전체 JSON 바이트 일치(한글·따옴표·줄바꿈·중첩값),
다른 스레드에서 실제 응답을 만드는지, worker가 대기 중일 때 동일 event loop의 health
요청이 완료되는지를 포함한다. 큰 페이지의 조회·인코딩 비용과 최대 메모리를 별도 기록한다.

최대 36,000개 응답을 큰 문자열로 결합한 첫 HTTP 구현은 격리 프로세스의 peak working
set을 약 496MiB에서 546MiB로 늘렸다. 전체 문자열의 중간 사본을 줄이도록 `BytesIO`에
각 record를 UTF-8로 순차 기록하고 최종 bytes를 반환한다. 이는 HTTP streaming 전환이
아니며 기존 한 응답의 Content-Length와 bytes 응답 계약을 유지한다. 같은 최대 페이지의
해시, 조회 시간, peak working set/commit을 새 프로세스에서 수정 전후 재비교한다.

### 5.24 검증된 1.0.30 후보의 현장 도우미 연결

제품 build는 `0732c8e810be3c46096b397812f53a9767354229`, installer는
164,941,077bytes / `e72c042dd4554d5c31e27b8a2edfa6ecdcbdd08c58ed43769e7a84d782b370c1`로 고정한다.
이미 검증한 같은 설치본을 사용하며 도우미 변경만으로 제품을 재빌드하지 않는다.
`CandidateIdentity`에 이 정확한 1.0.30 값만 추가한다. 기존 1.0.28 기본값과 1.0.29
식별자는 유지한다. 1.0.30 payload 기준은 기존 검산 JSON 원문 SHA256
`4e3e95be87d8ea51a509ba62c8eb29236eefe402f5f353bb78c9a342d7825a97`이다.

관찰 요청의 outer/spec commit과 후보별 기준 SHA를 함께 검증한다. 900/7200초 일반 관찰,
300초 host 진단과 900초 timing 진단의 기존 시간 예산을 유지한다. timing 진단에만
1.0.29/1.0.30을 허용하고 native 생성 FILETIME 검증을 유지한다. 6초 WPR 전용 수집기는
계속 1.0.29만 허용한다. 승인된 Low Signal OFF 범위와 실제 설정 snapshot은 새 후보로
명시적으로 검증하며 과거 attestation/기준 파일을 수정하지 않는다.

성공 조건은 새 후보의 실제 격리 collector 및 닫힌 CSV·이미지 경로에서 후보 식별이
끝까지 유지되는 것이다. 잘못된 payload/provenance/runtime/기준 SHA, 생략된 새 spec
commit, 과거 fingerprint, 혼합 종료 metadata를 거부해야 한다. 느린 첫 health, 변경된
실행 세대·잘못된 timing header와 200ms 실패 기준, 소유 수집 프로세스 정리도 유지한다.
기존 후보 회귀와 새 후보 정상/오류 조건을 함께 검사한다. 제품별 현장 설치 도우미의
1.0.29→1.0.30 연결 및 실제 서버 설치·15분/120분 QA는 이 계약 시험 뒤 별도로 확인한다.
어떤 합성 PASS도 현장 효과·물리 경계·전체 데이터·운영 승격으로 올리지 않는다.

### 5.25 1.0.29→1.0.30 원본 보존 설치 계약

기존 1.0.28→1.0.29 계약과 과거 묶음은 보존하고, 요청에 명시된 후보 commit으로
정확한 두 교체 쌍만 선택한다. 새 요청 schema는 `sfl-history-observed-install-request-v1`,
백업 정책은 `OMITTED_FOR_1030_HISTORY_ONLY`다. 제품 변경은 메모리 이력·응답 준비이며
CSV/설정 이관이 없고, 같은 설치본의 격리 업그레이드/복구에서 원본 보존을 확인했으므로
새 전체 백업을 만들지 않는다. 원본 기본/추가 스트림·metadata·구성원 전수 검산은 유지한다.

새 계약은 이전 후보 `acaf77d9...`/1.0.29/installer `3394a23d...` 164,824,610bytes,
새 후보 `0732c8e8...`/1.0.30/installer `e72c042d...` 164,941,077bytes를 고정한다.
payload 기준 SHA는 각각 `658b0964...`, `4e3e95be...`다. 새 요청에는 이전 후보 설치본도
명시해 검증하고, 정식 롤백 기준541d/08c061ee도 별도 보존한다. 새 후보 제거 파일은
격리 설치에서 확보한234,260bytes/SHA256
`a9f2f1785d7e1c41ba5b6db75253b91da716eaf565017ed213091bff29091910`으로 고정한다.

성공 조건: 현재1.0.29의 실제 process 생성 식별자·정상 종료 리뷰와 관찰 manifest를 결합하고,
앱/포트 부재 상태에서 원본 전수 재검산 후120초 안에 설치를 시작한다. 설치는 동일 잠금
바이트, `/S /currentuser`, native 종료0을 사용하고 강제 종료·자동 재시도·자동 복귀는 하지 않는다.
설치 뒤1,899 payload와 제거 파일·등록값1.0.30, 원본/설정 전체 보존을 다시 확인한다.
앱 시작·새 실행 설정 attestation·현장 성능은 별도 단계다. 이전 버전·정책·payload·제거 파일이
섞인 요청, 없거나 변경된 복구 설치본, 정상 종료가 아닌 부재만으로는 설치를 허용하지 않는다.

### 5.26 자정 이후 대용량 현재 CSV의 종료 증거

현재 1.0.29 파일은 358MB를 넘고 첫 순번은 18,573이다. 기존 종료 도우미의 128MiB
전체 메모리 읽기와 첫 순번1 가정은 이 파일에 적용할 수 없다. 제품과 과거 묶음은 바꾸지
않고 `sfl-health-runtime-close-request-v2`에 읽기로 확인한 `csv_first_sample_seq`를 고정한다.
기존 v1 요청은 첫 순번1과128MiB 한도를 유지한다. v2는 현재1.0.29만 대상으로 하며
1GiB 상한·1MiB 복사 버퍼·300초 복사 제한을 둔다. 전체 백업을 추가하지 않는다.

정상 종료의 native handle·생성 시각·exit0·450초 대기·앱/포트 부재와 설정 해시를 유지한다.
현재 CSV의 기본 스트림만 잠금 읽기로 새 결과 파일에 순차 복사하며 덮어쓰기와 추가
스트림 경로를 거부한다. 같은 스트림 바이트의 길이·SHA256을 기록하고, 회수 검토는
잠금 핸들을 유지한 채 해시와 CSV를 순차 읽는다. 행 shape·중복 header·logger 세대,
요청 첫 순번부터의 연속성, metadata 최종 순번 및 종료 직전 health 순번을 대조한다.
세대 전체 `rows_total`을 현재 파일 행 수와 혼동하지 않으며 이전 파일의 무결성은 별도다.

검사 예: 실제128MiB 초과 파일의 복사/CLI 검토, 순번18,573부터 연속된 파일, 잘린 첫 행,
중간 누락/중복, 잘못된 최종 순번, 다른 logger, 잠긴 writer, 초과 용량, 기존 목적지,
잘못된 UTF-8/CSV를 확인한다. 이 한 파일 검토는 전체 데이터·이미지·worker 종료 QA를
대신하지 않는다. 실제 서버 종료·설치 전에는 수정 도우미의 로컬 검증을 먼저 마친다.

### 5.27 1.0.30 승인 프로파일 확인 항목 연결

운영 프로파일은 변경하지 않고, 별도로 전달하는 설정 확인 도우미에 검증한 후보 commit
`0732c8e810be3c46096b397812f53a9767354229`만 추가한다. 기존 두 후보와 같은
Low Signal OFF·comparator 미검증·USER_SELF·설정/metadata SHA 검사를 유지한다.
실제 새 실행 metadata의 build/fingerprint/readback을 확인한 후 앱이 종료된 상태에서
확인 항목 네 개만 갱신한다. 새 후보의 정상 입력과 변경된 프로파일·잘못된 입력 해시를
검사하며, 물리 경계 NOT_TESTED/정식 QA HOLD를 유지한다. 도우미 변경으로 제품 설치본을
재빌드하지 않는다. 실제 현장 실행 전까지 설정 확인 완료로 보고하지 않는다.

새 실행의 종료 증거에는 `sfl-health-runtime-close-request-v3`를 사용한다. v3는 위 1.0.30
commit만 허용하고 health 버전·build·metadata를 함께 대조한다. v1/v2는 기존 1.0.29
계약을 유지한다. v3는 v2의 명시된 첫 순번·1GiB 스트리밍·native 종료 확인을 그대로
사용하며, 이전 버전과 섞인 요청/health/metadata는 거부한다. 실제 서버 실행 전 로컬
native 종료·복사 검사와 Python 검토기의 혼합 버전 거부 검사를 통과해야 한다.

### 5.28 완료한120분 관찰과 정상 종료의 연결

이미 실행 중인1.0.30 canary를 재시작하지 않고, 기존 v3 종료 관찰기와 native 제어기를
그대로 사용한다. 새 로컬 준비기는 실제 SSH terminal, 콘솔 결과 경로·launcher SHA·종료 코드,
회수 manifest와 독립 원시 표본 재계산 결과를 연결한 뒤에만 실행별 새 종료 묶음을 만든다.
terminal이 없거나900초 자료·다른 요청/세대·불일치 해시·불완전 재계산이면 준비를 거부한다.

최종 health 바이트에서 같은 backend·build·spot/logger·CSV·최소 순번을 다시 계산하고
관찰기의 shutdown expectation과 일치시킨다. 실제 첫3행1/2/3을 확인한 현재 CSV만 첫 순번1로
요청하며, 최종 관찰의 최소 순번은 후속 닫힌 CSV/fact/이미지 검증의 하한으로 전달한다.
최종 설정 대조PASS와 현재 config 해시도 유지한다. 묶음에는 실제 runtime 기준·설정 기준·
최종 관찰 연결 자료를 동봉하고, 실행 직전에도 같은 연결 조건을 다시 확인한다.

성능 FAIL 자체는 진단 자료를 보존하는 정상 종료를 금지하지 않는다. 이 경우 FAIL과 출시
HOLD를 보존하며, 증거 무결성·최종 실행 식별이 확인돼야 종료를 준비할 수 있다.
서버 실행은 기존 전달 정책에 따라 최종 로컬 복사·잠금 해시 확인을 마친 뒤 수행한다.
`READY_FOR_NORMAL_APP_EXIT` 이후 정상 GUI 종료만 사용하며 강제 종료·설치·전체 백업·
자동 재시작을 추가하지 않는다. 종료 후 원문 회수와 실제 native 종료·CSV 최종 경계 검토는 별도다.

검사 예: 실행 중 terminal 부재, 중복 콘솔 결과, 잘못된 launcher SHA/종료 코드,900초 요청,
다른 logger/CSV/build, 감소하거나 정수가 아닌 순번, 변조된 최종 health, 승격된 scope,
기존 목적지 재사용을 거부한다. 합성 묶음 생성 검사는 로컬 fixture 안에서만 수행하며
실제 canary 완료·서버 전달·정상 종료 증거로 사용하지 않는다.

### 5.30 정상 종료 후 선택한 CSV·대장의 고정 사본

기존 종료 관찰기는 CSV/metadata/config를 보관하지만 누적 관찰 fact·이미지 fact·최종 image
manifest를 포함하지 않는다. 후속 CSV/fact 연결 검사에 필요한 이 입력을 확보하기 위해
`scripts/field-v1028/capture-closed-facts.ps1`를 별도 검증 도우미로 추가한다. 제품 설치본을
재빌드하지 않으며 전체 운영 폴더의 백업도 추가하지 않는다.

실제120분 결과와 정상 종료 기록을 검토한 뒤에만 실행별 새 요청을 만든다. 같은 main/backend
PID·생성 시각·실행 파일, logger/build/CSV, 최종 최소 순번, 설정 SHA와 정상 종료 결과 SHA를
결합한다. 서버·운영자·관리자/native PS5.1과 앱/8000포트 부재를 확인한다. 해당 config·CSV·
metadata와 필요한 대장 모두를 쓰기/삭제 공유 없는 읽기 핸들로 연 뒤 복사 종료까지 유지한다.

이미지 fact4GiB·관찰/선택 fact2GiB·CSV1GiB·metadata/최종 manifest/config4MiB 예산을 적용한다.
현재 metadata가 요구하는 선택 fact도 포함하고, 0행/해시없음인 선택 fact의 실제 부재를 검사한다.
별도 추가 스트림이 있으면 조용히 생략하지 않고 중단한다. 새 보호 결과 폴더의 여유 공간은
선택 입력 합계+64MiB로 확인하며 기존 부모 ACL은 바꾸지 않는다. 복사된 각 파일을 별도로
재해시하고, CSV/metadata/config는 종료 영수증, 관찰 fact는 metadata, 이미지 fact는 최종
manifest의 SHA와 대조한다. 중간 실패 파일은 보존하고 HOLD에 불완전 사본 가능성을 표시한다.

기존 native owned Job 제어기를 그대로 사용해 진단 자식만 관리하고1800초 제한을 적용한다.
전달·서버 실행 전 실제 증거 결합을 다시 확인한다. 앱 재시작은 사본 확보·검토 후 별도 수행하고
운영 화면을 전면에 복귀시킨다. 예: canary 재계산 → 정상 종료 검토 → 요청·묶음 생성 →
Z/원격 탐색기로 서버 로컬 전달 → 잠금 해시 검사 → 선택 사본 확보 → 회수/CSV 소비자 검사.
선택 사본의 해시 일치는 내용 QA나 전체 과거 데이터·이미지 실물 검사 PASS가 아니다.

### 5.31 CPU 지연 진단의 데이터·이미지 동시 부하

2026-10-17 보존 CPU 추적에는 최대 요청216의 CPU 샘플이 남아 있지 않았다. 기존 health
단독 진단과 실제120분의 data/image 동시 부하 차이를 줄이는 보조 수집기를 별도 추가한다.
`field_concurrent_api_load.py`는 data6초/image0.25초만 요청하고 health를 중복 요청하지 않는다.
기존 HTTP 수집기의 timeout5초·기록/응답 검증·비동기 fsync·부하별 주기를 유지한다.
최대900초, body128MiB, 파일7,510개로 제한한다. 기존120분의 전체 body293,487,403bytes를
참고했으나 새로운 실행이 같은 양이라는 보장은 하지 않으며 예산 초과는 실패로 남긴다.

자식의 실제 HANDLE을 전용 Windows Job에 배정한 후에만 실행 gate를 연다. 공통 미래
origin보다 늦은 준비·배정 실패는 거부한다. 종료 요청은 즉시 전달하고, 최대30초의 파일
저장/종료 대기 이후에는 소유한 job만 종료해 실패를 기록한다. 성공/실패 모두 실제 종료
코드·Job 잔여·결과/manifest 해시를 확인한다. 취소된 HTTP 슬롯은 성능 PASS로 바꾸지 않는다.

로컬 실물 HTTP/정상 종료/조기 종료/시간 제한/배정 실패 검증 후 명시적 CPU 동시 진단
요청·계약에 연결한다. 느린 health 요청이 나오면
보조 부하 중지 요청 → WPR 저장/정지 → 보조 부하 drain 순서로 원래 요청의 보존을 우선한다.
기존 solo 진단·200ms 기준·900/960초 한도·설치본·앱/장비 설정·출시HOLD는 유지한다.
이는 성능 원인을 추적하기 위한 진단이며 정식15/120분 QA를 대체하지 않는다.

로컬7조건 및 보존 결과52항목 대조를 완료했다. 상세 근거는 분석5.48절과 후보 보고서에
기록한다. 완료된 로컬 검사는 entrypoint 통합/서버 검증을 대신하지 않는다.

동시 진단에는 `sfl-health-cpu-concurrent-request-v1`과 별도 concurrent contract/lease,
`LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC`을 사용한다. 기존 요청은 동시 부하를
추가하지 않는다. native CPU profile 해시와900/960초, 외부1500초, 최종180초 한도는
유지한다. WPR 준비와 기존 앱/설정 결합 뒤3초 미래 origin을 공유하며, 보조 결과는
collection/concurrent-api에 저장하고 evidence에 시작/종료 사실을 연결한다.
trigger 뒤 보조 요청 중지, trace 완료, 보조 drain을 순서대로 실행한다. 오류 경로에서도
중지 요청과 trace abort를 먼저 전달한 뒤 소유 자식만 정리한다. 보조 capture 실패는
전체 수집 완료 판정을 막는다. 취소된 슬롯은 보존하되 진단을 성능 시험으로 표시하지 않는다.


통합 구현·49 Python 시험/18 native PS 묶음·14 frozen 거부 조건과405개 보존 자료 대조는
분석5.49절에 기록했다. frozen 성공 경로와 실제 서버 진단은 아직 미검증이다. 공유 전송이
완료돼도 서버 로컬 최종 복사·해시 검증 전에는 실행하지 않으며, 현재 공유 접근 오류와
준비된 bootstrap을 분리해 보존한다. 기존 실패·실제 물리 시험/승격 조건은 그대로 유지한다.


2026-10-17 후속 실제 서버 전달·frozen 동시 진단은 완료했고 분석5.50절에서 종료/전체회수와
선택 ETW 필드를 독립 대조했다. 이는 위5.49 시점의 미검증 상태를 갱신하는 후속 증거다.
연결 준비 중 Ready 상태 지연191.964ms를 확인했으나 근본 원인·계측 영향·정식 성능은
미확정이다. 조기 시작14건과 취소 슬롯을 invalid/NOT_MEASURED로 유지한다. 현재 설치본,
200ms 계약, 물리 경계 NOT_TESTED와 출시HOLD를 유지한다.

### 5.32 보조 HTTP 수집기의 예정 시각 대기 보완

동시 진단의 data1/image13건이 예정 시각 전에 시작했다. 보조 worker가 일반 관찰기와
달리 raw multiprocessing.Event를 HTTP 수집기에 직접 전달한 것을 확인했다. 개발PC의
Python3.12.6 native 실험960회 중 multiprocessing의0.3ms 대기80회가 모두 일찍 반환됐다.
이 결과는 대기 후 실제 시각을 재확인해야 함을 입증하며 서버14건 각각의 OS 원인은 아니다.

새 보조 worker에서 기존 `ObservationStop`을 재사용한다. 취소를 전달하는 로컬 Event와
단조 시각 재확인을 사용하고, 수집 성공·예외 모두 bridge thread를 종료한 뒤 결과를 쓴다.
기존50ms 취소 전달 간격, HTTP timeout/주기/예산·200ms 상한, owned Job 정리 계약은 유지한다.
기록 시각을 보정하거나 이전 invalid 표본을 PASS로 변경하지 않는다.

검증: 수정 전 동일 worker의 조기 반환 재현 → 수정 후 같은 검사, 실제 native 자식의
data6초/image0.25초 전 요청 시작·관찰 종료 시각 확인, 외부 중지·오류·강제 종료·결과 변조
및 bridge 정리 회귀를 수행한다. 일반 HTTP/ObservationStop/진단 회귀도 영향 범위에 포함한다.
도우미 변경만으로 제품 설치본을 다시 만들지 않으며, 다음 서버 사용에는 새 고정 도우미와
패키지 검증이 필요하다. CPU 배정 지연의 근본 원인과 정식120분 실패는 별도 미완료다.

### 5.33 보조 HTTP 이상 시점의 추적 보존

2026-10-17 `H49927dfe58dc`에서 health450건은200ms 이내였으나 이미지 요청1717이256.8425ms
걸려 슬롯1718을 놓쳤다. 마지막54.494초의 CPU 표본에는 해당 요청이 없었다. health만으로
중지를 결정하는 관측 공백을 보완하며, 이미지 저장 drop이나 지연의 근본 원인을 고쳤다고
주장하지 않는다. 근거는 분석5.53과 `CWAIT_20261017_c8314fa2/missed-slot-review.json`이다.

HTTP 수집기에 내부용 완료 관찰 callback을 추가한다. 기존 호출은 callback 없이 같은 동작을
유지한다. 요청 기록을 비동기 저장 큐에 넣은 뒤, 기존 다음 슬롯 판단에 쓰는 종료 시각과 함께
보조 수집기에 알린다. 보조 수집기는 다음 중 최초1건만 최대4KiB의 단방향 Pipe로 전달한다:
요청 실패, 기존 failure_ms 초과, 다음 예정시각 도달/초과, 실제 missed_slot. 경고 임계값과
취소 슬롯은 trigger로 바꾸지 않는다. 주기·timeout·200ms health 계약은 유지한다.

알림에는 endpoint/sequence/예정시각/판단시각/이유와 큐에 넣은 원본 JSON의 SHA256을 묶는다.
첫 알림을 보낸 뒤 추가 전송하지 않아 Pipe backlog를 제한한다. 부모는 기존 health 대기 전후와
각 health 완료 뒤, 마지막 관찰 대기 뒤에 확인한다. 알림 수신 시 중지 요청 → WPR 저장/정지 →
보조 수집기 drain 순서를 유지한다. 진행 중 health 요청은 기존 timeout으로 제한되며 즉시 강제
중단하지 않는다. 알림 시각과 부모 판단시각은 별도로 기록하고 즉시 보존을 보장했다고 쓰지 않는다.

새 trigger는 health와 companion 출처를 구분한다. 같은 health 검사에서 두 조건이 관찰되면
health trigger와 companion 알림을 모두 보존한다. 아직 health 표본이 없어도 초기/최종 앱·설정
결합이 유효하고 companion 원문이 검증된 경우 수집 완료를 허용한다. 정식 성능 PASS는 아니다.
drain 후 알림의 원문 파일·SHA·예정시각·이유를 재대조하고 알림과 결과가 다르거나 전송/저장이
실패하면 전체 수집 완료를 거부한다. 자식 조기 실패와 Pipe EOF, 시작 실패, 정상/강제 종료에서
기존 owned Job 정리와 Pipe handle 정리를 확인한다.

검증 예: 정상health+350ms 이미지 응답을 실제 loopback/native 자식으로 재현해 수정 전에는
추적을 보존하지 못하고 수정 후에는900초를 기다리지 않고 저장을 요청하는지 검사한다. 경계값,
한 번만 전송, 실제 missed_slot, 원문 변조, 알림/추적 실패 정리와 기존 일정 회귀를 포함한다.
전체 frozen/WPR 및 서버 적용은 별도 증거가 필요하며 현재 제품 설치본·설정·출시HOLD는 유지한다.

### 5.34 System 이벤트 조회 결과의 명시적 기록

분석5.63의 BOM-only78개는 과거 수집기가 조회 오류를 숨겨, 빈 결과와 실패를 구분할 수 없다.
해당 역사적 수집기와 pinned 사본은 변경하지 않는다. 현재 field-v1028 health 진단의 소유 worker에
읽기 전용 System 이벤트 메타데이터 수집을 추가한다. 요청 측정·WPR 종료·보조 요청 drain·최종
앱 결합 확인 뒤 실행하며 측정 중 추가 부하를 넣지 않는다. 조회 창은 trace 시작 직전2분 전부터
요청 관찰 종료까지의 UTC 범위다. 이 범위는 실제 성능 표본의 정밀 ETW 시간 경계와 구분한다.

Windows EvtQuery/EvtNext/EvtRender를 같은 스레드에서 사용한다. System 채널만 조회하고
최대1,000건·개별 XML64KiB·협조적5초·Next250ms 한도를 둔다. 막힌 native 호출의 최종 정리는
기존 소유 worker/Job의 `origin + 예정 관찰 길이 + 180초` 고정 한도가 담당한다. 조기 trigger가
이 한도를 앞당기지는 않는다. 별도 프로세스·권한 변경은 없다.
실제 ERROR_NO_MORE_ITEMS와 모든 handle 종료가 확인돼야 COMPLETE다. 정확히1,000건이면
다음 항목의 유무를 확인하며, 초과·취소·시간 초과·조회/해석/정리 실패는 INCOMPLETE로 보존한다.

system-events.json에 조회 채널·UTC 범위·XPath·조회 시각·한도·오류 단계/유형/Windows 코드와
수집한 건수를 기록한다. 전체 일치 건수는 COMPLETE일 때만 정수이며 나머지는 null이다.
성공0건은 명시적 빈 배열이다. 항목은 record ID·event ID·provider·level·UTC 시각으로 제한하고
본문/계정/컴퓨터명은 저장하지 않는다. 같은 manifest에 결합하며 미완료 조회는 전체 수집 완료를
막는다. 이는 출시/성능 PASS나 과거 이벤트 부재 증명이 아니다. 새 frozen 묶음은 별도 검증 전
서버에 사용하지 않는다.

검증: 0건/비어 있지 않은 성공, query/next/render/parse/close 오류, 부분 결과, 정확한/초과 건수,
취소·시간 한도·handle 정리, 실제 개발PC System 조회와 PowerShell 대조, 이벤트 파일 변조,
trace/drain 뒤 실행 순서와 기존 health/동시 진단 회귀. 조회 실패를 과거와 같은 빈 성공으로
표시하지 않는 것이 성공 기준이다.

### 5.35 고정 NAS CSV 검사 범위의 내용 해시 대조

NAS CSV157,139개의 고정 목록을 온도1,470·PLC127,158의 검증 사본 및 나머지28,511개의
기존 잠금 읽기/재해시 기록과 경로·크기·mtime으로 대조한다. SHA256과크기가 같은 경우에만
온도/PLC/압축 CSV 구조 검사 결과를 연결한다. 같은 내용을 검사한 사실은 원래 파일의 업무 의미,
세대/metadata 연결·현재 원본 불변성·전체 snapshot 일관성을 증명하지 않는다.

원장의 일치148,920개와 미대응8,219개를 전부 기록하고, 미대응을7,596내용/25,506,700,718바이트로
중복 제거해 읽기 전용 후속 검사 대상으로 삼는다. 조회한 원장 밖의 별도 검사 부재는 주장하지 않는다.
원본은 기존 Z 공유 매핑/경로 guard로 열고, 크기·mtime·기존 내용SHA를 재검증한다. 대표 사본1개를
검사한 결과를 같은 SHA의 과거 alias에 연결하되 모든 alias를 현재 다시 읽었다고 쓰지 않는다.

검증된 streaming CSV parser를 재사용한다. 전체 바이너리 EOF/해시 → strict encoding/CSV 구조 →
다시 원본 해시/파일·상위 디렉터리 identity 대조를 수행한다. 분석 기록만 새 실행 폴더에 저장하고
원본을 복사·수정하지 않는다. generic 구조 finding과 스키마별 실제 손상은 구분한다.
worker는7,200초 협조 한도를 사용하고 별도 부모는7,260초 후 소유 worker만 종료한다. 부모가
예기치 않게 종료되면 Windows 소유 Job 닫힘으로 worker를 종료한다. 중간·실패 기록은 보존하고
기존 실행을 관찰 timeout만으로 다시 시작하지 않는다. 결과 조회가 아니라 실제 종료 코드가 있어야
해당 실행을 완료로 분류한다. 전수 의미·양방향 이미지 연결·최종 delta는 별도R4 미완료다.

Windows 프로세스 handle의 종료 관측과 Job active 수 반영 사이에 짧은 지연이 있을 수 있다.
worker 종료 후 최대5초 동안 정리 여부를 관찰하고, 이후에도 남은 소유 트리만 종료한다.
정리 대기 전후 수치와 시간을 기록한다. 정상/오류 종료·시간 초과·감시 부모 종료 fixture로
실제 native Job 동작을 확인하고, 완료 결과에는 실제 종료 코드와 기록 해시를 함께 검증한다.

### 5.36 중첩 CSV 구조 증거와 해시 목록의 범위 연결

기존 중첩 멤버 원장161 CSV/115고유 내용을 고정 구조 registry와 SHA256·크기로 연결한다.
기존 문법 검사는 strict CSV 해석·행 폭 집계를 수행했으므로 이를 보존하고, 미대응10내용의
헤더/빈 칸/NUL/본문 폭 판단만 검증된 parser로 보완한다. 일치105내용은 기존 finding까지
함께 연결하며 무조건 PASS로 바꾸지 않는다. 결과는 전체161멤버에 정확히 대응해야 한다.

추가 검사는 보존 중첩 ZIP3개의 고정 manifest·그래프·멤버 offset/이름/크기/CRC와 연결하고,
잠금 바이트의 전체 해시·EOF·전후 identity를 검증한다. 추출·복원·NAS 재읽기는 하지 않는다.
해시 목록 CSV는 상대경로/크기/SHA 형식과 중복을 검증하고 동봉 JSON과 전수 대조한다.
목록이 참조하는 원본이 ZIP 안에 없으면 원본 본문 검증 완료로 쓰지 않는다. NIC 값과 이벤트는
원래 컬럼 계약에 맞게 분류하되 실제 장비/시각/조회 완전성을 형식 검사로 증명하지 않는다.
부정 fixture로 경로 탈출·중복·해시/크기 오류·CSV/JSON 불일치를 거절하고 최종 기록을 별도 검산한다.

### 5.37 NAS CSV finding의 형식별 후속 검사

진행 중 원장은 완결된 줄의 prefix 길이·SHA와 선택한 행 번호를 고정하고 중간 결과로만 사용한다.
최종 worker 종료 후 전체 선택·원장·summary·terminal을 결합해야 NAS 범위 완료로 기록한다.
generic UTF-8/열 폭 finding은 즉시 손상으로 분류하지 않는다. 원본 경로 guard·크기/mtime·
SHA·전후 identity를 확인한 읽기 전용 후속 검사로 실제 바이트와 보존 생산자 계약을 대조한다.

UTF-8 거절 자료는 strict CP949/EUC-KR의 전체 decode/encode roundtrip과 CSV 구조를 확인한다.
호환 가능 인코딩임을 기록하며 실제 작성기의 선택이나 단위·정확성까지 단정하지 않는다.
Rect 제목9열/본문4열과 제목 없는 후보는 보존 소스의 고정 제목·동적 본문 길이·문자 필터와
대조한다. 실제 배포본/인식 영역/원본 화면이 없으면 저장 형식 재현과 물리 의미를 구분한다.
빈/개행만/Invalid Date 파일과 HCellShareFileInfo signature 보조 바이트는 개별 증거를 보존하고
업무 수치로 사용하지 않는다. 원본 수정·복원·전체백업을 수행하지 않는다.
헤더에 실제 탭이 있는 파일은 탭 구분 strict CSV도 비교한다. 인용된 셀 안의 탭·줄바꿈은
본문 행과 구분하며 쉼표 parser 실패를 파일 손상으로 단정하지 않는다. 전체 해석 가능한 형식과
수치 NaN/빈칸 등 데이터 품질은 따로 기록한다. 예외 분석은 기존 실패 기록을 덮어쓰지 않는다.

붙은 PLC 행의 경계 후보는 알려진 마지막 비고 문자열과 관측된 열 수가 맞을 때만 메모리에서
나눈다. 보존 사본의 공통9열 문자열·행 순서를 전수 대조하고 날짜 칸 제외/빈 행 제외의 범위를
기록한다. 없는 날짜나 수치를 채우지 않으며 비교용 변환을 원본 복구 완료로 보고하지 않는다.
사본 간 시간 표기 차이는 원문 차이로 남기고 실제 시계 정밀도·시간대 일치로 확대하지 않는다.
옛 통합 CSV는 보존 Git 소스의 순수 행 구성/CSV 쓰기만 재현하며 당시 배포 설정은 별도 미확정이다.

### 5.38 완료된 NAS 구조 원장과 세대 연결 후보

NAS worker의 실제exit0·summary·terminal·잔여Job0을 확인한 뒤7,596내용/8,219alias를
고정 선택 집합과 전수 대조한다. 기존148,920개 구조 근거와 합쳐157,139개 NAS CSV의 경로·
크기·mtime·SHA 결합 누락이 없어야 구조 범위 완료다. 구조 finding532개의 후속 형식 분류는
원인 미분류0 또는 전체R4 통과와 구분한다. 후속PLC 행 경계/빈 행 위치 증거도 최종분류에 연결한다.

현재 원장의v2 CSV·관찰/image fact 헤더를 가진 내용은 모든alias와 함께 목록화한다. 고정NAS
전체 목록에서 동일부모의metadata/final-manifest 후보를 찾되 이름 일치만으로 세대/내용을
확정하지 않는다. `Factory_Integrated_Log_v2_<suffix>.csv`에는 동일suffix의 `.metadata.json`
후보를 대응시킨다. 미발견은 해당목록의 부재이며 다른경로·이름·현재서버의 부재로 확대하지 않는다.
이는 후속 읽기 범위 준비다. 실제JSON·스키마·출처·fact·CSV키/순번·허용빈값·최종해시 연결은
각 해당계약으로 확인하며 최신 validator를 지원하지 않는 옛스키마에 그대로 적용하지 않는다.

인접JSON/JSONL247개는 고정목록의 경로·크기·mtime과 대조해 읽는다. 전체EOF/SHA와 읽기
전후identity를 검증하고 원문은 변경하지 않는다. 이JSON에 과거내용SHA가 없는 경우 현재관측
해시임을 표시하며 과거바이트불변으로 확대하지 않는다. 최대파일26,530,224바이트를 포함하도록
개별32MiB한도를 명시하고 한도초과를누락하지않고실패로기록한다. strict UTF8/BOM·중복키·
NaN/Infinity/overflow·JSONL행별오류를구분한다. JSON문법통과와업무값유효성은별개다.
출력은형식/키목록/해시와metadata의schema·CSV종료·fact manifest블록으로제한한다.
일반설정·원시HTTPpayload·비밀값은보고서에복제하지않는다. 소유Job/고정시간한도로읽기를
관리하고 실제종료/잔여프로세스를확인한다. 새32MiB한도는기존서버도우미한도변경이아니다.

### 5.39 누적 fact의 정확한 바이트 prefix 대조

전체 해시가 다른 과거 manifest는 추가 행이 붙은 파일의 snapshot일 수 있다. 기존 NAS 후보
9개를 반복 읽기 전에 개발 PC에 이미 회수·검증한 누적 이미지 fact와 같은 제목의 역사적 관찰
fact를 후보로 결합한다. 이전 본문 SHA·크기·행 수 근거를 고정하고 실제 현재 파일을 검증한다.
후보 선정은 일치 판정이 아니다. 같은 종류·제목·충분한 행 수만으로 원래 세대를 확정하지 않는다.

원본 바이트를 그대로 hash하며 CSV parser가 한 논리 행을 소비한 지점의 SHA·바이트 offset을
기록한다. BOM, CRLF/LF/CR, 인용 셀의 줄바꿈을 유지하며 CSV 재직렬화 해시는 사용하지 않는다.
후보 전체 EOF/해시·기존 행 수·제목과 전후 파일 identity를 대조하고 같은 잠금 아래 전체를
재해시한다. 정확한 prefix 일치만 증명하며 이후 행·다른 사본·실제 값·닫힌 세대 통과로 확대하지 않는다.
기존 NUL/열 폭 finding은 보존한다. 손상된 부분을 해시 계산에서 제거하거나 보정하지 않는다.

fixture는 BOM/다중 줄/CRLF 경계 분할/CR/빈 행/마지막 개행 없음과 잘못된 UTF8·미완결 인용·
잘못된 전체 해시·행 수/제목을 포함한다. bounded owned Job로 실행하고 실제 종료와 active0을
확인한다. 로컬 후보로 해결되지 않은 참조만 기존 NAS 후보 또는 다른 보존 증거에 이어서 대조한다.

### 5.40 보존 CSV의 버전별 행 규칙 대조

신규 구조 원장의 v2 측정51내용/4,325,141행을 고정한다. metadata가 선언한 Git commit이
있으면 해당 Git 객체의 validator 규칙을 사용한다. 선언 commit이 없는 자료에는 헤더 세대와
맞는 보존 reference contract를 명시하되 실제 배포본의 증명으로 쓰지 않는다. 지원 소스를
찾지 못한 스키마는 공통 행 검사를 수행하고 원래 계약 미확정 상태를 유지한다.

원본 validator의 필요한 함수/상수 AST와 의존 정의를 같은 commit에서 추출한다. 앱 초기화,
설정 로드, 네트워크/장비 동작을 실행하지 않는다. 소스 SHA와 선택 함수/의존 노드를 기록하고,
순수 행 함수의 원문을 바꾸지 않는다. chunk는 메모리 제한이며 모든 행의 메시지와 전역 행 번호를
보존한다. sample_seq/행 고유키의 전체 파일 연속성과 중복은 chunk 밖에서 별도로 확인한다.

고정 NAS 경로·SHA·크기·mtime·전체 EOF와 전후 해시/identity를 확인한다. metadata가 있으면
고정 JSON SHA를 재확인하고 schema·rule version·실제 freshness/cache threshold를 읽는다.
metadata 부재를 임의 기본 설정이나 승인 프로파일로 채우지 않는다. 해당 조건부 규칙을
NOT_EVALUATED로 명시하고 독립적인 검사는 계속한다. 현재 validator를 옛 버전에 일괄 적용하지 않는다.

공통 검사는 선언 스키마/열 폭, NUL, 행 순번·고유키, UTC/local 시각 형식과 품질/누락 표기를
해당 보존 계약 범위에서 확인한다. 숫자 구문과 실제 장비 단위/값 정확성은 구분한다. 기존
동일 내용의 fact 의미 증거는 SHA·크기·행/계약이 일치하는 범위만 재사용한다. 참조 사실표와
이미지 실물의 양방향 검증, 출처·장비 프로파일·최종 delta 및 알려진 손상은 별도 미결로 유지한다.

발견된 메시지는 원문/전역 논리 record/원본 SHA/적용 참고 commit을 보존한다. 실제 배포본을
모르는 자료는 문서화된 규칙 변경 commit의 같은 함수를 해당 행에 비교하되, 열이 부족한
후대 계약은 적용 불가로 분리한다. 새 규칙에서 메시지가 없어져도 실제 배포본 일치나 데이터
정상으로 승격하지 않는다. 비교 가능한 모든 계약에서 남는 값/출처 불일치는 원인 미확정으로
유지하고 추정값으로 원본을 보정하지 않는다. 비교 범위가 처음 고정한 전체 finding을 포함하는지
최종 issue 원장 해시와 대조한다. 완료 뒤 실제 종료 코드와 소유 Job active0을 확인한다.

### 5.41 보존 fact의 의미 근거 재사용과 불일치 관측 연결

남은 fact 내용은 기존 검증 누적 본문의 정확한 CSV 논리 행 prefix인지 확인한다. 원본 바이트
SHA뿐 아니라 prefix 바이트 길이·행 수·제목과 기존 의미 검사의 전체 본문/소스 근거를 결합한다.
이전 manifest 검증과 다른 목표 행 경계만 새로 확인하며 같은 참조 검사를 반복하지 않는다.
혼합 스키마는 기존에 검증한 동일 열/규칙 변경 근거를 유지하고, prefix 안에 알려진 손상 행이
포함되면 이를 전파한다. 새 규칙 적용 또는 해시 일치만으로 손상/미검증을 PASS로 바꾸지 않는다.

측정 CSV의 지속 불일치는 logger ID와 SPOT service ID를 혼동하지 않고 spot_observation_key로
보존 관측 fact에 연결한다. 같은 service의 앞뒤2개 관측은 문맥으로만 보존하며 가까운 시각이나
온도값만으로 동일 관측이라고 판정하지 않는다. 찾은 원 관측과 CSV의 값/시간/상태를 대조하되
정확한 배포 소스와 원인 재현이 없으면 인과를 확정하거나 원본을 수정하지 않는다.

### 5.42 이미지 시작 snapshot과 별도 종료 manifest 구분

sidecar의 이미지 manifest는 CSV 종료 표시와 별도로 생성될 수 있다. 같은 폴더의 고정
`spot_image_fact_manifest.final.json`과 metadata 선언 Git 객체의 종료 처리/검증 함수를
대조한다. final manifest의 실제 행 수·SHA를 전체 fact 내용에 결합하고, 기존 시작 snapshot을
재작성하지 않는다. 공식 validator의 명시적인 final-manifest 인자를 사용해 엄격한 행 수/해시
검사를 유지한다. 시작 snapshot/실제 fact override/종료 manifest의 서로 다른 검증 동작을
fixture로 확인하며, 별도 종료 파일이 맞는다는 사실을 이미지 실물·CSV 역방향 검증으로 확대하지 않는다.

종료 선언이 있는 CSV는 기존 전체 행 검사의 SHA·행 수·엄격 증가 순번·logger ID 근거에
연결한다. 순번이 양의 정수로 엄격히 증가하고 `마지막-처음+1=행 수`이면 그 순번열을 복원할
수 있다. metadata 선언 commit의 원래 `validate_csv_closeout`에 이 순번열과 보존된 종료
블록을 적용한다. 이는 원본 CSV 재읽기나 전체 metadata 검증이 아닌 종료 순번 증거의 재생이다.
종료 선언이 없는 자료와 metadata가 없는 자료는 별도로 남기며 정상 종료로 추정하지 않는다.

### 5.43 보존 metadata 계약과 CSV/fact 교차 참조

고정된 측정51내용/56경로의 metadata41건은 같은 SHA를 다시 확인한 뒤 검사한다. 선언된
commit 또는 명시된 참고 commit의 원래 validator에서 metadata/헤더 검사 구문과 필요한
함수·상수만 추출한다. 원래 구문/조건은 유지하고 제외한 행 검사·파일 읽기·fact 검사는
소스 위치와 이유를 남긴다. 설정 함수에는 빈 행 목록을 전달하여 정적 metadata 조건만
검사하며, 실제 행의 설정 일치 조건은 후속 CSV/fact 연결 단계에서 적용한다.

스키마 지원 여부·필수 열·센서 매핑·운영자 필드 선언·shadow/sentinel 정의·설정 provenance·
active schema/column hash를 해당 소스 규칙 범위에서 대조한다. 원 계약을 찾지 못한2.0은
NOT_EVALUATED로 남긴다. metadata의 선언은 실제 배포 바이트 또는 물리 장비의 증명이 아니다.
metadata 부재15건은 임의 기본값으로 채우지 않는다. 검사기의 mutation fixture는 원본의
메모리상 사본에서만 필수 블록·스키마·열·해시를 바꾸어 검출 여부를 확인한다.

CSV/fact 연결은 exact observation key와 출처 필드로 수행하며 누적 fact의 범위를 명시한다.
참조된 키를 찾지 못한 경우 검사한 자료의 범위와 누락/부재를 구별한다. CSV의 온도값과
관측값·실물 이미지·현재 서버 세대는 각 증거가 확보된 범위만 판정한다. 새로운 업무 값이나
원본 보정본은 만들지 않는다.

종료 선언이 있는12건은 앞서 검증한 fact 전체 내용 또는 정확한 prefix의 source SHA와
최대 논리 record를 고정한다. 같은 observation key가 다른 세대에 있다는 이유만으로
종료 명세와 연결됐다고 판정하지 않고, 해당 source와 prefix 경계 안의 일치를 별도 계산한다.
이미 검증한 역사적 관측 색인은 원래 DB 전체 SHA를 전후 확인한 읽기 전용 연결로 재사용한다.
CSV에서 얻은 관측 필드별 값의 묶음과 행 수는 압축 분석 원장으로 보존하여 후속 값 대조에서
원본 전체를 다시 읽지 않게 한다. 이 분석 원장은 원본 CSV 복구본이나 새 전체 백업이 아니다.

### 5.44 원 관측 값과 진단 출처의 교차 비교

5.43의 CSV별 값 투영과 exact source/record 색인을 재사용한다. 관측 키가 양수인 모든
대상 행을 원 fact에 연결하고 동일 이름의 직접 기록 필드는 정확한 문자열로 비교한다.
CSV의 spot_response_content_length는 원 writer의 spot_response_length_bytes 대응을
소스별로 확인한다. 두 형식에 공통으로 없는 열은 비교하지 않은 범위로 기록한다.

관측 온도는 원 raw 텍스트에 선언/참고 소스의 finite-float parser를 적용하여 대조한다.
원 문자열 차이를 지우지 않고 숫자로 같은 경우를 별도 분류하며 허용 오차를 새로 만들지 않는다.
진단 evidence code는 해당 소스의 원래 parser와 missing-source 함수를 추출해 실행한다.
함수가 없는 옛 소스는 임의 최신 규칙으로 대체하지 않는다. 원본/선언 metadata/배포 바이트와
참고 소스의 차이를 유지하며, 문자열 차이만으로 손상이나 실제 코드 원인을 단정하지 않는다.

원 fact는 필요한 source만 읽되 끝까지 해시를 계산하여 고정 SHA와 대조한다. 파일 identity와
읽기 잠금, 소유 Job 종료를 확인하고, 이미 회수한 최근 관측의 검증된 필드 투영은 재사용한다.
fixture는 잘못된 키/record/값, 정상 raw 개행, 숫자 표기 차이, 빈값, 부재 필드, 진단 근거 누락을
검출해야 한다. 결과는 CSV·키·원본 SHA·논리 record·값 variant별 행 수에 연결하고 전체 집계를
재검산한다. 분석용 색인/차이 원장은 새 폴더에만 쓰며 원본 보정·백업·서버 변경은 하지 않는다.

### 5.45 관측 manifest의 전체 집계와 비종료 snapshot

고정 metadata의 비어 있지 않은 관측 명세13건(종료12/비종료1)을 모두 선택한다. 기존의
원본 전체/prefix SHA와 행 경계를 재사용하고, 원 fact의 진단 집계는 같은 source를 한 번 읽어
필요한 prefix 시점마다 기록한다. 선언된 Git commit의 원 summarize 함수에서 진단 누적과
최종 통계 표현식을 그대로 추출하며, 제외한 파일 해시/파일 I/O/identity 처리는 외부 고정
해시와 기존 읽기 전용 색인에 결합한다. 전체 원 함수를 작은 fixture에 실행한 값과 같아야 한다.

옛 전역 poll 순번 집계와 새 service별 집계를 구별한다. 여러 service/중복/잘못된 key/빈값/
진단 누락/JSON 오류/부분 prefix의 fixture를 포함한다. 역사 색인의 파일 SHA와 원본 행 수가
맞는지 확인하고 source/record 경계를 적용한다. 최근 작은 직접 fact는 같은 원 identity
함수로 계산한다. 파싱한 원본 전체 SHA와 파일 identity를 전후 확인한다.

CSV 링크 수는 기존 exact key 원장으로 다시 집계하며 원 CSV를 재읽지 않는다. 비종료
snapshot에서 realtime_rows 없이 기록한0은 실제 CSV 키가0개라는 증거가 아니다. 명세의
통계가 맞는지, CSV 링크를 그 명세가 실제로 집계했는지, 정상 종료했는지를 구분한다.
write/spool의0 선언은 실제 과거 실패 이력 부재의 증명으로 확대하지 않는다. 기존 NUL손상과
그 원인은 집계 일치와 독립적으로 남기며 전체 R4/출시 통과로 바꾸지 않는다.

### 5.46 CSV 이미지 참조와 기록 시점별 원장 범위

고정 측정 CSV51종 중 이미지 열이 있는19종을 선택한다. 이전 관측 투영에는 이미지 열이
없으므로 이19종만 다시 읽고, 이미지4열과 시각·관측 키·service·공정 문맥을 압축 분석
투영에 함께 남긴다. 기존 검증된 이미지 원장 색인4,385,307행은 읽기 전용으로 재사용하고,
별도 시험 원장4종/23,707행은 내용 SHA·행 수·파일 identity를 확인하여 연결한다.

CSV의 이미지 ID를 먼저 찾은 뒤 Windows의 대소문자 구분 없는 상대 경로를 비교한다.
ID 부재,경로 차이,service 차이,여러 원장 일치를 각각 집계한다. 서로 다른 service는 실제
nearest 선택 규칙을 확인하기 전에는 손실 또는 버그로 단정하지 않는다. CSV의 모든 이미지
열이 빈 행과 참조가 있는 행을 구별하고, 논리 record와 참조별 행 수를 보존한다.

이미지 명세23건(비어 있지 않은19건과 초기0행4건)의 기존 전체/prefix 해시 증거를 재사용한다.
metadata snapshot과 별도 final manifest를 나누고, 해당 원장의1부터 시작하는 데이터 행
번호가 명세 범위 안에 있는지 검사한다. 범위 밖이어도 보존 원장 전체에서 ID/경로가 맞으면
이를 전체 원장 부재로 보고하지 않는다. 실제 이미지 바이트/디코드,nearest 선택·age 재현,
종료 후 파일시스템 전체와 양방향 대조는 별도 검증 상태로 유지한다.

검증 예: 원장1·2행,다른 시험 원장1행,잘못된 경로,다른service,0행 snapshot fixture를
구분하고, 전체 투영의 행 수·참조 수를 결과 SQLite와 독립적으로 재집계한다. 읽기 전후
SHA·identity와 소유 Job 종료를 확인한다. 제품·서버·원본 변경이나 새 전체 백업은 하지 않는다.

ID 연결이 완료된 뒤에는 참조된 이미지의 원 기록을 선택하여 관측 키·service·연결 상태·
연결 age 네 필드를 CSV 투영과 정확한 문자열로 비교한다. 공통 보존 원장은 끝까지 읽어
전체 SHA를 확인하되 필요한 ID의 원 행만 후속 분석용 투영으로 남긴다. 별도 시험4종의
이미 회수한 원 행 투영은 재사용한다. 기록 값의 일치와 당시 최신 이미지 선택/age 계산의
정확성을 구분하고, 차이가 있으면 수치 허용 오차로 지우지 않고 원 문자열을 보고한다.

### 5.47 보존 이미지 바이트·디코드 증거의 양방향 연결

서버13일·14일·16일의 원 디코드 원장과 NAS loose 이미지 원장을 재사용한다. 같은 크기와
SHA256에만 디코드 결과를 연결하고, 반복 경로/동일 내용과 서로 다른 촬영 ID를 구분한다.
PASS는 모든 프레임 decode와 기존 바이트 검산을 완료한 기록만 허용한다. NAS의0바이트
3건과 producer exit1,16일 원 전송exit255 및 후속 완료 증거는 각각 보존한다.

이전 단계의 고유 참조 이미지373,000개를 연결하고, 실제 decode 형식·크기·프레임 수와
fact의 MIME·width·height를 비교한다. 역방향은 공통 원장 색인,별도 시험4원장,옛31열
원장을 모두 포함한다. 파일명 capture ID의 일치와 내용만 같은 경우를 따로 기록한다.
라이브러리/NAS 기타 이미지를 이름만으로 설비 orphan으로 분류하지 않는다.

디코드 증거가 없는 참조는 기존 NAS 압축의 검증된 일반 멤버 전체에 크기/SHA로 조회한다.
그 조회에서 바이트가 발견돼도 디코드 완료로 승격하지 않는다. 손상 압축 뒷부분·추가 중첩
본문·선택 밖 NAS 파일은 미확인 범위로 남긴다. 이 연결은 과거 사본 증거이며 현재 서버
파일 존재나 retention 삭제 원인의 증명이 아니다. 예: 같은 SHA지만 크기가 다르거나
decode 실패인 기록을 PASS로 결합하지 않는 fixture와 독립 집계로 분류를 검증한다.

기존 증거에 없는 시험 이미지는 원 final manifest의 capture_root 네 곳이 서버에 남아 있는지
승인된 SSH로 확인한다. 대상 host/user/권한을 먼저 확인하고, 정확한 네 폴더에서 reparse
지점을 거부한 파일 수·크기를 읽는다. 남아 있으면 해당 폴더의 파일만 읽기 전용 스트림으로
회수해 원 fact의 크기/SHA, 전체 프레임 decode, MIME·해상도와 양방향 대조한다. 쓰기 probe는
별도 내용·해시로 기록하며 이미지로 세지 않는다. 압축을 풀거나 서버 원본을 변경하지 않는다.
전송은 소유 Job·시간·바이트 한도 안에서 수행하고 실패/부분 결과를 보존한다. 수신 파일은
`Z:/SmartFactory/20261017/return` 아래 실행별 폴더에 둔다. 사용자 답변의 추가 사본 없음은
2023–2025 온도·PLC 기록에만 적용하며, 2026 시험 이미지의 부재 근거로 확대하지 않는다.

### 5.48 이미지 연결 시간의 원 계약과 재현 가능 범위

기존373,000개 참조 이미지 원 행 투영을 재사용해 capture ID의 시각/내용 식별자, 연결 키,
age의 형식·유한성·부호와 상태를 검사한다. 촬영 시각과 별도 link_checked_at을 혼동하지
않는다. 각 CSV metadata의 선언 commit 또는 명시된 참고 commit에서 계산·스냅샷 선택·CSV
연결 함수를 읽어 AST별로 묶고 원 순수 함수의 경계 fixture를 실행한다. 실제 배포 바이트
확인과 선언/참고 소스 검토는 구별한다.

기록하지 않은 입력 때문에 정확히 재현할 수 없는 계산은 그 누락 입력을 명시한다. 예:
`link_checked_at - completed_epoch`로 구한 age를 촬영 시각 차이로 재계산해 불일치로
판정하지 않는다. metadata에 당시 refresh interval/stale 기준이 없으면 현재 기본값을
소급 적용하지 않는다. lock 획득 시점의 최신 스냅샷을 전체 이력의 시간상 최근접 검색과
같다고 주장하지 않는다. 새 전체 백업·서버 변경 없이 독립 합계와 입력 해시로 검산한다.

### 5.49 현재 운영 경로 목록과 이전 기준의 증분

승인된 SSH에서 host/user/관리자 여부와 현재 설정의 저장 경로를 먼저 확인한다. 원 설정과
프로세스 세대를 바꾸지 않고 SmartFactoryLogger 운영 루트의 전체 파일/디렉터리를 읽는다.
명시된 루트 경계와 reparse 미추적,시간·항목·출력 한도를 적용하고 부분 출력/실패를 보존한다.
파일명은 UTF-8 base64,크기·생성/수정 tick·속성과 관찰 시작/종료 시각을 남긴다. 쓰기 중인
비이미지 파일은 디렉터리 조회 길이와 읽기 handle 길이를 구분한다. handle 열기 실패도 숨기지 않는다.

이전 종료 목록의 같은 운영 루트와 경로별로 추가·부재·크기/시각/속성 변경을 대조한다.
변경 없는 metadata는 내용 SHA 동일성의 증거가 아니며,열거 중 생성될 수 있는 파일과
쓰기 중인 CSV/fact를 일관된 종료 snapshot으로 취급하지 않는다. 두 목록의 차이는 후속
일관된 범위 회수·내용 검증 대상을 정한다. 예: 현재0바이트 디렉터리 표시라도 읽기 handle의
길이를 확인하기 전 빈 CSV/데이터 손실로 판정하지 않는다. 새 전체 백업·원본 변경은 하지 않는다.
서버 작업 후 Smart Factory Running/전면 표시를 화면으로 확인하고 과거 작업 값을 덮어쓰지 않는다.

### 5.50 고정 증분 이미지의 제한 회수와 내용 검증

5.49의 52,755개·511,098,674바이트 선택 목록과 SHA를 고정한다. 승인된 SSH의 대상과
권한을 확인한 뒤 목록에 있는 이미지만 tar 표준 출력으로 읽어 새 return 폴더에 수신한다.
먼저 소수 파일로 stdin 목록 전달을 확인하고, 성공한 파일은 이후 묶음에서 제외한다.
각 묶음의 시간·바이트 한도, 소유 Job 정리, 읽기 잠근 목록과 실패/부분 결과를 보존한다.
경로 이탈·중복·링크를 거부하고 압축을 풀지 않는다. 예: 완전한 tar payload만 인정하며
부분 전송은 확인된 성공 집합을 빼고 남은 파일만 후속 회수 대상으로 기록한다.

모든 선택 payload의 크기·SHA256·파일명 내용 해시 접두부와 전체 프레임 디코딩을 확인한다.
별도 검산은 선택 집합·묶음·기록·실제 payload의 합계와 SHA를 다시 대조한다. tar의 초 단위
mtime 일치는 NTFS tick 전체나 원자적 snapshot 보증으로 확대하지 않는다. 새 이미지의
관찰 SHA/디코딩 성공은 아직 회수하지 않은 최신 fact/CSV 연결의 성공과 구분한다. 이미
증명된 이미지 재복사·전체 백업·원본 변경은 하지 않으며 종료 후 운영 화면을 확인한다.

추가 실행 조건: stdin 목록의 첫 대형 전송이 SSH 응답 시간 초과로 중단되면 해당 실패를
그대로 보존한다. 남은 원격 tar는 PID·부모 PID·생성 시각·명령과 실제 process handle을
결합해 이 작업 소유임을 확인한 경우에만 종료한다. 완전한 payload만 재사용하고 누락 집합을
계산한다. 검증된 나머지 파일 목록을 새 서버 바탕화면 SmartFactory 실행 폴더에 전달하여
서버 로컬 SHA를 확인한 뒤 `tar -T <목록 파일>`로 읽을 수 있다. 목록 텍스트는 진단 입력이며
운영 데이터·설정 변경이나 전체 백업이 아니다. 진행 기록은 실행별 고유 파일명으로 남긴다.

### 5.51 고정 CSV/fact 범위의 증분 회수와 연결

현재목록의233657 CSV/metadata와20261017 CSV/metadata,두fact의고정끝바이트를사용한다.
기존종료사본의image/observation fact 전체prefix SHA를서버에서다시확인하고,일치할때만
추가구간을회수한다. 원본은Read/ReadWrite공유로열어앱쓰기를막지않으며,고정prefix·수신범위의
전후SHA와생성시각·길이를기록한다. 이는전체파일의동시시점snapshot과구분한다.

도우미와요청은새서버실행폴더의SHA고정·읽기잠근동일바이트로실행한다. 각파일의고정범위를
바이너리stdout으로회수하고stderr의시작/종료receipt와수신SHA를대조한다. 파일별시간·바이트한도와
chunk별읽기/쓰기대기를제한하며실패·부분출력을보존한다. 기존full prefix를다시전송하거나
전체백업을만들지않는다. 예: live CSV의마지막불완전행은원바이트로보존하고파서가완전하게
확정한record 경계까지만분석한다. 중간절단행을정상행으로꾸미거나새끝시점을계속늘리지않는다.

회수후전체행의스키마·키·관측값·이미지ID/경로/전체SHA/크기/차원연결을기존인덱스와함께대조한다.
순차목록경계로인한파일간차이와실제불일치를구별하고,한정된PASS를전체R4/출시PASS로확대하지않는다.

순차 목록의 끝에서 선택 이미지 3개의 fact만 범위 밖이면, 기존 고정 범위를 넓혀 다시 받지 않는다.
원 고정 끝까지의 전체 SHA를 기존 사본과 증분으로 계산하고, 같은 서버 prefix의 전후 SHA를
검증한 뒤 image/observation 각각 다음 8,192바이트만 한 번 읽는다. 선택 대상은 원래 3개로
유지한다. 추가 구간의 불완전 끝부분은 별도 원바이트로 보존하고 완전 record로 세지 않는다.
예: quoted CSV 안의 줄바꿈을 행 끝으로 오인하지 않으며, 3개 ID의 전체 SHA·크기·차원과
관측 키를 결합한다. 6개 원 범위와 2개 보충 범위의 결과·소유 프로세스 정리를 각각 남긴다.
원본 전체 행 구조·raw echo·이미지 참조의 성공과 파생 온도 규칙·빈 실시간 image hint의
원인·최종 정상 종료 QA를 분리하여 다음 단계의 미완료 항목으로 명시한다.

### 5.52 고정 현재 행의 설치 commit별 의미 검사

5.51의 완전 CSV 248,944행과 metadata/관측·이미지 인덱스를 읽기 잠금과 SHA로 재사용한다.
metadata에 기록된 0732c8e commit의 validator와 의존 순수 정의를 Git object에서 추출한다.
당시 metadata를 원 validator 호출식에 적용해 3초 freshness/15초 cache TTL/v6 조건을 확인한다.
현재 소스의 기본값이나 과거 버전의 규칙을 대신 적용하지 않는다. 7개 행 규칙 전부를 검사하고
fixture 변이와 chunk 경계 비교로 누락된 검사·잘못된 record 번호를 확인한다.

채워진 이미지 hint는 같은 이미지 fact의 관측 키·status·age와 대조한다. 빈 hint는 관측 키
유무, 그 키에 연결된 이미지 존재, 캡처 시각과 CSV 시각의 전후로 분류한다. 예: 나중에
캡처된 이미지를 CSV 작성 당시 이미 게시된 이미지라고 가정하지 않는다. capture 완료 시각,
fact 게시 순서·lock 획득 시각이 기록되지 않은 부분은 런타임 원인 재현으로 주장하지 않는다.
원본·서버 설정을 바꾸거나 새 전체 백업을 만들지 않고, 불일치는 record와 근거를 보존한다.

### 5.53 잔여 비이미지 경로의 기존 증거와 고정 범위 대조

5.52에서 남긴 같은 30개 경로를 사용한다. 기존 종료 CSV/metadata·설정·종료 영수증 15개는
기존 사본의 SHA와 출처 영수증을 먼저 검증하고, 서버의 정확한 파일 길이·생성/수정 시각과
내용 SHA가 일치하면 재전송하지 않는다. 설정 이전본은 attestation 전후 기록과 연결하며,
새로운 백업을 만들지 않는다. 기존 사본의 검증과 현재 원본 바이트 일치는 별도 기록한다.

로그 11개 중 append형은 이전 검증 prefix SHA를 전후 확인한 뒤 당시 목록의 고정 끝까지
추가 바이트만 읽는다. 회전형은 길이·생성/수정 시각이 당시 목록과 다르면 해당 세대의
바이트 미확보로 기록한다. 현재 파일을 과거 범위로 가장하지 않는다. 상태 파일 4개는
제한된 현재 길이를 두 번 읽어 SHA와 경로/handle 식별자를 대조하고 시각·프로세스 세대와
함께 기록한다. 예: 작업 정보가 바뀌었으면 이전 생산 번호를 덮어쓰지 않고 현재 표본과
당시 미확보 바이트를 구별한다. 로깅 쓰기를 막지 않는 공유 읽기를 사용한다.

읽기 도우미는 요청·동일 도우미 바이트 SHA 고정, 경로 경계/reparse 검사, 읽기/출력/전체
시간·바이트 제한과 소유 실행 정리를 적용한다. 원본 변경·전체 백업 없이 기존 증거와
새 추가 바이트를 검산하고, JSON/종료 sidecar/행 경계와 실제 확인 범위만 보고한다.
회전·휘발성 과거 바이트의 미확보를 새 데이터 손실 원인 확정이나 전체 R4 PASS로 바꾸지 않는다.

회전된 별명 중 당시 metadata와 같은 후보가 있으면 그 정확한 한 경로만 한 번 보충 조회한다.
앞선 handle ID와 길이·시각을 재확인하며, 이미 교체됐으면 바이트를 인정하지 않고 미확보로
끝낸다. 무조건 별명이 없다고 가정하거나 현재 파일을 과거 내용으로 대체하지 않는다.

### 5.54 초기 193310 실행의 관측·이미지 사후 연결

이미 결합된 193310 CSV 2,439행과 metadata, P30 종료 시 누적 관측/이미지 fact 사본을
사용한다. CSV의 모든 양수 관측 키·16개 raw echo·관측 온도, 이미지 힌트의 ID/경로/
관측 키/status/age를 대조한다. 초기 서비스의 관측과 이미지 전체를 원 누적 파일의
record 번호·시작/끝 바이트로 추출하고, 기존 244개 이미지 실물 SHA·decode 증거와 연결한다.

같은 파일의 시작/종료 manifest가 다른 시점을 나타낼 수 있으므로 metadata의 row_count
위치까지 실제 원바이트 SHA를 계산한다. 예: image metadata written=0은 시작 prefix와
대조하고, 종료 receipt written=244 및 뒤 canary의 누적 final manifest와 혼동하지 않는다.
관측 metadata의 종료 prefix와 실제 full 사본도 각각 결합한다. 파일 내용·설정은 바꾸지 않는다.

원래 source commit에서 manifest 작성/검증 정책을 읽고, 일치·미확보·실제 차이를 구분한다.
독립 검산은 저장된 원 offset 범위를 다른 CSV reader로 읽어 원 row와 일치하는지, 모든 CSV
참조 및 기존 byte proof가 연결되는지 확인한다. 현재 값으로 과거 미기록 publish/lock 순서를
추정하지 않고 서버 추가 수집·전체 백업·같은 대형 이미지 디코딩을 반복하지 않는다.

### 5.55 고정 R4 범위와 남은 인과 증거의 통합

기존 단계의 실제 closeout·summary를 저장된 SHA와 대조해 최신 범위표를 만든다. 과거 NAS,
서버 고정 목록, 초기 실행, 닫힌 canary, 실행 중 CSV를 구분하고 중복 사본·겹친 행을
합산하지 않는다. 예: 157,139개 NAS CSV의 구조 근거 100%는 물리 의미·현재 서버 원바이트
일치 100%가 아니다. 원인 미확정과 후보 데이터의 설명 없는 누락을 별도로 남긴다.
추가 사본 부재 때문에 복구하지 못한 값은 추정하지 않고, 아직 읽을 수 있는 원 근거에
다음 작업을 연결한다. 기존 PASS를 반복하기 위한 서버 수집·전체 백업은 하지 않는다.

R2의 기존 221.0337ms 요청에서 두 Ready 구간은 CSwitch에 이미 연결됐다. 보존 CPU 이벤트의
DPC/ISR 시작·종료 raw 값, 독립 tracerpt 필드, CPU별 중첩 합집합을 대조해 해당 구간의
인터럽트 시간과 그 밖의 실행 점유를 구분한다. 전후 process/thread 매핑과 당시 동적
priority 근거를 유지한다. 예: ISR이 DPC에 중첩되면 두 시간을 중복 합산하지 않는다.
공식 ETW/스케줄러 정의를 사용하며 불완전 스택·미기록 affinity·반사실 시험 부재를 보존한다.
원인 확정 전 우선순위·성능 기준·운영 프로그램을 변경하지 않는다. 이 분석이 최초 R1 사건이나
120분의 다른 두 실패 표본까지 설명한다고 확대하지 않는다.

### 5.56 같은 지연 구간의 경쟁 프로세스 스택 확인

보존 CTRACE의 221.0337ms 요청과 두 Ready 구간에서 CPU sample을 선택한다. 기존 원시
sample 대조 증거와 출력 SHA를 재사용하고, 선택한 스택의 모든 주소는 독립 tracerpt의
StackWalk 원문과 timestamp/process/thread로 다시 연결한다. kernel/user 조각의 순서와
누락·중복을 검증하고 맞지 않는 스택을 임의로 합치지 않는다. 예: 같은 thread라도 sample
시각이 다르면 다른 스택이며, 두 CPU의 표본 수를 벽시계 응답 시간으로 계산하지 않는다.

이미 확인한 CSwitch 구간·thread/process 매핑과 해당 시점 표본을 대조한다. 프로세스·
thread·모듈별 표본 수와 반복되는 스택을 기록하되 빈 symbol이나 알 수 없는 프레임을
함수명으로 추정하지 않는다. 모듈 이름은 변환기의 기록이고 독립 주소 대조와 구분한다.
Windows storage/MSI 등 모듈의 존재만으로 사용자가 파일을 복사했거나 설치를 실행했다고
단정하지 않는다. 다음 분석에 필요한 정확한 주소·모듈·PDB 확인 범위를 남긴다.

새 서버 추적·설정 변경 없이 잠긴 기존 입력과 유한 시간/프로세스 정리 경로로 분석한다.
선택 범위·독립 대조·스케줄 연결·표본 한계·실행 종료를 확인하며 기존 실패와 출시 HOLD를
유지한다. 문제를 확인하기 전 경쟁 프로그램 종료나 우선순위 변경을 해결책으로 적용하지 않는다.

함수명이 필요하면 기존 ETLX에 기록된 정확한 PDB GUID/age가 있는 Windows 모듈만
Microsoft 공개 symbol 서버와 대조한다. 기존 패키지 잠금 파일과 라이브러리를 재사용하고
새 분석 폴더에만 결과·symbol cache를 기록한다. 서버의 원 DLL이나 ETL은 바꾸지 않는다.
PDB 식별값이 없으면 해당 함수는 미확인으로 남기며 개발 PC의 동명 DLL로 대체하지 않는다.

### 5.57 캐시 갱신 계기의 보존 증거 확인

직전 단계의 8개 PDB 식별값을 원 tracerpt의 ImageID/RSDS와 ImageLoad 기록에 연결한다.
모듈 경로·주소·크기·PID와 PDB GUID/age를 구분하며, 같은 이름의 다른 모듈을 합치지 않는다.
예: system32와 syswow64의 ntdll은 서로 다른 PDB다. 선택한 원 이벤트·ordinal·payload와
독립 해석을 남기고 변환기 결과의 자기 비교만으로 원본 일치를 주장하지 않는다.

기존 추적의 provider/event inventory와 capture 설정을 확인해 파일·레지스트리·shell 작업이
실제로 기록됐는지 먼저 판단한다. 기록되지 않은 이벤트의 부재를 작업 부재로 해석하지 않는다.
가능하면 같은 시각의 이미 보존된 host event와 연결해 캐시 갱신 계기를 좁힌다. 근거가 없으면
과거 원인 미확정과 필요한 후속 관측을 명시하며, 반복적인 동일 자료 재분석을 끝낸다.
서버 설정·우선순위·성능 기준을 바꾸지 않고 기존 실패 및 물리/데이터 QA 한계를 유지한다.

### 5.58 개발 PC 파일 쓰기와 AppResolver 비교

개발 PC의 새 Desktop/SmartFactory 폴더에서 무쓰기·새 파일 생성·기존 파일 추가 쓰기를
각 30초씩 두 번 비교한다. 순서는 무쓰기→생성→추가→추가→생성→무쓰기이며 단계 사이
10초, 최초·최종 20초를 둔다. 같은 4KiB 내용을 250ms마다 쓰고 열린 파일은 매번 닫는다.
측정값은 메모리에 모아 마지막에 저장한다. 준비 파일·로그 생성은 최초 대기 전에 끝낸다.
예: 생성 조건은 각기 다른 JSON 파일, 추가 조건은 미리 만든 JSONL 파일 하나를 사용한다.

기존 Shell-Core 로그를 읽기만 하며 채널 상태·원 XML·조회 한계·PID/TID별 검사 쌍과
단계별 횟수·시간 겹침을 기록한다. Explorer 프로세스 세대와 CPU도 전후 읽는다.
자체 자식만 소유 Job에 넣고 시간 제한·종료 상태를 남긴다. 기존 원본·서버·설정을 바꾸거나
새 백업을 만들지 않는다. 결과는 개발 PC의 제한된 재현이며 서버 원인이나 성능 QA 판정이
아니다. 미관측이면 가설을 기각하지 않고 OS/경로/부하 차이를 남긴다.

첫 비교에서 생성 조건의 검사 두 건이 약 120초 간격으로 관측되어 주기와의 우연한 일치를
확인한다. 두 번째 비교는 생성→무쓰기→추가→무쓰기→생성→추가 순서로 바꾸고 나머지
시간·쓰기량·검증은 유지한다. 생성 구간의 간격은 약 160초가 된다. 첫 증거는 보존한다.

### 5.59 서버의 파일 쓰기 조건 비교

개발 PC에서 확인한 두 순서를 서버에서도 각각 한 번 실행한다. 기존 검증된 native
소유 Job 실행·시간 제한·연결 중단 정리를 재사용하고, 같은 측정 로직을 미서명 시험
실행 파일로 동결한다. 배포 제품은 변경하지 않는다. 묶음·요청을 외부 SHA로 잠근 뒤
새 Desktop/SmartFactory 결과 자식에만 관리자 쓰기와 운영자 읽기 ACL을 적용한다.
자료는 Z/send와 서버 로컬 최종 폴더까지 전달하고 결과는 Z/return으로 회수한다.

예: 실행 전후 backend PID/생성 시각과 승인된 Low Signal OFF 설정을 읽고, 측정 중에는
탐색기·복사·추가 조회를 하지 않는다. 실행마다 최대360초이며 정상·실패의 종료 기록을
보존한다. 로컬 동결 실행 smoke, 제한시간 종료, 제어 프로세스 종료의 정리를 확인한다.
새 전체 백업·장비 제어·우선순위 변경·운영 데이터 쓰기는 하지 않는다. 관찰 결과는 기존
200ms 기준의 QA와 구분하며, 원인 확인 전 진단/제품 동작을 바꾸지 않는다.

### 5.60 파일 저장의 fsync 조건 비교

5.59 서버 비교는 반복 AppResolver 검사를 재현하지 못했다. 보존된 원 진단 소스에는
파일별 `flush` 뒤 `os.fsync`가 있고 비교 worker에는 `flush`만 있음을 확인했다.
기존 원 진단의 쓰기 시각·파일 manifest와 검사 구간도 대조하되 상관을 원인으로 바꾸지 않는다.

새 worker는 같은4KiB JSON 파일을250ms마다 생성하면서 flush만 하는 조건, flush+fsync
조건, 무쓰기 조건을 비교한다. 예: 첫 순서 무쓰기→flush→fsync→fsync→flush→무쓰기,
두 번째 flush→무쓰기→fsync→무쓰기→flush→fsync. 각30초/사이10초/앞뒤20초로 유지한다.
파일 형식·크기·경로 깊이·간격을 맞추고 차이를 fsync 호출 여부로 한정한다. 기존 결과는 보존한다.
동결 smoke에서 두 순서의 실제 파일 내용을 확인하고 변경 없는 native Job/종료 시험 증거를
재사용한다. 외부 SHA·서버 전후 세대/프로파일·새 보호 폴더·360초 제한·Z 전달/회수 기준은5.59와 같다.

기존 Windows 로그를 읽고 기록은 마지막에 저장한다. 새 추적 provider·OS 설정·장비 제어·
제품 변경·전체 백업을 추가하지 않는다. 미재현도 결과로 남기며 더 큰 임의 부하로 확대하지 않는다.
fsync 유무의 검사/CPU/쓰기 시간 차이만 판단하고 HTTP200ms QA·원 timeout 해결로 해석하지 않는다.

### 5.61 보존 ETW의 검색 스레드 준비 문맥

fsync 비교에서도 반복 검사가 재현되지 않아, 보존된 원 trace의 Process/Thread와 ReadyThread
기록을 확인한다. 기존 프로파일에는 FileIO/Registry 및 ReadyThread 스택이 없으므로 그 동작의
부재나 특정 호출자를 증명하지 않는다. 새 서버 추적이나 설정 변경 없이 기존 고정 XML을 읽는다.

예: 검색 담당TID15572/704의 ReadyThread와 전후 CSwitch, 전체 프로세스 시작·종료 및 스레드
세대 기록을 추출한다. XML 원본 해시/ordinal/원 payload를 보존하고 기존 독립 scheduler decoder와
일치시킨다. 같은 CPU의 실행 문맥은 당시 스레드 정보로만 표시하고 DPC 플래그나 미확정 세대를
원인 프로세스로 승격하지 않는다. 이벤트 시각 대조는 이전 시각 불확도 한계를 유지한다.
읽기는 기존 소유 Job/시간 제한으로 실행하고 원본·과거 결과를 변경하지 않는다.

### 5.62 호출자 스택 수집의 통제된 깨우기 시험

기존 R5 소유 추적 실행기를 새 묶음으로 복사하여 ReadyThread 스택과 Loader를 추가한
프로파일을 시험한다. ProcessThread/CSwitch/ReadyThread/ThreadPriority는 유지하고
FileIO·Registry·SampledProfile은 추가하지 않는다. Memory64KiB×1024버퍼, 기존8초 guard와
독립 종료 감시·해시 잠금·새 결과 경로를 유지한다. 기존 묶음과 증거는 수정하지 않는다.

예: 동일 프로세스의 두 전용 스레드 중 하나가 이벤트를 기다리고 다른 스레드가100ms 간격으로
8회 SetEvent를 호출한다. 네이티브 TID·QPC와 SetEvent 전후 구간·수신 시각을 메모리에
모았다가 종료 후 기록한다. 일반 권한에서 정상8회와 의도적 첫 신호 누락의 실패·스레드 정리를
먼저 검증한다. WPR 프로파일 해석과 변경된 실행기 제어/거부 검사를 수행한 뒤 관리자 실제
추적으로 준비 이벤트·스택·통제된 호출자 연결과 보존 범위를 대조한다. 관리자 실행이 미완료면
프로파일 구문/fixture 통과를 실제 추적 검증으로 표시하지 않는다. 새 권한 경로나 영구 설정은
자동 생성하지 않으며, 새 전체 백업·제품 수정·장비 제어·운영 승격은 없다.

실행 대기 중에는 결과 해독기를 독립 준비한다. 기존 고정 TraceEvent4.0.0 프로젝트를
새 경로에서 빌드하여 ReadyThread/CSwitch/Thread 원 payload에 StackWalk 원 payload를
함께 내보낸다. 예: EventTimeStamp QPC와 stack PID/TID를 원 바이트에서 읽되 없는 호출자를
헤더의 직전 실행 문맥으로 채우지 않는다. 원 ETL 해시·새 출력 경로·파일/이벤트/시간 예산을
적용하고 stack reference는 원문만 보존해 미해결로 표시한다. 기존 스택 미수집 ETL의 음성
대조에서 스택0을 유지하는지 확인한다. 빌드·음성 대조를 실제 새 스택 연결 검증으로
표시하지 않으며, 실제 신호8회의 연결은 승인된 독립 실행 후에 수행한다.

2026-10-17 권한 승인 후 기존 Explorer의 `Document.Application.ShellExecute` 경로도 확인한다.
먼저 추적을 시작하지 않는 프로브로 일반 권한·x64·상위 Job 밖 실행과 종료를 확인하고,
검증된 launcher 바이트를 같은 경로에서 실행한다. 정상 Windows 권한 상승과 기존 독립 감시
조건을 유지하며 예약 작업·서비스·계정·영구 실행 정책을 추가하지 않는다.
실제 StackWalk는 같은 event QPC/PID/TID로 연결하고 각 원 레코드의 CPU도 독립 대조한다.
사용자/커널 스택 조각의 출력 CPU가 다를 수 있으므로 CPU 동일 여부를 조각 결합의 필수 조건으로
삼지 않는다. 통제된 신호구간의 유일한 ReadyThread와 발신자 식별을 확인한 범위만 보고한다.

### 5.63 ReadyThread 스택의 동일 조건 로컬 비용 비교

같은8회 신호 fixture와 동일 Memory64KiB×1024버퍼·Loader/스케줄 키워드에서 ReadyThread
스택 태그만 OFF/ON으로 바꾼다. 순서는 OFF→ON→ON→OFF로 고정하고 매번 새 독립 추적과
정리를 확인한 뒤 다음 조건으로 간다. 기존8초 guard·60초 stop·해시 잠금은 변경하지 않는다.
fixture 전후의 QPC 구간, 프로세스 CPU·private bytes, 시스템 idle/kernel/user 누적 시간을
기록하고 신호별 SetEvent 시간·발신→수신 시간, 추적 시작/저장 시간·ETL 크기를 비교한다.
예: 시스템 busy 시간은 kernel+user-idle 차분이며 배경 작업을 포함하므로 추적 자체 CPU로
표시하지 않는다. 파일 저장 구간과 신호 구간도 분리한다. 초기화는 추적 전에 수행한다.
계측을 추가한 fixture는 일반 권한의 정상/신호 누락 조건과 정리를 먼저 검사한다.
4회32신호의 작은 비교는 장기 성능 보증이나 서버200ms QA가 아니다. 관찰한 차이와 순서/
배경 부하 한계를 보고하고, 큰 지연이나 정리 실패가 있으면 서버 적용 전에 원인을 확인한다.

### 5.64 승인된 제한 서버 ReadyThread 추적

기존 동시 API 진단에 별도 `health-ready-concurrent` 요청/계약을 추가한다. 로컬에서 검증한
ReadyThread 전용 스택 프로파일 SHA256을 고정하고, 기존 CPU 샘플 계약/프로파일은 그대로 둔다.
새 모드는 CPU 샘플을 수집했다고 표시하지 않는다. 예: health와 기존 data6초/image0.25초 요청을
최대900초 기록하며 첫200ms 초과 응답이나 기존 오류 조건에서 추적을 저장한다. 기존960초 감시,
60초 저장 한도·프로세스 세대·설치/설정 해시·원자적 파일 전달·연결 중단 정리를 유지한다.
신규 범위에 대한 요청/계약/프로파일 혼합 거부와 정상/실패 정리 검사를 실행한다. 실행 도우미는
검증된 소스와 고정 묶음으로 발행하고 서버 로컬 최종 전달/검산 후 SSH로 수행한다.
진단 중 HTTP 지연은 성능 QA로 승격하지 않는다. 실제 요청 구간과 원 ReadyThread·스택의
시간/프로세스/스레드 연결이 확인된 범위만 원인 조사 근거로 사용한다. 서버 작업 종료 후 앱을
작업자에게 보이는 상태로 확인하며 작업번호나 장비 설정은 진단을 위해 임의 변경하지 않는다.

### 5.65 보존된 모듈 기록의 독립 대조와 설치본 식별

같은 고정 ETL의 Image/DbgID 기록을 별도 TraceEvent 해독기로 읽고 기존 Windows XML과
GUID·opcode·version·QPC·CPU·payload 및 중복 수를 대조한다. 예: XML이 원 바이트 대신
Image 필드를 제공하면 크기·시각·서명/예약 필드·파일명까지 모두 재조립하고 생략된 바이트가
없는지 비교한다. 알 수 없는 구조는 거부한다. 기존 해독기/증거는 변경하지 않는다.

모듈 주소 범위와 ImageID/RSDS를 PID·base로 연결하고, 설치 당시 고정 payload의 실제 파일
해시·PE size/checksum/timestamp·RSDS GUID/age/name을 검산한다. Loader timestamp가0이면
동일하다고 판정하지 않고 미제공으로 기록하며 별도 ImageID 시각을 사용한다. OS 파일 바이트를
읽지 않았다면 그 범위를 명시한다. PDB나 함수명이 없는 상태를 호출 함수 확인으로 표시하지 않는다.
종료 시 모듈 목록만으로 과거 전체 적재 수명이나 미보존 요청의 원인을 입증하지 않는다.

### 5.66 정확히 일치하는 PDB와 호출 주소 연결

공식 배포의 기호 패키지는 설치하지 않고 필요한 PDB 데이터만 추출한다. 설치본/추적의 RSDS와
PDB GUID·info age·DBI age를 대조하고, 명시적 로컬 경로에서 DbgHelp의 exact-symbol 옵션으로
조회한다. 실제 적재 PDB의 경로·해시·식별자를 확인하며 export fallback이나 가장 가까운 이름은
성공으로 취급하지 않는다. 주소가 크기0이 아닌 함수 범위 안에 있을 때만 함수 이름을 붙인다.
예: 중복 주소·잘못된 RVA·함수 범위 이탈·export 연결을 거부하고 원 프레임 순서를 검산한다.

집계 단위는 ReadyThread 스택에 함수가 포함된 횟수이며 API 호출 수·CPU 점유율과 구분한다.
Python 앱 프레임이 없으면 파일 경로나 업무 기능을 추정 확정하지 않는다. 정상8요청 분석에서
얻은 기호는 실제 이전 지연 기록의 모듈 식별을 별도로 대조한 뒤 활용한다. 정상 구간의 GIL
해제나 파일 탐색만으로 원120분 지연 원인을 확정하거나 제품을 수정하지 않는다.

### 5.67 이전 지연 샘플의 프로세스별 기호 연결

기존 지연 기록의 원 ImageID/RSDS/Loader를 PID·base와 연결하고 별도 TraceEvent의 모듈 식별과
대조한다. 같은 주소가 다른 프로세스에 나타나도 PID/모듈/주소 조합을 유지한다. 예: 진단 도우미의
python312.dll 주소를 운영 백엔드의 주소로 바꿔 넣지 않는다. 현재 참조 바이너리/PDB의 일치는
과거 프로세스의 원 파일 바이트 재회수를 의미하지 않으며, 종료 시 rundown의 수명 한계도 기록한다.
반환된 기호 이름이 함수 범위 밖이면 실제 조회 성공 여부와 무관하게 미해석으로 보존한다.

선택 샘플이 원본의 정확한 부분집합인지, 독립 스택 조각·sample flags·스케줄 구간과 맞는지
확인한다. native 함수의 포함 샘플 수를 CPU 시간이나 원인 비율로 바꾸지 않는다. 앱 프레임이
추가로 필요하면 외부 읽기 도구를 같은 Python 버전의 로컬 fixture에서 먼저 검증한다. PID/스레드
세대·비정지 옵션·불완전 읽기/오류 표시·시간 한도·소유 프로세스 정리를 확인하고, 지역변수·전체
메모리는 수집하지 않는다. 새 도구의 서버 실행은 그 검증과 기존 승인 범위를 확인한 다음 진행한다.

### 5.68 외부 Python 프레임 읽기의 로컬 검증과 현장 결합 조건

공식 Windows wheel의 배포 해시와 추출 실행 파일을 고정하고 실제 버전·CLI 옵션을 기록한다.
설치 없이 사용하며 `dump --json --full-filenames --nonblocking`으로 프레임만 읽는다.
서버와 같은 Python 버전의 일반/frozen 시험에서 알려진 함수 순서·소스 줄 범위·스레드 이름·
native ID를 대조한다. 예: busy_leaf→busy_outer가 빠진 샘플이나 지역변수가 포함된 샘플은 거부한다.
frozen 시험의 Python DLL은 후보 설치본과 해시를 대조하며 제품 전체의 동등성으로 확대하지 않는다.

보호 실행은 기존 Windows Job 구현을 활용해 새 진단 worker를 먼저 배정하고 실행 gate를 연다.
대상 앱은 Job에 넣지 않는다. 실제 정상 읽기와 시간 제한·출력 상한·제어 프로세스 종료를 시험해
진단 자식 정리와 같은 대상 프로세스의 생존을 확인한다. 예: 각 출력은1MiB까지만 보존하고
초과는 완료로 표시하지 않는다. 제어자 종료로 최종 요약이 없으면 외부 감시 증거와 미완료 상태를
분리한다. 로컬 임의 명령 시험 API를 서버 실행 진입점으로 전달하지 않는다.

현장 사용 전 기존 보호된 실행 경로에 고정 py-spy 바이트·고정 인수·현재 프로세스/스레드 생성
시각·설치/설정 식별·한정 출력 경로를 결합한다. 짧은 소수 관찰로 현재 역할을 먼저 확인하고,
불완전 읽기·시간 범위·관찰 부담을 그대로 보고한다. 비정지 읽기는 원자적 스냅샷이 아니며
현재 스레드 번호로 과거 스레드 역할을 소급 확정하지 않는다. 서버 전달·해시·연결 종료 정리와
운영 화면 복귀 기준을 유지한다. 로컬 기능 시험을 서버 성능 통과나 전체 출시 승인으로 바꾸지 않는다.

### 5.69 고정 Python 프레임 모드의 실행 경로 결합

기존 field_runner의 별도 `python-frames` 모드는 candidate1.0.30과 정수6초 요청만 받는다.
도구 경로는 package/py-spy.exe로 결정하고 요청에 임의 경로·명령·샘플 수를 받지 않는다.
공식 실행 파일의 크기/SHA256을 읽기 공유 잠금 상태에서 전후 검산한다. 각 읽기는2초,
stdout/stderr 각1MiB까지 제한하며 최대3회 수행한다. 기존 앱 설치·설정·인증된 제어 세대
확인과 owned Job 감시를 재사용하고, 이 모드의 외부 실행 한도는600초로 제한한다.
이전 모드의9000초 외부 한도 및 기존15/120분 요청은 변경하지 않는다.

현재 프로세스의 제한 조회/동기화 핸들로 경로·생성 시각·생존을 확인한다. Toolhelp 스냅샷에서
같은 PID의 스레드만 읽기 권한으로 열고, 소유 PID와 GetThreadTimes 생성 시각을 대조한다.
핸들을 읽기 완료까지 보유해 생성 시각과 생존을 다시 확인하며 대상 프로세스/스레드를 제어하지 않는다.
예: 읽기 중 종료된 스레드나 새로 나타나 사전 핸들이 없는 TID는 UNBOUND로 남기고 샘플을
PARTIAL로 표시한다. Python thread.join과 OS 핸들 종료 시점은 구분한다.

알려진 py-spy JSON 배열을 중복 키/비정상 상수 거부 decoder로 읽고 예상 키·프로세스·스레드
중복·문자열/프레임 수·지역변수 부재를 검사한다. 수집 완료와 샘플 완전성은 별개로 저장한다.
현장 전달에는 실제 실행 파일·도구·라이선스·소스 묶음·후보 payload 기준·외부 manifest/launcher
해시를 포함한다. synthetic frozen 시험 harness는 서버 실행 묶음에 넣지 않는다.

### 5.70 현장 Python 프레임 결과의 해석 범위

실제 서버의3회 관찰은 프로세스와 스레드 생성 시각·전후 생존·원 출력에 연결한다. 현재 역할을
과거 ETW의 같은 숫자 TID에 그대로 소급하지 않는다. 예: 현재17460이 이미지 저장 큐에서
대기한다고 확인해도 과거 파일 조회528건이나221.0337ms 응답 지연의 원인은 별도 증거가 필요하다.
Python 프레임이 없는 native 스레드와 비원자적 읽기의 누락 가능성을 함께 기록한다.

개발 PC와 서버 wall-clock의 차이는 출처별 시작·완료 시각으로 구분한다. 설정 시각 검증을
완화하거나 시스템 시각을 바꾸지 않는다. 읽기 시간과 전체 snapshot 경과 시간은 진단의 관찰값이며
앱 응답 지연이나 순수 계측 부담으로 대체하지 않는다. 서버 로컬 전달·전 파일 해시·진단 자식 정리와
운영 화면 전면 복귀를 완료 조건으로 유지한다.

### 5.71 과거 스레드 생성 시각 연결의 판정 범위

과거 ETW의 실제 Start/End와 DCStart/DCEnd 열거를 구분한다. 원 XML과 별도 decoder에서
QPC·CPU·opcode·version·전체 payload·중복 횟수가 일치하는지 대조한다. 같은 TID·payload·
프로세스 필드는 호환 근거이며, 보존 구간 밖의 연속 생존이나 당시 Python 호출을 대신하지 않는다.

과거 HTTP 응답에 native 생성 시각이 있으면 원 body/headers 해시·probe ID·프로세스 세대·
서버/수집기 anchor와 QPC 구간을 재계산한 뒤 현재 native 생성 시각과 직접 비교한다.
예: loop812와 worker16664는 실제221.0337ms 요청의 생성 시각까지 대조할 수 있다.
이미지 writer17460은 과거 생성 시각이 없어 COMPATIBLE_NOT_INDEPENDENTLY_BOUND로 남긴다.
직접 일치한 스레드도 현재 대기 프레임을 과거 실행 함수나 지연 원인으로 소급하지 않는다.

### 5.72 Python 단발 읽기의 QPC 구간

고정 비정지 dump 실행 직전과 출력 수신 완료 직후에 수집기 자신의 native 시계·생성 시각을
기록한다. 기존 clock validator로 같은 프로세스/스레드·주파수·단조 순서·변환 범위를 확인한
경우만 read_window=BOUNDED를 기록한다. 범위는 자식 시작·메모리 읽기·출력 수신을 포함하며
개별 프레임의 정확한 읽기 시각이나 함수 실행 시간을 뜻하지 않는다. 원자적 snapshot도 아니다.

시계 결합 실패 시 원 프레임과 역할 관찰은 보존하되 시간 구간은 UNAVAILABLE로 남긴다.
예: 생성 시각이 다른 두 anchor로 시간 범위를 만들지 않는다. 알려진 함수의 QPC 시작/종료가
전체 reader 범위를 포함하는 실제 시험으로 연결을 검증한다. 짧은 사건이 범위와 일부 겹치는
경우에는 같은 순간의 실행이라고 단정하지 않는다. py-spy의 병합된 chrometrace 상대 시각을
원 메모리 읽기 시각으로 대체하지 않는다. 새 현장 계측 전 비용과 정리 검증을 별도로 수행한다.

### 5.73 지속 Python 읽기의 로컬 검증

py-spy0.4.2의 PythonSpy를 한 프로세스에서 유지하고 각 get_stack_traces 호출 직전/직후
Windows QPC와 원 프레임 배열을 함께 보존한다. NonBlocking을 명시하고 native unwind,
지역변수·자식 프로세스 수집·대상 쓰기/정지는 사용하지 않는다. 초기 연결 시간은 샘플 시간과
분리한다. 비원자적 읽기와 샘플 사이 공백은 남으며 함수 실행 시간으로 해석하지 않는다.

먼저 개발 PC의 소유한 시험 대상만 사용한다. 고정 실행 한도·샘플/출력 상한, 취소·대상 종료·
부모 종료 시 도우미 정리, PID/TID 생성 시각 결합, 알려진 함수 구간을 검증한다. 직접 QPC와
외부 경계 대조, 같은 조건의 비수집/수집 비교를 통해 시간 해상도와 부하를 별도로 판단한다.
예: 샘플이 다른 함수 구간과 겹치면 확정 연결을 하지 않고, 읽기 실패도 원 순서에 남긴다.

공식 도구 체인과 소스는 실행별 로컬 폴더에 해시·라이선스와 함께 보존한다. 새 reader를
기존 PF30/고정 py-spy 실행 파일로 가장하거나 원 해시 묶음을 수정하지 않는다. 실제 빌드·
동작·정리·비용을 확인한 뒤에만 현장 적용 묶음과 보호 실행 연결을 검토한다.

### 5.74 지속 읽기와 HTTP 수집의 결합

새 `python-health` 모드는 1.0.30과 6초로 고정한다. 기존 설치 파일·설정·인증된
실행 세대의 전후 검사를 통과한 구간에서만 고정 reader를 3회 실행한다. 각 실행은
100회/20ms이며 초기화와 실행 사이 공백을 보존한다. 도구 경로는 묶음 내부로 제한하고
실행 파일의 크기와 SHA256을 잠긴 핸들로 확인한다. 자식은 기존 수집기 Job에 속한다.

HTTP 수집과 별도 스레드에서 stdout/stderr를 상한 내 수신한다. 취소·시간 초과·잘못된
출력은 원 바이트와 실패를 남기고 자신의 reader만 정리한다. 예: 잘린 JSONL, 샘플 누락,
QPC 역행, 다른 PID/생성 시각 또는 추가 JSON 멤버를 정상 수집으로 처리하지 않는다.

원 HTTP 응답을 다시 검증한 후 QPC 빈도와 PID/TID 생성 시각이 일치할 때만 프레임을
연결한다. 요청 전체와 단계별 구간에 완전히 포함된 읽기, 경계만 겹친 읽기, 미관측을
구분한다. 비원자적 프레임은 CPU 시간·GIL 경합·지연 원인을 증명하지 않는다. 기존 ETW
시작 이후 reader를 시작하고, reader 정리와 결과 결합 이후 ETW 종료를 요청하는 순서를
유지한다. 실제 ETW 실행·완성된 frozen 묶음·현장 비용은 별도 검증 전 미완료로 남긴다.

### 5.75 지속 읽기용 실제 추적 계약

6초 Python/HTTP 수집은 별도 요청·계약·lease schema로 기존 독립 WPR coordinator에 연결한다.
ReadyThread stack을 포함한 기존 검증 profile 바이트를 사용하고 30초 guard와 소유 세션만
종료하는 절차를 유지한다. 900초 concurrent/outlier 모드와 혼용하지 않는다. 예: Python
요청을 기존 도구 없는 패키지로 실행하거나 기존 계약으로 바꾸면 시작 전에 거부한다.

전용 패키지는 기존 구성에 고정 reader 한 파일만 추가한다. 공개 요청은 도구 경로를 받지
않고 관리자 launcher가 해시 확인 후 보관한 inputs 안의 파일만 선택한다. 도구를 고정한
핸들과 기존 참조 잠금을 전체 실행 동안 유지한다. 실제 통합 시험은 합성 대상·고정 요청으로
진행하며 운영 payload hash 검사를 합성 값에 맞춰 약화하지 않는다. 합성 시험용 진입점은
별도 표시하고 운영 묶음에서 제외한다. 실제 ETL의 시계·손실·세대·같은 구간 coverage를
읽기/HTTP 원자료와 비교하기 전에는 추적 저장 성공을 인과 분석 완료로 취급하지 않는다.
### 5.76 비차단 Python 읽기 누락의 명시적 보존

2026-10-18 실제 1.0.30 Sandbox 실행 두 번에서 각각 100회 중 1회가
`Failed to call get_stack_trace for thread ...`로 끝났다. 앱을 멈추지 않는 읽기의
실패 원인은 아직 미확정이다. 기존 엄격 경로의 실패 기록은 보존한다.

- 새 Python+ETW 진단 경로만 완전한 100개 시도와 종료 레코드가 있을 때 개별
  읽기 실패를 보존한다. 기존 Python 단독 경로는 계속 0오류를 요구한다.
- 실패 레코드는 `stacks=null`, 유효한 순번·QPC 구간·제한된 오류 문자열이어야
  한다. 종료 레코드의 오류 수가 실제 실패 수와 같아야 하고 취소·잘림·전체 실패는 거부한다.
- 오류가 있는 종료 코드 1은 고정 reader의 정확한 `reader-incomplete` 메시지와
  위 완전한 레코드가 함께 있을 때만 해석한다. 다른 종료·stderr는 거부한다.
- 결과는 `CAPTURED_WITH_READ_GAPS`로 구분하고 성공/실패 시도 수와 누락 QPC를
  기록한다. 누락은 요청별 겹침 목록에 별도로 남기며 Python 함수 일치에 포함하지 않는다.
- 수집 완료는 스택 품질 통과가 아니다. ETW 범위·인과관계·현장 및 출시 판정은
  별도 검증 전까지 미평가/HOLD다. 예: 300회 중 2회 누락 → 298회 해석,
  2개 누락 구간 보존, 누락 구간의 실행 함수 추정 금지.

### 5.77 재시작 없이 관찰 시간 전체를 포함하는 읽기

PYTRACE에서 세 번째 요청이100회 묶음 재시작 사이에 놓였다. 새 reader는 한 프로세스에서
고정350회/20ms를 읽는다(마지막 예약 시각6.98초). 기존8초 자체 종료·9초 외부 제한,
16MiB/행1MiB 출력 제한, 비차단/locals 없음/자식 제외, PID+생성 시각 검사를 유지한다.
350회는6초 관찰과 준비250ms를 포함하기 위한 고정 여유이며 사용자가 바꾸는 옵션이 아니다.

새 schema와 새 바이너리 hash를 소비기와 package에 고정한다. 원100회 reader와 과거
봉인 묶음은 그대로 보존한다. 새 단독/추적 경로 모두 reader 한 번만 시작하며 단독 경로의
0오류 조건과 추적 경로의 명시적 누락 처리는 유지한다.

수집기는 관찰 시작/끝을 reader와 같은 native QPC로 변환하고 6초 관찰 구간 전체가
첫 읽기 시작과 마지막 읽기 종료 사이에 포함되는지 검사한다. 프로세스·스레드 native HANDLE은
한 번의 전체 읽기 동안 보유한다. 각 읽기 사이20ms 샘플링 공백·실패·스케줄 지연은 별도
기록하며 ‘연속 읽기’가 모든 순간의 함수 관찰이나 모든 짧은 요청과의 겹침을 뜻하지 않는다.
예: 요청이 두 샘플 사이에 끝나면 `NO_READ_OVERLAP`이며 수집 범위 포함과 구분한다.

검증: 고정 횟수/schema/이전 byte 거부,6초 범위 부족 거부, 기존 원 요청·설정·세대 검사,
실제 정상/취소/잘못된 세대/대상 종료/출력 정지 제한/부모 Job 정리, frozen 보호 실행을
확인한다. 제품 설치본 재빌드나 같은 설치 매트릭스 반복은 하지 않는다.

### 5.78 빈 Python 스택을 별도 공백으로 보존

현장 PYWFIELD의350회 중5회는 reader 오류이고, 별도1회는 유효한 스레드 행에
빈 `frames=[]`가 있었다. 빈 스택의 발생 원인·당시 실행 함수는 미확정이다.
기존 엄격 decoder의 `frame-stack-budget` 실패와 현장 launcher FAIL은 보존한다.

새 명시적 누락 정책에서만 빈 스택을 허용하되 전체 행의 PID/TID·중복·필드·예산·
locals 금지 검사는 유지한다. 빈 스택이 하나라도 있는 샘플 전체를 함수 대조에서
제외하고 순번·QPC·해당 TID를 별도 frame gap으로 남긴다. 단독 엄격 경로는 계속 거부한다.
reader 오류 수는 원 종료 레코드와 대조하고, 빈 스택 수를 reader 오류에 합산하지 않는다.
예:350시도/reader 오류5/빈 스택 샘플1 → 성공한 reader 응답345, 함수 대조 가능344,
명시적 공백6.0오류 exit0에도 빈 스택이 있으면 품질은 `CAPTURED_WITH_READ_GAPS`다.
전체 샘플이 공백이면 거부하며, 다른 malformed JSON·초과 스택·잘린 출력은 허용하지 않는다.

회귀 검증은 원 현장 바이트의 실패 재현과 수정 decoder의 별도 재해석, 엄격 경로 거부,
누락 정책의 잘못된 필드 거부·오류 수 대조·함수 일치 제외를 포함한다. 과거 결과 JSON을
고치지 않으며, 재해석 성공은 설치/설정 종료 검증을 누락한 현장 실행을 PASS로 바꾸지 않는다.

### 5.79 같은 추적·요청 조건의 Python 진단 비용 비교

회수한 PYEFIELD의6초 구간에서 reader의 배정 CPU 시간은1,696.7962ms였다.
기존 기본 health 모드는 profile603c872d, Python 모드는 ReadyThread stack을 포함한
profile03220768을 사용하므로 두 모드의 결과 차이를 Python 진단만의 비용으로 해석하지 않는다.
기존3스레드 합성 대상의 짧은 OFF/ON 결과도 실제 앱의 현장 부담 상한으로 사용하지 않는다.

비교 질문은 ‘같은1.0.30 앱·HTTP 요청·ReadyThread 추적에서 Python observer 전체를 켜면
요청 지연과 배정 CPU 시간/프로세스 CPU 시간이 얼마나 달라지는가’다. 개별 함수 읽기만의
비용과 초기 연결·프레임 전달·검증을 포함한 전체 observer 비용을 혼동하지 않는다.

1. 먼저 격리된 실제 frozen 앱에서 고정 OFF→ON→ON→OFF 순서를 두 번 실행한다.
   각 구간6초/HTTP3건/2초 간격, 동일 Ready profile·30초 독립 guard를 유지한다.
   앱과 요청 스케줄·수집/쓰기 방식·우선순위·affinity·탭 수는 두 조건에서 같다.
   ON만 현재 고정350회/20ms reader와 소비기를 사용한다. OFF는 동일 비교 계약에서
   observer를 시작하지 않는다. 기존 요청의 schema/해시를 조작해 OFF를 위장하지 않는다.
2. 전용 비교 계약과 두 조건의 차이를 먼저 검증하고 새 패키지로 식별한다. 기존 설치본·
   설정·실행 세대·원 응답 대조, 출력 예산, 독립 종료/정리, 명시적 읽기 공백을 유지한다.
   아래5.80에 비교 계약 구현과 검증 범위를 기록한다. 이전 완성 패키지가 이 조건을 이미
   지원한다고 보고하지 않으며 새 패키지의 실제 비교 실행은 별도 확인한다.
3. 요청별 원 지연·route 단계·예정/실제 시각, 샘플 범위/누락, ETW 손실과 세대,
   reader/수집기/backend 각각의 CPU 시간과 스케줄링 시간을 구분해 기록한다.
   원자료로 각 OFF/ON 쌍의 차이와 변동 범위를 보고하며 드문 최댓값의 상한을 추정하지 않는다.
4. 세대/설정 변경·요청 누락·trace 손실·정리 실패는 해당 비교를 미완료로 남긴다.
   불리한 결과를 버리거나 원하는 결과가 나올 때까지 반복하지 않는다. 로컬 결과는 현장
   영향의 증명이 아니며 현장 비교가 필요한지는 결과와 현재 부하를 근거로 결정한다.

모든 계획된 health 요청200ms 이내 등 기존 출시 기준을 바꾸지 않는다. 비교 목적만의 새 합격 임계값을
만들거나 짧은 성공을120분 통과로 바꾸지 않는다. 기존221.0337ms 실패 당시 새 reader는
없었으므로 이 observer가 과거 실패를 만들었다고 주장하지 않는다. 제품 수정·전체 백업·
반복 설치 또는 새120분 시험은 이번 비교 설계만으로 실행하지 않는다.

### 5.80 고정 Python OFF 비교 계약

ON은 기존 `sfl-python-health-trace-request-v1`, OFF는 새
`sfl-python-health-baseline-request-v1`로 구분한다. OFF에는 별도 contract/lease/scope를
부여해 ON·기본 health 계약의 바꿔치기를 거부한다. 두 경로는 같은 새 실행 파일과 Python
패키지를 사용하고, 사용하지 않는 OFF reader도 같은 파일·해시로 잠가 준비 조건을 맞춘다.

OFF는1.0.30만 허용하며6초 관찰·30초 독립 trace guard·600초 전체 launcher 예산과
Ready profile03220768을 ON과 동일하게 고정한다. 실제 collector의 HTTP 루프는 공통이다.
OFF worker는 Python companion을 만들지 않고 `_python_frames=None`으로 전달한다.
기존 설치본·설정·실행 세대·원 응답 확인, 출력 제한, 정상/실패 정리와 출시HOLD를 유지한다.
예: OFF 요청에900초 또는 spec 내부 `python_frames=true`를 넣으면 시작 전 거부한다.

소스 관련96개 범위(첫 실행80개와 fixture 수정 후 trace16개), PowerShell 패키지 거부21조건,
새 frozen 실행 파일의 describe 및 내부19모듈·진입 코드 일치를 확인했다. 첫 fixture 파일
누락 실패는 보존한다. 이 검사는 실제8구간 OFF/ON 실행이나 새 baseline의 관리자 WPR
종료·정리 검증을 대신하지 않는다. 후속은 새 패키지를 격리 실제 앱에서 실행하는 단계다.

### 5.81 비교 기록의 CPU 경계와 해석 범위

실제 PYAB 비교는 예비 OFF 이후 OFF→ON→ON→OFF 두 차례를 같은 앱/설정 세대에서
실행했다. 프로세스 핸들을 종료까지 유지해 reader/collector의 전체 CPU 시간을 읽었으며,
backend CPU 차이는 각 보호 실행 전후 구간이다. 이 값들을6초 구간의 CPU 사용량으로
바꾸지 않는다. 동일한200ms 간격의 보조 프로세스 탐색기를 양쪽 조건에 사용하고 그 비용도 남긴다.

CSwitch 구간은 앞뒤 전환으로 묶인 부분만 합산한다. 예:12논리 CPU의6초 중 한 CPU의
끝768.938ms에 후속 전환이 없으면 이를 idle로 추정하지 않고 `unbracketed`로 기록한다.
추적 header의 논리 CPU 수로 전체 분모를 정하고 관측되지 않은 CPU도 미확인 시간에 포함한다.
원 HTTP/native clock·ETW 두 해석기·프로세스 세대·출력 해시·설정/설치파일 종료 검산은 유지한다.

짧은 모의 장비 시험의 요청24건과 관찰 차이는 현장 지연 상한·통계적 유의성·과거221ms 원인을
증명하지 않는다. 후속 현장 진단은 기존 SSH 승인 범위, 현재 세대·설정·공간, 고정된 순서와
동일한 추적 조건을 확인하고 진행한다. 앱 재설치·전체 백업·120분 반복은 자동으로 추가하지 않는다.

### 5.82 현장 비교의 시각 기준과 보조 관찰 비용

현장 준비 스냅샷의 시각은 서버에서 생성된다. 개발 PC 시각과 직접 대조한 결과가
`configuration-time-order` 하나만 실패하면 원 판정을 보존하고 SSH 요청 전후 개발 PC 시각과
응답의 서버 UTC를 함께 기록한다. 예: 서버가 개발 PC보다 약10초 빠르면 서버에서 방금 읽은
설정도 개발 PC 기준으로 미래처럼 보인다. 시계나 원 스냅샷을 변경하지 않는다.

준비 단계에서는 다른 설정 조건이 모두 일치해야 하며, 서버 기준 승인 시각≤수집 시각≤관찰 시각+2초,
수집 나이−2~5초, SSH 요청 정상 종료와30초 이내 전송 범위를 별도로 확인한다. 시각 외 불일치,
오래된 수집·역전·잘못된 UTC는 거부한다. 이 결과는 준비 승인에 한정하며 실제 서버에서 실행하는
고정 도우미의 기존 시각·설정·프로세스 검증을 대체하거나 완화하지 않는다.

현장 OFF/ON은 격리 시험과 같은 패키지·추적 profile·6초/3요청·고정 순서를 사용한다.
양쪽 모두 같은 PowerShell 보조 관찰기가200ms 간격으로 프로세스 핸들을 보유해 종료 후 CPU를
읽는다. 보조 관찰기 자체 CPU, reader/collector 전체 수명 CPU와 backend의 보호 실행 전후 차이를
분리한다. 로컬 Python 관찰기와 현장 PowerShell 관찰기의 수치를 동일 계측 비용으로 취급하지 않는다.
각 회차의 종료·로그 닫힘·해시 결합을 확인한 뒤 다음 회차를 시작하며, 실패한 회차를 자동 재실행하지 않는다.

큰 오프라인 해석 산출물은 개발 PC 여유 공간을 확인해 승인된 날짜별 공유 `records` 아래에 저장할 수 있다.
원 ETL·입력 해시·해석 명령 종료 코드·출력 위치를 함께 남긴다. 공간 확보를 위해 봉인 증거를 삭제하지 않는다.


### 5.83 요청·Python 읽기·스레드 전환의 구간 결합

기존 봉인 HTTP/native clock/원 Python stream/CSwitch·ReadyThread·thread payload를 해시로
확인한 뒤 같은 QPC 구간에 연결한다. 시작·끝 시각의 불확실성은 안쪽/바깥쪽 경계로 유지한다.
실행 배정은 앞뒤 CSwitch로 묶고 독립 누적 적분값의 차이로 재계산한다. 요청 단계 합과
수집기 배정+Ready/Wait/미확인 전환 후 구간 합이 해당 요청 경계와 일치하는지 확인한다.

예:36.3290ms 요청의 connect_ms29.2955ms에는 시계 확인과 Python 준비가 포함된다.
이를 순수 네트워크 지연으로 바꾸지 않는다. 읽기 envelope가 route에 조금 겹쳐도 읽기가
비원자적이면 그 프레임이 route 안에서 실행됐다고 확정하지 않는다. 구간 밖 표본을 근접 보간하지 않는다.

OldThreadState1은 Ready 전환 관찰로 기록한다. 다음 switch-in까지 경과 시간을 남기되,
관찰되지 않은 상태 전이·연속 우선순위·affinity를 추정하지 않는다. wait-mode의 legacy 범위와
일치하지 않는 원 바이트는 해석하지 않는다. 프로세스 종료 시점 rundown 이름은 전체 수명 증명이 아니다.
후속 ReadyThread 스택은 깨우는 호출자 정보이며, 깨워진 스레드의 CPU 작업 스택으로 치환하지 않는다.
사용 profile의 CPU sampling/CSwitch stack/FileIO/Registry 부재를 분석 한계에 명시한다.


### 5.84 기존 Ready 호출 문맥과 그래픽 비교 준비

ReadyThread QPC의 전체 중복 개수와 StackWalk의 원 이벤트 시각·PID/TID를 확인한다.
raw payload와 구조화 Stack1..N 모두 원문 바이트로 대조하며, Image 전체 필드와 Process 안전 필드를
독립 해석기와 비교한다. kernel-only 문맥을 해당 프로세스의 직접 깨우기 원인으로 해석하지 않는다.
직전 요청 밖 문맥·요청 안 이벤트를 분리하고, 미확정 프레임과 종료 시점 목록의 수명 한계를 유지한다.

예: d3d10warp가 호출 스택에 보이면 그래픽 비교의 후보로 기록하되 CPU 비용으로 환산하지 않는다.
과거 CPU 표본은 비프로세스/DPC/ISR를 제외하고 기존 해시·주소·모듈 순서를 확인한 범위만 재집계한다.
현재 가속 OFF는 PR144 시작 성능 개선이므로 운영 기본값을 자동 변경하지 않는다. 격리 비교는
같은 화면·입력·관찰 조건, 실제 graphics backend 차이, CPU/프레임/HTTP, 종료·정리를 확인한다.
차이가 적용되지 않으면 비교 불성립으로 기록한다. 제거 후보에는 기존 설치 앱20회 시작 gate도 적용한다.


### 5.85 격리 화면 그래픽 비교의 적용 범위

후보 설치본에서 추출한 화면은 기존 manifest와 파일별 검산한다. 제품 main/backend를 사용하지 않으면
그 범위를 분리한다. 숨김 native 창도 document.visibilityState는 visible일 수 있으므로 두 값과 focus,
최소화 이벤트를 함께 확인한다. API 누락·시각 누락·화면 밖 차트가 있는 준비 실행은 비교에서 제외한다.

CPU는 PID+생성시각이 같은 프로세스의 누적 CPU초 차이를 사용하고 프로세스 교체/누락을 거부한다.
예:GPU 프로세스 CPU2초는 GPU 사용률이 아니다. rAF16.7ms는 물리 표시 프레임 증명이 아니다.
모의HTTP는 실제 health gate와 구분하고, 고정 영상/규칙뿐 아니라 실제 요청 개수·표본 위상 한계를 기록한다.
공유 캐시와 observer 부하를 명시한다. 비용 개선이 관찰되지 않으면 운영 기본값 변경 근거로 사용하지 않는다.


### 5.86 현장 그래픽 경로의 적용 가능성

개발 GPU 비교는 현장의 GPU/드라이버/논리 CPU와 구분한다. WMI video와 signed-driver 목록의
PNP 장치 ID·이름·버전을 교차 확인한다. 현재 프로세스 명령행의 역할은 정밀 생성 FILETIME으로
기존 trace 전체보다 이르게 생성돼 현재까지 살아있는지 확인한 뒤 과거 같은 PID에 연결한다.
예: GPU 프로세스의 WARP 인자는 선택 경로이며 단독 지연 원인이나 GPU 하드웨어 사용량이 아니다.
기본 가속 가능성은 다른 장치의 성공으로 추정하지 않고 별도 프로필·고정 실제 규모 화면·정상 정리를 갖춘
격리 경로에서 확인한다. 읽기 조사만으로 설정 변경·드라이버 업데이트·설치를 자동 수행하지 않는다.


### 5.87 현장 표시 위젯의 제한된 그래픽 비교와 CPU 누락

현재 현장 layout의 보이는 위젯·영상 범위로 별도 비교를 정의할 수 있으나,5.85의 전체 차트 시험을
충족했다고 바꾸지 않는다. 고정 수치·반복 JPEG·관찰 비용·원래 앱의 동시 실행 한계를 기록한다.
native/document focus와 실제 graphics backend,각 요청 결과,잠긴 입력,종료·정리를 확인한다.
PID+생성시각 집합이 바뀌면 전체 CPU 합계와 정확한 쌍별 중앙값은 미확정으로 유지한다.
예: 한 표본에서 나타난 GPU의 최종 CPU값이 없으면 고정 프로세스 소계만 표기한다.
기능/정리 검증의 성공으로 CPU 누락 실패를 덮지 않고,통과 결과를 얻기 위한 선택적 재시험도 하지 않는다.
관측 소계만으로도 개선 주장을 지지하지 않으면 설정 변경 후보를 채택하지 않는다.


### 5.88 과거 이미지 drop의 실행 세대와 완료 전 정체

다른 버전의 재현을 그대로 과거 사건의 원인 근거로 쓰지 않는다. 정확한Git blob 소스를 추출해
네트워크/외부쓰기 없이 원래enqueue·writer·종료 경로를 확인하며 합성시간/규모 한계를 기록한다.
원문body가문자열이면내부JSON까지해석하고manifest·PID생성시각·SPOT세대·종료영수증을연결한다.
예: 세 표본에서fact가완료보다1개앞서고queue가증가하면정체관찰로기록하되,
비원자적getter·상태잠금·스케줄링·fact추가후작업의불확실성을유지한다.
drop수는거부시도이며고유이미지수로환산하지않는다. drained와historical integrity미해결은함께참일수있다.


### 5.89 과거 저장 대기와 원본 파일 시각의 연결

기존 인덱스에서 사건 주변의 유한한 행 집합을 선택하고, 대장 ordinal·capture ID·크기·SHA와
원본 보존 목록의 행번호·시각을 연결한다. 예: fact N 뒤의128개가 뒤늦게 수정된 경우 큐 용량과
대조하되, 촬영 공백을 연속 정체로 해석하거나 수정 시각을 실행 trace로 간주하지 않는다.
실제 drop 시도 기록이 없으면 고유 누락 수를 만들지 않는다. JSON/일반 텍스트가 섞인 로그를
함께 분류하고 시각 직렬화 해상도보다 작은 차이로 실행 순서를 단정하지 않는다.
주기와 위치가 맞는 함수는 원인 후보로 유지하며 실제 규모 비용/실행 증거를 확보한 뒤 수정한다.


### 5.90 실제 보존 사본의 삭제 없는 순회 측정

정확한 과거 함수 AST를 추출해 쓰기/삭제를 차단한 경로로 실제 파일 시스템 비용을 측정한다.
새 결과 폴더와 외부 고정 소스 해시, 현재 서버 identity, 입력EOF·soft/hard 제한·잔류 확인을 갖춘다.
예: glob319,971항목은 전체 이미지 내용 검증319,971건을 뜻하지 않는다.
stat 호출 계측·reparse 검사·다른 Python 버전의 비용을 명시하고 원래 프로덕션 성능으로 단정하지 않는다.
삭제를 차단했으므로 삭제 비용은 제외하며 inclusive 호출 시간은 합산하지 않는다.
과거 디렉터리 상태·cache·스케줄링 차이를 유지하고 한 회차 결과로 과거 drop 원인을 확정하지 않는다.
측정 종료 후 원래 앱 세대·화면 복귀와 결과 회수 해시를 확인한다. 개선은 보존 규칙과 큐 종료 책임을
유지하는 분할 순회/시간 예산 설계부터 검토하며, 통과값을 얻기 위한 같은 규모 재시험은 추가하지 않는다.


### 5.91 보존 정리의 협력적 분할 실행과 큐 수명

실제 서버 사본의91.094초 순회와 현재 동일 함수 AST를 근거로, 한 번의 저장에서 전체 정리를
동기 완료하는 구조를 보완한다. 이 구조적 비용의 수정은 과거 drop15 직접 원인 확정과 구분한다.
기존 writer가 정리 iterator를 소유하며 추가 스레드는 만들지 않는다. 한 호출은 최대256개
순회 단계 또는 monotonic10ms 이후 다음 단계 전에 반환한다. 단일 OS 호출의 hard 시간 상한은 아니다.
기존3600초 시작 주기·mtime의 strict cutoff·관리 파일명/확장자/날짜 경로 조건은 유지한다.
날짜 디렉터리와 파일도 scandir로 지연 순회해 큰 목록을 한꺼번에 생성하지 않는다.
새 캡처 뒤 한 분량을 진행하고, 캡처 큐가 비었을 때는 시작된 정리만 이어간다.
예: 진행 중 정리는 wall clock의 다음3600초를 기다리지 않고 이어가며, 유휴 상태만으로 새 정리를 시작하지 않는다.
종료/설정 교체 때 해당 writer의 iterator를 닫아 OS 핸들을 정리한다. 미완료 정리를 완료로 보고하지 않는다.
캡처·대장·drop/실패 계수·manifest·정상 종료 판정은 기존 계약을 유지한다.
회귀 조건: 단일 저장의 단계/시간 예산, 유휴 진행의 완주, 관리 파일만 만료 삭제, cutoff 경계,
오류 후 다음 주기 재시도, 비활성화/종료/설정 교체의 핸들 닫힘, 큐 회계와 정상 종료 검증.

5.91 보완: 빈 연·월 폴더를 일반적으로 지우지 않고 실제 관리 날짜 폴더 제거 후의 부모만 정리한다.
유휴 중 설정 서명이 바뀌거나 writer가 교체되면 이전 iterator를 닫는다. 링크/reparse 표식은 건너뛴다.
캡처/대장 메서드와 큐 완료·실패 집계는 AST로 불변을 확인하며,최종13회귀를 전체 백엔드에 포함한다.


### 5.92 새 보존 정리 경로의 실제 규모 분할 계측

커밋80fee9aa의 네 retention 메서드와 두 조건 helper AST를 고정하여 기존 현장 보존 사본에서
삭제 없는 투영을 실행한다. 원래 함수의256단계/10ms 제어는 바꾸지 않고 호출별 시간·yield 수,
scandir 항목·열림/닫힘·최대 동시 핸들, 전체 완주·CPU를 기록한다. unlink는 계수만 하고
rmdir는 ENOTEMPTY로 억제한다. 계측·삭제 억제·연속 호출의 차이를 명시한다.
예: 호출 사이 대기 없이 계측한 총 시간은 실제 큐의100ms 유휴 대기 포함 시간이 아니다.
원래 함수가 OSError를 삼켜도 계측 오류·미완주로 구별하며 완료로 보고하지 않는다.
EOF·soft deadline·hard deadline·원본 쓰기 차단·도중 오류를 작은 로컬 사본에서 검사한다.
서버 실행은 기존SSH/외부 고정 해시/읽기 잠금/새 결과 폴더를 사용하고 결과 회수 해시와
소유 프로세스 종료·Smart Factory 화면 복귀를 확인한다. 파일 삭제·설치·새 전체 백업은 없다.
기존 전체91초 순회를 재실행하지 않고 새 코드 경로만 측정하며, 현장 QA와 과거 원인 확정은 별도다.

5.92 사전 계측 보완: 개발 Python3.12.6의 monotonic은 GetTickCount64/15.625ms이고
perf_counter는 QueryPerformanceCounter/0.0001ms이며 둘 다 단조·비조정 시계다.
10ms 예산 검사에는 perf_counter를 사용한다. 저해상도 시계가 아직 움직이지 않아도
고해상도 시계상12ms 작업 후 다음 파일을 조사하지 않는 회귀를 적용한다.
wall clock 기반3600초 시작 주기와 cutoff는 바꾸지 않는다. 단일 OS 호출의 강제 시간 제한은 아니다.

### 5.93 기존 느린 요청의 우선순위 변경 기록 대조

CTRACE의221.0337ms 요청에 대해 아직 선택하지 않은 Thread SetPriority(48)·SetBasePriority(49)
기록만 추가 추출한다. 기존XML/ETL 해시를 잠근 읽기에서 확인하고, 원시payload·QPC·CPU·opcode를
독립 해석 경로로 대조한다. 예: 문맥 전환의 양끝 우선순위가 높았다는 기존 결과와, 실제 변경
이벤트가 관측됐다는 결과를 구분한다. 대상TID는 수명 기록과 결합하며 재사용/누락 가능성을 표시한다.
최초 우선순위나 변경 원인이 없는 구간을 추정으로 채우지 않는다. 관측된 변경만으로 전체 구간의
우선순위·affinity·스케줄링 인과를 확정하거나 우선순위 설정을 바꾸지 않는다. 원본은 읽기 전용이며
제품 코드·서버·수집기·200ms 기준을 변경하지 않는다. 입력 손상/스키마 불일치/중복 키와 미완료를
검출하고, 결과·도우미 해시와 종료/정리 증거를 남긴다. 전체 릴리즈HOLD와 기존120분FAIL은 유지한다.

### 5.94 보존 정리 후보의 분리된 clean 빌드 준비

서버 연결 대기 중에도 a21e963d의 clean 소스와 고정 의존성 전체 health를 준비한다.
개발C: 여유가 약210MiB로 기존 준비 기준12GiB보다 작으므로, 기존 파일을 삭제하거나 이관하지 않고
E:의 새 실행 폴더를 임시 빌드 작업 위치로 사용한다. 바탕화면SmartFactory에는 소스SHA·실행 경로·
명령/종료/로그/환경 검증을 남긴다. E:는FAT32/이동식이므로 이 경로에서NTFS ACL 검증을 통과했다고
보고하지 않는다. NTFS가 필요한 작은 시험의TEMP는 별도C: 실행 폴더로 격리하고 여유를 확인한다.
예: Git clone/checkout 후 HEAD와전체clean을 확인하고 npm lock/pip hash lock으로 설치한 뒤
동일commit의전체health와전후clean을 확인한다. 이 결과는 새 코드의현장성능·패키지/설치/복구QA·승격과별도다.
도우미는 소유job의시간 제한/잔류 정리를 유지한다. 네트워크게시·서버실행·서명·전체백업·기존자료삭제는없다.

5.94 준비 경로 보완: FAT32 소유권 미지원으로 첫checkout이128로 중단되면 그 결과와clone완료를
보존한다. 직접 만든 해당clone의경로·이전종료·HEAD·객체연결을 확인하고, 새 준비 프로세스의
Git환경에만 정확한safe.directory를 지정한다. 전역설정·와일드카드 신뢰는 추가하지 않는다.
기존clone을 다시 복사하지 않고 작업트리가 아직없는단계에서checkout부터이어가며 새로그폴더를쓴다.

5.94 패키지 준비: 전체health가종료0/잔류0이고같은HEAD/clean임을확인한뒤에만새출력에
frontend빌드·고정venv PyInstaller·NSIS를순서대로실행한다. deploy.ps1전체실행에따른기존출력정리와
별도portable ZIP은추가하지않고,해시로고정한기존manifest함수두개만추출해동일목록계약을쓴다.
합성자료에서정상검증·덮어쓰기거부·손상검출을검사한다. npm게시옵션은never,서명은승인된미서명정책이다.
예: installer를실행하지않고내장7z를새폴더로풀어전체파일을win-unpacked와대조하고,
frontend두위치·backend manifest/provenance·asar의Git커밋·세실행파일의NotSigned/버전을확인한다.
archive경로탈출/링크/대소문자중복을거부하고추출도소유job의시간제한안에서수행한다.
E:FAT32검사결과를NTFS설치/ACL·실제앱실행·복구·현장QA의통과로확대하지않는다.

5.94 의존성 재개: R2의 frontend npm ci가900초에중단되면 실제TimeoutExpired와소유job잔류0을
확인하고새R3로그로재개한다. clone/checkout/성공한루트npm ci는반복하지않는다.
HEAD/clean과루트의설치상태를대조한뒤, lock을유지한frontend npm ci만prefer-offline으로실행한다.
이전실행이만든부분node_modules의정규절대경로·부모경계·reparse를검사하며npm의교체범위를기록한다.
예: 실제루트287패키지설치가398초였고frontend는900초에도새쓰기/다운로드가이어졌으므로
재시도의frontend기한은3600초,기타단계1800초,소유job9000초로명시한다. 시간초과도단계영수증에남긴다.
기한조정은미완료를통과로바꾸지않으며고정wheel/전체health/최종HEAD·clean조건을유지한다.

5.94 실행 검증 준비: 새 installer의 실제 추출 payload를 검증한 뒤, 그 backend 실행 파일을
합성 loopback 장비와 격리된 config/AppData에 연결한다. 기존 검증한 장비 fixture와 요청·시계
검증 경로를 해시로 고정해 재사용한다. 예: frozen/1.0.30/a21e963d identity, frontend 준비,
일반 health 한 요청과 진단 네 요청의 PID/생성 시각/요청 시계 결합을 확인한다.
루프백 밖 연결 부재와 제어 토큰을 사용한 정상 종료, 종료 코드0·listener/자식 정리를 대조한다.
각 파일·준비 결과를 검증하기 전에는 실행하지 않으며 소유job 기한 안에서만 실행한다.
이 시험은 이미지 보존 정리의 실제 규모 성능이나 Electron·NSIS 설치/복구·현장 QA를 대신하지 않는다.

5.94 의존성 감사 범위: health:dependencies의 제한된 회귀 시험과 현재 npm 감사 결과를 구분한다.
기존 R6 계획에 따라 root/frontend의 고정 lock을 package-lock-only 모드로 감사하고 전후 SHA를
대조한다. 예: JSON의 취약점 계수와 native exit0/1, 네트워크 오류를 구분해 보존한다.
기존 설치 캐시와 분리한 새 감사 캐시를 쓰며 audit fix·버전 변경·서버 작업은 수행하지 않는다.
감사 결과만으로 실제 패키지 도달 가능성·실행 QA·운영 승격을 통과 처리하지 않는다.

5.94 실행 중단 복구: 실행 핸들이 사라졌으면 worker의 PID/생성 시각과 알려진 자식,
동일 후보 경로를 사용하는 의존성 프로세스를 확인한다. 실제 부재를 확인한 경우에만 새 R4로
재개하며, terminal이 없는 이전 실행의 종료 코드를 추정하거나 정상 정리로 기록하지 않는다.
예: R3의 launcher·로그·관찰 결과를 해시로 묶고, R4에서 다시 충돌 프로세스가 없음을 검사한다.
기존 clone·루트 설치를 재검증해 재사용하고, 새 로그 폴더와 같은 제한·최종 health 조건을 유지한다.
서버 전원 종료가 사용자에게 확인된 동안은 원격 재시도를 하지 않고 독립된 로컬 검증을 진행한다.

5.94 다운로드 의존성 경로 확인: 설치된 고정 root 의존성의 Electron downloader→got→
cacheable-request→http-cache-semantics 호출과 기본 cache 옵션을 대조한다. 로컬 HTTP fixture에서
실제 downloader의 기본 옵션 두 요청과 명시적 메모리 cache를 사용한 양성 대조 두 요청을 검사한다.
CachePolicy 생성 호출만 관찰하며 원본 모듈 바이트는 바꾸지 않는다. 예: 기본 경로에서 호출0,
양성 대조에서 호출1 이상인지 확인하고, 실제 파일 내용·HTTP 요청 수·종료도 검증한다.
이는 기본 다운로드 경로의 제한된 도달성 근거이며 실제 NSIS 빌드·배포 payload·다른 옵션이나
나머지 감사 항목의 안전성을 증명하지 않는다. 기존 취약점 재현과 미해결 감사 결과는 유지한다.

5.94 실제 Electron 검사 범위: backend 전용 18029 포트 시험과 달리, 패키지 frontend의
기본 API 주소에 맞춰 전체 앱 시험은 사용 가능한 8000 포트를 선행 확인한다.
기존 measure_nsis_operational_ready.ps1의 기본 정리는 taskkill /T /F이므로 이를 정상 종료
검증으로 사용하지 않는다. 예: 실제 payload의 앱 시작 → 렌더러 준비와 같은 backend 세대 확인 →
main의 종료 경로를 통한 renderer 준비·backend closeout → 정상 exit와 잔류 부재를 확인한다.
Electron userData/sessionData와 backend AppData/config는 새 시험 폴더로 격리되었음을 실제
경로로 확인한다. 환경변수 지정만으로 격리됐다고 판단하지 않는다. app.getPath는 초기 로그에도
쓰이므로 첫 실행 전 CLI 경로 처리 근거를 확인한다. 프로필 격리·실제 앱 실행·설치/복구는 아직 미검증이다.

### 5.95 재개한 서버 투영 검사와 NTFS 후보 출처 검증

2026-10-19 사용자 승인에 따라 RETBOUND_R2 5파일만 SSH로 서버 로컬에 전달하고 파일별 SHA를 검증했다.
기존 보존 데이터는 재사용한다. 먼저 EOF 종료·결과 저장·순회 정리를 확인한 뒤 읽기 전용 투영을 수행한다.
Windows 명령 길이를 넘으면 기존 고정 스크립트의 압축 전송·복원 해시를 검증하고 cmd/PS5.1 경로를 대조한다.
예: 실제 서버에서319,971항목/7,630호출을 완료했지만 최대1,031.8582ms였다. 10ms는 협력적 예산이며
단일 OS I/O 상한·실제 캡처 스케줄·삭제 비용·과거 drop 원인 검증으로 확대하지 않는다.

FAT32에서 hardlink 종료 증거와 Git fixture가 실패하면 제품 안전장치를 약화하지 않고 NTFS 후보에서 검사한다.
같은 clean commit/고정 lock·전후 clean을 확인하고 전체 health를 실행한다. 기존 E: 실패 증거는 보존한다.
빌드에는 제품 모듈뿐 아니라 DLL의 실제 PyInstaller TOC 출처도 포함한다. 명시적 도구 PATH와 비운 PYTHONPATH를
사용하며 후보·고정Python·Windows 밖의 출처를 거부한다. 첫 빌드의 외부DLL43개는 실행 없이 별도 보존했다.
NSIS의 PowerShell 경로 누락처럼 패키징만 실패하면 전 단계 소스/의존성/출처/manifest 불변을 검증해 재사용한다.
예: 최종 설치본 d0e28e3e의 추출1,864파일을 대조하고 합성 backend5요청·정상 종료 후 바이트 불변을 재확인했다.
이 결과는 전체 Electron·설치/복구·현장15분/120분 통과를 대신하지 않는다. 서버 설치·설정·전체 백업 변경은 없다.
[실제 결과와 후속 조건](C:/Users/user/Desktop/SmartFactory/RESUME_20261019_b3ea61d4/review.md).

### 5.96 감사 의존성과 실제 JavaScript payload의 결합

lock의 dev 표시만으로 배포 앱의 미포함을 판단하지 않는다. 같은 installer SHA에 결합된 실제 ASAR를
읽고, frontend는 원 config/소스/고정 의존성에 관찰 plugin만 추가해 별도 출력에 빌드한다.
주 화면과 Vite의 별도 Worker 빌드에 각각 모듈 그래프를 수집한다. `generateBundle`의 post 순서에서
최종 코드를 기록하고 모든 emitted JS의 그래프·SHA 일치와 원 payload 전체 파일 일치를 요구한다.
예: d0e28e3e의 ASAR16파일, 주 화면4,577/Worker64모듈, JS34개/전체50파일을 결합했다.
표시 경로와 Windows ASAR 파서 경로를 구분하고, 누락 Worker나 후속 hook 변경 전 해시를 통과로 처리하지 않는다.
이 절차는 앱 JavaScript의 포함 여부 검증이며 빌드 도구 실행 경로·모든 외부 입력·Electron 자체 보안 또는
설치/복구/현장 QA를 대신하지 않는다. 독립 경로 분석·바이트 검산과 실패 이력을 보존한다.
[검증·현재 권고·남은 조건](C:/Users/user/Desktop/SmartFactory/PKGDEP_20261019_c72e8a16/review.md).

### 5.97 실제 Electron 실행과 정상 종료의 결합

변경 없는 최종 NSIS payload를 새 user-data-dir/AppData와 가상 TCP/HTTP 장비에 연결한다.
실제 native 창의 버전·작업 값·내용을 관찰하고 창 닫기로 renderer drain/인증된 backend 종료를 거친다.
프로세스 내부 final만으로 종료를 판정하지 않고 외부 소유 감독자의exit/job/포트와 대조한다.
예: a21e963d/d0e28e3e의 main/backend exit0, forced=false, job0, backend 종료550.6ms를 확인했다.
기존 프로필 전후 metadata 대조와 실제 열린 파일 경로를 기록하되 전체 바이트 보존 증명으로 확대하지 않는다.
NetLog의 사전 다운로드와 장비 연결을 구분하고, 화면 겹침/통신 경고를 정상 종료 성공으로 덮지 않는다.
기본 layout 수정은 별도 Act이며 저장된 운영자 layout을 임의 초기화하지 않는다.
[구체적 실행 및 한계](C:/Users/user/Desktop/SmartFactory/EL30_20261019_6c17a0e3_R2/review.md).

### 5.98 기본 카드 경계와 화면 전환 상태

새 기본 배치의 SPOT에12행, 보조/환경8행, 몰드12행, 작업 정보16행을 배정하고 차트는36행부터16행을 사용한다.
Native/Scenes의 panel-content는 최소 높이0과 CSS 스크롤 경계를 공유한다. 필수값 경고의overflow 예외는 유지한다.
명시적으로 저장된 배치에는 새 기본 좌표를 덮어쓰지 않는다. 최소 공간·충돌 없음·저장 좌표 왕복을 검사한다.
실제 일반/최대화 창과 편집 모드의 판독 가능성은 별도로 확인하며 작은 창은 페이지 스크롤을 허용한다.
예:3e96342b의 변경 frontend+기존a21백엔드 시험본에서 일반1266×793/최대화1920×1032를 확인했다.
이 혼합본은 출시 candidate가 아니다. OS 전체 격리가 아닌 별도 프로필/모의 장비 실행 범위를 기록한다.
제품 변경 경고의 컴포넌트 로컬 상태가 모드 전환에 소실되는 현상은 후속 재현·수정 대상으로 남긴다.
[시험 경로와 후속 조건](C:/Users/user/Desktop/SmartFactory/LAYOUT_20261019_d485f920/review.md).

### 5.99 화면 재마운트와 작업 정보 편집 상태의 수명

작업 정보의 초안·변경 경고·오류·진행 중 저장 상태는 Native/Scenes 분기 상위 Provider가 소유한다.
위젯만 재마운트될 때 최초 GET으로 입력과 경고를 초기화하지 않는다. 상태 수명은 현재 대시보드이며
디스크 저장이나 적용된 서버 값으로 간주하지 않는다. 기존 검증·저장·리셋 및 주기적 조회 동작을 유지한다.
예: 제품 변경 표시→편집 모드에서도 경고 유지, 입력99002→일반 모드 복귀에도 미저장 유지,
적용 없이 종료→시험 저장값99001·1 및 빈 이력 유지. 저장 중 전환 뒤 실패도 화면에 남아야 한다.
회귀 검사와 실제 두 화면 왕복을 구분해 기록한다. 최종 설치본의 실행·설치·복구 검증은 별도다.
[설계 적용·검증 범위](C:/Users/user/Desktop/SmartFactory/EDITSTATE_20261019_c07dba0f/review.md).


### 5.100 同버전 최종 후보의 현장 도우미와 승인 중복 정리

1.0.30의0732c8e8과685dde94를 commit·installer SHA·payload SHA로 구분한다. 최종 후보는 별도
설치 request/schema와 정상 종료v4·선택 사본v2 계약을 사용하며 기존 요청의 허용 범위를 묵시적으로 넓히지 않는다.
정상 종료·native 세대·원본 전수 재검산·Low Signal OFF·12.25GiB 공간 reserve를 유지한다.
예: 같은1.0.30의 과거 build가 들어오면 검증 전에 거부하고, 정확한 최종 payload1866파일만 허용한다.
도우미만 별도 커밋으로 만들고 실제 추출 소스207검사와 frozen 실행6건으로 결합한다. 제품을 재빌드하지 않는다.
서버 중복 정리는 사용자 승인9개와 일치하는 경로만 검산 후 LiteralPath 삭제한다. 보존 사본의 읽기 잠금을
삭제 종료까지 유지하고 삭제 후에도 해시를 대조한다. 운영 데이터·기존 백업·설치/롤백은 대상이 아니다.
확보 용량은 실제 free 전후와 삭제 바이트를 구분하고 새 전송/관찰 결과/운영 증가를 포함해 설치 전에 다시 확인한다.
[구체적 계약·실행·남은 조건](C:/Users/user/Desktop/SmartFactory/F30FIELD_20261019_4ae6b901/review.md).

### 5.101 렌더러 프로세스 소실 후 정상 종료 경로

2026-10-19 서버의 화면 프로세스 부재와 종료 준비 15초 timeout을 확인했다. 같은 Electron44.3.0의
격리 시험에서 renderer가 사라져도 BrowserWindow와 webContents는 파괴되지 않아 기존 destroyed 검사만으로
분기하지 못하는 것을 재현했다. 프로세스 소실 전·준비 중·전송 직전 세 조건을 별도로 검사한다.
isCrashed 또는 현재 webContents의 render-process-gone 확인 시 응답 불가능한 renderer의 준비 대기만 종료한다.
백엔드의 인증 종료·이미지/CSV drain·정상 exit 및 closeout 검증은 그대로 거치며, nonzero/강제 종료는 실패다.
살아 있는 무응답 renderer는 기존 timeout을 유지하고, 새 renderer에는 새 attemptId 확인을 요구한다.
실패 후 resume은 crashed renderer에 성공을 반환하지 않는다. 프로세스 소실의 reason/exitCode는 main 로그에 남긴다.
예: renderer crash → renderer 준비 종료 → backend closeout 실패이면 앱 종료 불허; 검증된 exit0 뒤에만 종료 허용.
이 변경은 renderer가 사라진 원인의 해결이나 현장 설치 성공을 의미하지 않는다. 서버에는 설치 전까지 적용되지 않는다.

### 5.102 현재 1.0.30의 사본 없는 설치 전 원본 관찰

preservation 도우미는 별도 정책 `OMITTED_FOR_1030_RENDERER_LOSS_FIX`와 현재 앱1.0.30,
직전 build `0732c8e810be3c46096b397812f53a9767354229`가 모두 일치할 때만 새 관찰을 허용한다.
이 도우미는 기존 원본을 읽고 정상 종료 뒤 검산할 뿐 설치본을 선택하거나 설치를 실행하지 않는다.
대상 설치본의 commit·SHA·payload 결합은 별도 설치 계약에서 확인하며 기존685 후보 계약을 재사용하지 않는다.
예: 같은1.0.30이어도685/8de 또는 다른 build이면 현재 원본 관찰 계약에서 거부한다.
이전 두 정책의 허용·거부 조건,14.25GiB reserve, 경로·세대·정상 종료 대기·패키지 잠금은 유지한다.
로컬 음성 대조와 패키지 전체 로드 검증 후에만 전달을 준비한다. 서버 실행·공간 확보·설치 성공은 별도다.

### 5.103 실제 설치본의 renderer 소실과 backend 정상 종료 통합 검증

네트워크를 끈 새 Windows Sandbox에서 같은8de/f1b6 설치본의 설치·업그레이드·재시작·복구를 확인한다.
후보 재시작 실행에서만 소유main의 직접 자식이고 같은 설치 경로인 단일renderer를 PID·생성시각으로 확인한 뒤
의도적 장애를 주입한다. main/backend는 종료하지 않는다. 이후 지원되는 화면 도구의 창 닫기를 수행한다.
예: 정상 CSV/이미지 수집→renderer 소실→같은backend 응답→창 닫기→main/backend native exit0→
종료 receipt·CSV/fact/image drain·원본 보존·잔류 프로세스/포트0을 대조한다.
의도적 renderer 종료와 실패 정리를 구분하며, 실제 서버와 개발 PC 운영 프로필에는 장애를 주입하지 않는다.
새 설치본의 결과만 판정하고 기존 실패·롤백 오류를 보존한다. Sandbox 성공은 현장 QA 통과를 대신하지 않는다.

### 5.104 renderer 종료 수정 설치본에 결합한 현장 도우미

8de/f1b6의 실제 payload1866파일과 Sandbox 설치 관찰에서 얻은 제거 파일 해시를 새 기준으로 고정한다.
기존0732/685 계약은 보존하고 새 후보를 별도 identity로 추가한다. 같은1.0.30이어도 commit·installer·reference가
섞이면 실행 전에 거부한다. 설치는0732→8de 전환과 `OMITTED_FOR_1030_RENDERER_LOSS_FIX`만 허용한다.
정상 종료 request-v5·선택 사본 request-v3는8de에만 결합하며 기존 schema의 허용 범위를 넓히지 않는다.
예: 새 설치 요청에685 기준 또는 이전 종료 schema를 넣으면 원본 읽기/설치 전에 거부해야 한다.
기존 정상 종료·Low Signal OFF·원본 검산·공간 reserve·직전본/등록 롤백 구분은 유지한다.
d064의 제품/관찰 변경과45fb의 이전 현장 도우미를 출처별로 결합한 별도 helper commit을 만들고,
정확한 커밋에서 계약·수집·종료/설치·패키지 검사를 실행한다. 기존 작업 트리와 검증 설치본은 변경하지 않는다.
이 준비는 서버 전달·설치·운영 승격을 의미하지 않으며, 현장 공간과 정상 종료 조건은 실행 시 다시 확인한다.

### 5.105 사용자 승인 범위의 서버 SmartFactory 중복 정리

2026-10-19 사용자가 서버 `C:\Users\user\Desktop\SmartFactory`의 불필요한 파일 삭제를 추가로 승인했다.
이 명시 범위에서 정확한 대상·보존 위치·파일별 SHA256을 기록한 뒤, 보존본과 같은 바이트인 중복본을 정리한다.
전체 백업을 새로 만들지 않으며 현재 운영 AppData/설치 경로, 기존 전체 백업, 유일한 결과·설정은 보존한다.
예: 여러 폴더의 같은 설치본은 대표본을 서버와 개발 PC에 유지하고 중복 파일만 삭제한다.
완료된 시험용 앱·회수된 진단 파일은 개발 PC의 정확한 사본을 읽기 잠금으로 보존한 동안에만 서버 사본을 삭제한다.
호스트·계정·접속 주소, 절대경로 경계, reparse, 추가 스트림, 실행 프로세스·서비스·예약 작업·바로가기를 확인한다.
추가 스트림은 Zone.Identifier만 내용·해시를 별도 기록할 수 있으며 다른 스트림은 삭제를 중단한다.
과거 helper/manifest를 고쳐 쓰지 않고 삭제 전 경로와 보존 경로의 대응표를 남긴다. 옛 절차 재실행에는
같은 바이트를 원래 경로에 복원하는 준비가 필요함을 기록한다. 삭제 수·바이트·남은 설치본과 여유 공간을 재검증한다.

### 5.106 내부 CSV·이미지 검사 프로세스 묶음의 종료 확인

외부 PowerShell 실행 도우미의 기존 종료 계약과 동일하게, 내부 Python command worker 종료와 소유 job 전체 종료를 구분한다.
worker exit0 뒤 최초 job accounting을 보존하고, 최대2초이면서 원래 전체 timeout 안에서 active_processes=0을 확인한다.
확인 중에도 출력 크기 상한을 검사하며, 0이 관찰되지 않거나 전체 시간 제한에 도달하면 실패·소유 job 정리를 유지한다.
새 대기 때문에 timeout을 다시 시작하지 않고, 실제 consumer exit·출력 검산·강제 종료/오류 시 FAIL 규칙을 바꾸지 않는다.
예: 짧은 자식 종료가 worker보다 늦으면 정해진 범위에서 종료를 확인한다. 계속 살아 있는 자식은 실패하고 무관한 프로세스는 유지한다.
실제 Windows 자식으로 짧은 종료 간격, 잔류 자식, 전체 제한 초과, 종료 확인 중 출력 상한 초과를 검증한다.
변경은 별도 helper commit에만 적용한다. 검증된 제품8de/f1b6 설치본은 재빌드하지 않으며 현장 실행·출시 승격은 별도 조건이다.
실제 잔류 자식 종료 시험에서 로그 쓰기 핸들 해제의 짧은 지연도 관찰했다. job 정리 뒤 로그·terminal의
읽기 공유 잠금은 Win32 공유/잠금 충돌32/33만 전체2초 안에서 재시도한다. 접근 거부·다른 오류는 즉시 실패하며
재시도 횟수·경과 시간·읽기 잠금 성공 여부를 기록한다. 실패에도 process receipt를 남기고 결과를 PASS로 바꾸지 않는다.

### 5.107 기존 서버 버전의 화면 다시 읽기와 정상 종료 재시도 경로

현재0732의 renderer 소실 후 종료 준비 실패를 해소할 수 있는지, 별도 개발 프로필의 실제 Electron에서 확인한다.
정확한 기존 lifecycle 소스를 사용하고 소유 시험 renderer만 소실시킨다. 기본15초 종료 실패·backend 호출0을 확인한 뒤
같은 webContents의 지원되는 reload API로 새 renderer를 생성하고 실제 preload IPC 준비 응답을 받는다.
예: 첫 종료 실패 → 같은창 reload → 새 renderer PID/준비응답 → 두 번째 종료 준비 성공.
운영 서버에는 장애를 주입하지 않고 제품 소스·설치본을 변경하지 않는다. 대체 backend 함수로 시험한다면
그 한계를 기록하며 서버의 실제 UI 입력·백엔드 drain·원본 검산은 별도 실행 조건으로 유지한다.

### 5.108 화면 소실 사고의 제한된 복구 가능성 시험

0732 서버의 Alt 메뉴·Ctrl+R 실패와 화면 도구 URL 확인 실패로 정상 UI 경로가 막혔다.
기존 인증 제어 API를 통한 수집 정상 종료 후, 남은 Electron main만 정리할 수 있는지
네트워크가 차단된 Windows Sandbox에서 정확한 0732 설치본으로 시험한다.
PID·생성시각·실행 경로·설치 바이트·loopback listener·backend generation을 확인한다.
제어 토큰은 선택한 backend 환경에서 메모리로만 사용하며 출력·로그·결과에 남기지 않는다.
소유 시험 renderer에만 장애를 주입하고, 실제 backend의 인증 종료 요청·native exit0·
CSV 종료 metadata·fact/image manifest·세대별 종료 receipt를 확인한 뒤에만 main 정리를 허용한다.
실패나 시간 초과이면 backend 또는 main을 강제 종료해 통과시키지 않는다.
시험에서 main 정리는 강제 종료로 명시하며 제품의 정상 종료 QA 통과로 계산하지 않는다.
예: renderer 소실 → 인증된 수집 종료 → 저장/세대/exit0 검산 → 남은 main 정리 → cold 상태 확인.
운영 서버 실행은 이 격리 시험과 별개다. 계획의 운영 강제 종료 금지에 대한 사용자 승인을
받기 전에는 서버 main 정리·백엔드 종료 요청을 수행하지 않는다. 기존 원본 관찰·설치 전후
검산과 새 후보의 정상 종료·현장 15분/120분 조건은 유지한다.


### 5.109 승인된 사고 복구의 현장 실행 계약

5.108의 한정 복구를 사용자가 승인했다. 최신 helper 0b80에서 별도 소스로 준비하며 제품 8de는 재빌드하지 않는다.
새 요청·승인 원문·실행 파일을 외부 SHA256으로 결합하고 서버/계정/관리자·PID/생성시각·payload·renderer 부재를
다시 확인한다. backend와 main의 native handle을 보유하며 제어 토큰은 선택한 backend 환경에서 메모리로만 사용한다.
backend 인증 정상 종료 후 exit0, 같은 세대의 종료 receipt와 현재 CSV 종료 metadata, fact/image 해시 및 drain을
검산해야 main만 정리할 수 있다. 실패/연결 중단에는 backend나 다른 프로세스를 강제 종료하지 않는다.
정리 전 durable intent와 정리 후 receipt를 보존하고 실제 강제 main exit와 정상 backend exit를 구분한다.
설치 도우미는 기존 정상 종료 분기와 별도로 이번 승인 해시·정확한 두 build·동일 관찰 세대·복구 receipt를
검증하는 분기만 추가한다. `normal_shutdown_observed=false`를 그대로 유지하며 실패 항목이 있으면 거부한다.
예: 승인 없음/다른 PID·세대/다른 build/backend 비정상 종료/저장 미완료이면 main 정리와 설치 모두 차단한다.
실제 Windows Sandbox에 같은 복구 코드를 적용하고 음성 조건·기존 설치 계약 회귀 검사를 수행한 뒤 전달한다.
현장 실행에는 기존 원본 관찰과 설치 전후 전체 검산, Low Signal OFF, 공간 reserve와 현장 QA 조건을 유지한다.


### 5.110 종료 직후 PID 검사 중단의 한정 이어가기

현장 IR16bf5f01은 인증된 종료 후 retained handle의 exit0 및 포트 부재를 확인한 직후
`backend-pid-remains-or-reused`에서 중단됐다. main 정리는 실행되지 않았고 후속 읽기에서 backend/port 부재를 확인했다.
이미 정상 종료된 backend에 종료 요청을 다시 보내지 않는다. 원래 실행 파일·요청·preflight·정상 종료 intent·hold를
외부 해시로 고정하고, 해당 유일한 오류 지점에 도달하기 전 native exit0 검사가 필수라는 코드 경로 근거를
명시적으로 검증한다. 전용 exit 영수증이 없으므로 이를 새 native handle 측정으로 표시하지 않는다.
같은 세대의 final/begin receipt와 CSV/fact/image 저장 증거를 재검산한 뒤 현재 정확한 main handle만 정리한다.
기존 정상 종료·복구 영수증을 수정하지 않고 재개 증거의 종류와 실패한 선행 실행을 새 영수증에 연결한다.
설치 게이트에는 이 고정된 사고 증거만 허용하는 분기를 추가하며 일반적 누락 증거나 다른 오류는 거부한다.
예: 원래 hold 해시·오류코드 불일치, backend 재등장, 다른 main 세대, 저장 증거 불일치이면 정리/설치를 중단한다.
이전 원본 관찰의 대기 제한이 끝나면 해당 HOLD를 보존하고, 새 cold 관찰에서 기존 전체 stream/metadata 검산을 수행한다.

### 5.111 검산 후 일반 사용자 재시작과 새 build 설정 결합

전체 원본 관찰·설치 전후 검산을 마친 동일 8de 설치본만 재시작한다. 설치 영수증의
`installer_exit`는 숫자가 아니라 native 종료 증거 객체이므로 `actual_exit_code=0`,
`identity.handle_retained=true`, `forced_termination=false`를 형식까지 확인한다.
설치·원본 보존 성공 및 앱 미시작 상태를 확인한 뒤 로그인 운영자 세션의 InteractiveToken/LUA로
앱을 한 번 시작한다. 임시 예약 작업은 트리거 없음·정상 우선순위·실행 시간 제한 없음·강제 종료 금지이며,
시작 후 작업 정의만 삭제한다. 예: 설치 실패/보존 실패/다른 build/이미 시작된 기록이면 재시작을 거부한다.
실제 프로세스 권한·세션·실행 build·health·운영 화면은 시작 요청 성공과 별도로 확인한다.

8de의 실제 metadata를 얻고 정상 종료한 후에만 기존 USER_SELF 승인 프로파일을 새 지문에 연결한다.
외부 설정 승인 도우미의 허용 build 목록에 정확한 8de만 추가하며 제품 설치본은 재빌드하지 않는다.
승인 해시·입력 해시·Low Signal OFF·comparator 미검증·프로파일·readback·drift 조건을 그대로 적용한다.
네 승인 필드 외 설정을 보존하고, 기존 도우미의 작은 설정 쓰기 복구 사본만 사용한다.
합성 시험 metadata는 도우미 검사 용도이며 서버 승인 증거로 사용할 수 없다.

실행 정보 회수 도우미의 v1~v5 요청과 로컬 검토기의 지원 범위를 일치시킨다.
요청 revision별 허용 build/version을 고정하고, v2 이후의 시작 sequence는 양의 정수로 검증한다.
동일 표시 버전의 다른 commit·잘못된 native 세대·파일 해시·listener 소유자는 계속 거부한다.
예: v5/8de 요청에 실제 health가0732라고 기록되면 동일1.0.30이어도 검토에 실패한다.
회수된 실행 정보 검증은 현재 생존 확인·설정 attestation·정상 종료·현장 QA의 PASS를 대신하지 않는다.


### 5.112 취소 구간의 실패 보고와 프로세스 저장 시각 구분

900초요청이도중취소되면각수집기의cancelled_remaining 한건이남은구간을표현한다.
통합검토는정수sequence/remaining_slots/예약시각을검증하고해당잔여구간을FAIL사유로남긴다.
존재하지않아야할후속파일을읽지않으며취소를성공요청이나검사표본으로세지않는다.
표식없는파일누락·manifest손상은계속거부한다.완료된실제요청수와처음/최대지연판정은유지한다.
프로세스표본에는현재판단시각과직전표본종료/동기저장시작·종료시각을기록한다.
이는저장지연과검사시각누락을구분하기위한증거이며검사간격이나실패기준을변경하지않는다.
현장원인이미확정인상태에서디스크·스케줄링원인을단정하지않는다.
도우미3a7609b7의117검사와실제실패바이트재분석,패키지6실행을확인했다.
제품8de변경없이새도우미를사용한R2의결과는별도검증한다.

### 5.113 CSV 시작과 이미지 기록 초기화의 실행 책임 분리

운영 CSV의 시작 sidecar는 이미지 fact의 과거 행 수·해시 스캔을 직접 실행하거나
writer/file lock을 기다리지 않는다. 아직 준비되지 않은 상태는
`image-persistence-pending-at-open`, finalized=false, writes_drained=false로 남긴다.
실제 저장 경로 불일치·초기화 실패·잘못된 해시 상태는 이 대기 상태로 숨기지 않는다.

cold 시작 및 설정 변경으로 이미지 writer가 필요하면 기존 이미지 저장 worker에 초기화
요청을 전달한다. 이미지 저장 OFF에서도 미리 초기화하므로 비용을 종료 시점으로 미루지 않는다.
요청은 처리 시작 때 소비하여 초기화 도중 새 설정에 대한 요청이 들어오면 다음 순회에서 처리한다.
별도 소유자 없는 thread를 만들지 않고 기존 worker의 종료 대기·남은 작업 확인을 사용한다.
예: 초기화가 멈춰 있으면 CSV 준비는 진행하지만 종료 성공을 보고하지 않는다. 초기화 완료 후에만
worker 종료와 최종 manifest 검증을 진행한다. 종료가 시작된 후 새 초기화 요청은 받지 않는다.

초기화는 이미지 캡처가 아니므로 enqueued/written/failure 합계에 가짜 이미지 건수를 더하지 않는다.
초기화 오류는 별도 실패 상태로 보존하고 clean closeout을 거부한다. 최종 manifest의 경로·해시·행 수
검증 및 기존 캡처 손실/미완료 판정을 유지한다. 시작 sidecar의 pending 상태를 최종 PASS로 바꾸지
않으며 기존 계약대로 별도 최종 manifest를 검증한다.

검증 예시는 초기화·파일 lock 경합, 경로 fallback, 준비된 해시, 초기화 실패, 저장 OFF 종료,
초기화 도중 설정 변경, 종료 후 요청 거부다. 코드 단위 검사와 실제 규모 시작 시간·패키지·현장
검증을 구분하며, 이 변경만으로 8de 현장의 약83.4초 전부를 설명하거나 개선됐다고 판정하지 않는다.

### 5.114 설치형 화면 관찰의 출처와 연결 수명

설치형240a는 `file://.../index.html#/dashboard`를 열고 기본 API는
`http://127.0.0.1:8000`으로 요청한다. 관찰기가 문서와 이미지의 origin 일치를 요구하면
실제 요청을 모두 제외할 수 있다. 따라서 file 문서는 명시한 loopback HTTP origin 하나만
허용하고 main frame의 정확한 이미지 경로만 기록한다. HTTP 문서의 기존 same-origin 제한은 유지한다.
예: file 문서에는 `--image-origin http://127.0.0.1:8000`이 필요하며,
LAN 주소·인증정보·경로·query·fragment·다른 포트의 응답을 같은 증거로 받아들이지 않는다.
설정을 읽었다는 이유만으로 새 이미지 요청을 만들거나 focus/표시 상태를 강제로 바꾸지 않는다.

이 변경은 관찰 도구 revision3에만 적용한다. 제품 설정·수집 주기·설치본은 변경하지 않는다.
브라우저 fixture의 성공은 실제 운영 화면이나 물리적 표시 연속성의 PASS가 아니다.
현재 설치본과 같은1867파일을 전후 검산한 격리 실행에서 실제 file 문서의 요청·load와
관찰기 정리·앱의 정상 종료를 확인하고, 연결 단절이 앱에 미치는 영향도 별도로 시험한다.

익명 파이프의 연결 종료가 실제240a 앱 종료를 유발한 시험 결과에 따라, 해당 파이프를
운영 수집 중인 앱의 관찰 연결로 사용하지 않는다. TCP loopback 방식은 수집기를 분리해도
같은 앱/로거가 유지되는 격리 증거를 확보했지만 현장 적용 준비 완료를 뜻하지 않는다.
현장 연결은 승인 범위, 정확한 설치본·프로세스/생성시각·사용자 세션·listener 소유자,
관찰 전후 세대 결합, 단절 시 관찰기 정리, 예정된 정상 종료 후 포트 제거를 검증해야 한다.
앱을 진단 Job에 넣어 수집기 장애 때 함께 강제 종료하는 방식은 허용하지 않는다.

### 5.115 현장 이미지 진단 연결의 승인과 회수

실제 화면 계측의 진단 인수는 이번 실행에만
`--remote-debugging-address=127.0.0.1 --remote-debugging-port=19221`로 제한한다.
진단/일반 실행 바로가기를 새 검증 폴더에 구분해 준비하고 기존 운영 바로가기는 수정하지 않는다.
파일 전달 승인은 진단 인터페이스 활성화 승인을 대신하지 않는다. 이 인터페이스는 서버 내부
프로그램에도 화면 제어 접근을 제공하므로 그 범위와 수명을 확인한 뒤 실행한다.

실행 순서 예: 현재 세대 재확인 → 종료 관찰 준비 → 정상 UI 종료와 저장 검산 →
같은 설치본 일반 사용자 진단 실행 → 실제 token/session/생성시각·logger/CSV/설정·listener
소유자와 loopback 주소 확인 → 기존 SSH를 통한15분 실제 화면 관찰 → 정상 종료·저장 검산 →
진단 listener 소멸 확인 → 진단 인수가 없는 일반 실행·수집 확인·작업 화면 전면 표시.
기존 SSH의 포트 전달 금지 조건을 유지한다. 실제 관찰기는 서버 내부에서 해당 loopback에
연결하고, 기존 SSH는 진단 실행·결과 회수에 사용한다. 진단 프로세스만 소유 Job으로 제한하며
관찰 전후 제품 native handle/생성시각·현재 logger/CSV·설정·listener 소유자를 대조한다.
진단의 측정 시간과 포트의 수명은 다르다. 포트는 앱 종료 시 사라지므로, 수집기나 SSH의
단절만으로 서버 포트가 닫혔다고 보고하지 않는다. 앱 강제 종료를 자동 정리 수단으로 쓰지 않는다.

### 5.116 이미지 관찰 종료 경계의 제한된 후속 확인

revision4 관찰기는 기본 관찰 구간이 끝나면 새 HTTP 요청을 집계 대상에 추가하지 않는다.
그 시점에 진행 중인 요청 ID만 최대2초 후속 관찰하고, 이후 새 요청 수는 별도로 기록한다.
2초는 도구가 종료를 기다리는 상한이며 운영 응답 시간·화면 갱신 합격 기준이 아니다.
deadline 뒤에 관찰된 응답은 완료 증거로 넣지 않으며, timer callback 지연이 있으면
실제 경과 시간이2초를 넘을 수 있으므로 이를 실시간 보장으로 표현하지 않는다.

DOM 기본 구간은 후속 대기를 시작하기 전에 seal하고 당시 이벤트 사본을 남긴다.
기본 load 간격·시작/끝 공백·가시성 표본은 이 구간에 한정한다. 후속 DOM 이벤트와
늦게 완료된 Resource Timing은 별도 기록하며 기본 구간의 load 수에 합치지 않는다.
서로 다른 host/page 시계의 cutoff를 동일 시각으로 추정하지 않고 각각 기록한다.
요청 수·resource 수·시계·경계 ID가 맞지 않으면 INCOMPLETE를 유지한다.

예: 기본 구간에3요청/2load가 있고 마지막 응답이0.5초 뒤 완료되면,
HTTP 완료3건·기본 load2건·후속 완료1건을 기록한다. 기본 load3건으로 바꾸지 않는다.
후속 응답 실패는 요청 FAIL이며,2초 안에 끝나지 않은 요청은 INCOMPLETE다.
후속 DOM 이벤트는 해당 HTTP ID에 연결된 증거가 아니므로 물리 표시·이미지 손실 판정에 쓰지 않는다.

요청 완료를 기다리는 동안에도 제품 요청을 취소하거나 창을 닫지 않는다.
관찰 중 페이지가 닫히면 기본 구간 사본을 보존하고 계측 미완료·자체 listener 정리를 기록한다.
revision3 이하의 원본 요약 계약은 그대로 재현하며 기존 현장 INCOMPLETE를 재작성하지 않는다.
현장 재사용 전 현재 설치형 Electron과의 연결 수명·결과 포맷·소유 Job 정리는 별도로 확인한다.

### 5.117 동일 후보의 격리 초기 시작 측정

R2의 초기 시작10회는 동일240a/56ec 설치본을 외부 통신 차단 Sandbox에 한 번 설치하고,
각 회차 새 AppData·빈 합성 데이터·동일 loopback 장비 fixture로 측정한다. OS 캐시는
초기화하지 않고 실행 순서·조건을 보존하므로 OS cold-cache 시험으로 표현하지 않는다.
후보 commit의 기존 measure_nsis_operational_ready.ps1·backend 무결성 모듈을 그대로
사용해 앱 내부 및 launcher 시각의30000ms 계약,9milestone·9progress·raf 준비를 확인한다.
예: 도구 exit0이라도 performance_status=FAIL이면 회차/전체 결과는FAIL이다.

기존 도구의 taskkill 정리는 격리된 합성 데이터 앱에만 적용한다. 이 시험을 정상 종료·
CSV/이미지 저장 완전성 검사로 세지 않는다. 기존 운영 정상 종료 증거와 별도다.
호스트는 기존CSV 소비기의 실제 종료·완료 검산·잔류0을 확인한 뒤에만 새 성능 시험을 시작한다.
이미 실행 중인Sandbox 또는 재사용 출력은 거부한다. 입력은 읽기 전용이고 새 출력만 쓰기 가능하다.
고정 installer·799입력·설치payload 전후·같은 회차 raw출력/시작session·정리 결과를 대조한다.
완료/실패 시 자신이 생성한Sandbox ID만 정리하고 실제 소멸을 확인한다.
초기 시작 결과는 실제 서버3회·다중 화면·물리 표시·장비 경계·학습 적합성을 대신하지 않는다.

### 5.118 현재 후보의 동일 브라우저 탭 비교 관찰

기존2026-10-13 탭 비교는 backend54파일 중6개가 현재240a와 개행을 제외하고도 달라
현재 후보의 완료 근거로 재사용하지 않는다. 기존 결과·404·실패 시도는 보존한다.
새 비교는 외부 통신 차단 Sandbox의 정확한 후보 payload·동일 초기 대량 fact·합성 장비를
사용한다. 별도 Chromium에서1개/3개 탭을 순차 비교하며 Electron 화면 성능으로 확대하지 않는다.
120초 warmup·300초 관찰,5초 자원·2초 health의 기존 수집 계약을 유지한다.

브라우저는 native launch와CDP noDefaults로 연결하며 한 창에서 마지막 탭만visible인 실제
상태를 확인한다. 최소화·예상 밖 페이지 재시작은 불완전한 측정으로 남긴다.
요청별 시작ID/완료·실패/미완료와 이미지load/error/크기/URL/시각을 분리해 기록한다.
예: browser 요청 시작3건·완료2건이면 남은1건의ID를 보존하며 이미지1장 손실로 세지 않는다.
LCP/CLS와 각탭 visibility/viewport·시작/종료 화면·정상 브라우저 종료도 보존한다.
원시 관찰 종료0은 실제표시 연속성·저장·전체운영PASS와 다르며200/500ms는 비교값이다.
게스트/호스트 실행기·입력 SHA·후속 저장 검산이 모두 준비되고 CSV와START10이 끝난 후에만
새 성능 비교를 시작한다. 첫 smoke는 모의 페이지에서 실제창/탭/이벤트 흐름을 확인한다.

### 5.119 탭 비교의 실행 및 독립 결과 검토

TAB20은 설치된 frozen backend와 별도 Chromium을 사용한다. 각 조건마다 새 합성
AppData와 동일한 2,350,216,905바이트 image fact를 사용하며 원본은 읽기 전용이다.
전후 prefix SHA를 대조하고 새 이미지·CSV·종료 기록과 추가 fact 행만 회수한다.
전체 원본의 새 백업을 만들거나 운영 설정을 적용하는 작업은 아니다.

게스트는 사용자·VM·외부 통신 차단·고정 경로를 확인한 뒤 묶음 입력을 재검산한다.
호스트는 CSV의 실제 종료·잔류0·완료 검산과 START10 완료를 확인한 뒤 자신의 새
Sandbox ID만 실행한다. 제한시간이나 수집 오류는 완료로 간주하지 않으며 자신의
Sandbox만 폐기하고 종료 결과를 기록한다. 원본 파일을 변경하거나 다른 VM을 닫지 않는다.

독립 검토는 85개 자원 표본·예정 health 시각·31개 브라우저 상태·요청 ID 대응·응답
본문 SHA·동일 실행 ID를 확인한다. 이미지 load 간격과 종료 경계 오류는 분리한다.
예: 종료 직후 취소된 요청은 종료 경계 오류로 보존하고 관찰 중 이미지 손실로 바꾸지 않는다.
새 JPEG는 fact의 경로·크기·SHA·decode와 정상 종료 worker 수를 대조한다.
CSV는 원문을 보존하며 이 검토만으로 전체 CSV 내용 검증을 완료했다고 판정하지 않는다.
RSS 합계에는 공유 페이지가 중복되고 CPU 차이는 양쪽 경계에 존재하는 프로세스에
한정되는 한계도 결과에 포함한다. 수치 비교가 운영 SLO·물리 표시·학습 적합성을 대신하지 않는다.

### 5.120 탭 비교 요약의 첫 요청과 계측 불가 보존

탭 비교 HTTP 요약은 준비·첫 요청·마지막 경계를 포함한 전체와 본 관찰 구간을 나눈다.
각각 첫값·마지막값·최대·중앙값·nearest-rank p50/p95/p99, 오류·timeout,
내부 비교값 초과 수·연속 초과 표본을 남긴다. 첫 요청 실패를 요약에서 제외하지 않는다.
예: 900/201/10/230/30ms에서 200ms 초과는3회, 최장 연속 초과는2회다.
이는 연속 장애 지속 시간을 뜻하지 않으며 200ms를 새 합격 기준으로 쓰지 않는다.

동일 자원 표본에 guest 가상 디스크의 읽기/쓰기 누적 카운터를 추가한다.
계측 불가·디스크 집합 변경·카운터 역전이 있으면 INCOMPLETE로 남긴다.
61개 본 관찰 표본의 차이를 보존하지만 호스트 실제 디스크의 작업별 지연이나
전체 운영 성능 PASS로 해석하지 않는다. 이미 완료된120분 서버 검사의 원문은 변경하지 않는다.

### 5.121 초기 시작 계측의 실제 로그·프로필과 Sandbox 수명

Windows Sandbox 시작 응답과 ExistingLogin 준비 완료는 구분한다. 자신이 만든
Sandbox의 연결 창을 열고, 앱을 시작하지 않는 준비 확인이 성공한 뒤 guest entry를 실행한다.
준비 확인은120초 이내에서 알려진0x80070520만 재확인하며 제품 설치/실행을 반복하지 않는다.
정상 stop의 빈 stdout을 JSON 실패로 오판하지 않고 실제 목록에서 소유ID 소멸을 확인한다.

Electron의 app.getPath('userData')와 backend에 전달한 APPDATA 경로는 같다고
가정하지 않는다. 초기 시작은 실제 native Electron 로그를 지정하고, 원래 지정한 환경변수
경로·native 경로·fallback의 존재와 원문 SHA를 실패 때도 보존한다.
각 회차의 native 프로필 부재를 확인한다. 앱 종료·잔류0 뒤에만 정확히 지정된
Sandbox의 합성 프로필을 해당 회차 WORK 안으로 옮기고 다음 회차가 새 프로필로 시작한다.
호스트/서버 프로필은 이동하지 않는다. source/target의 실제 경계와 reparse 여부를 확인한다.
측정 helper와 설치본은 그대로 유지하며 로그 경로 수정이 과거 TIMEOUT을 PASS로 바꾸지 않는다.

### 5.122 탭 시험의 격리 Python 모듈과 초기 오류 기록

탭 시험은 완료된 START10R3의 결과·정리 기록 SHA를 선행 조건으로 사용한다.
봉인 대상에서 제외할 manifest는 시험 입력 루트의 자체 manifest 하나이며, Chromium의
정상 구성 manifest 파일은 해시 목록에 포함한다. 예: hyphen-data/manifest.json은 보존한다.

묶음 Python의 ._pth 격리 모드에서는 스크립트 디렉터리가 자동 추가되지 않는다.
검산한 input 폴더를 명시적으로 먼저 지정하고, 실제 읽힌 네 지원 모듈의 경로·SHA를
게스트 결과에 남긴다. 기존 legacy 경로의 동명 모듈을 암묵적으로 재사용하지 않는다.
PowerShell entry는 표준 출력·오류를 비동기로 함께 읽고 실제 프로세스 종료 코드와
같이 보존하여 import 단계의 실패도 분석할 수 있게 한다. 이 처리는 제품 변경이 아니다.
실패한 봉인 묶음은 수정하지 않고 실행별 새 폴더에서 수정본을 검산·실행한다.

### 5.123 실제 카메라 표시와 종료 증거 경로의 대조

후보 CameraWidget는 내려받은 이미지를 blob URL로 img.camera-image에 표시한다.
관찰기는 원래 HTTP 주소만 찾지 않고 해당 실제 이미지 요소의 load/error와 크기·
visibility·blob 여부를 기록한다. HTTP200, blob 로드, 파일 저장은 서로 다른 증거다.
실제 브라우저 예비 시험도 fetch→blob→카메라 요소 표시 경로를 사용한다.
준비 실패 시에는 각 탭의 본문·카메라 상태·관찰 원문·스크린샷을 가능한 범위에서 보존한다.

후보의 종료 증거는 config.APP_DATA_DIR/shutdown_evidence에 생성된다.
환경변수 SFL_SHUTDOWN_DIAGNOSTIC_DIR에 지정한 폴더가 실제 저장 위치라고 가정하지 않는다.
backend의 실제 종료0·잔류0 뒤, 이번 격리 프로필 안의 실제 경로에서 증거를 회수하고
각 파일 SHA를 대조한다. 종료 코드만으로 receipt·worker drain 검증을 대신하지 않는다.

### 5.124 반복된 Sandbox 종료의 제한된 관리자 로그 읽기

같은 입력의 실제 VM 종료가 두 번 확인됐으므로 동일 시험을 반복하기 전에 환경을 진단한다.
개발 PC DESKTOP-SS5CURC의 두 실패 시간창에 한정해 Hyper-V 치명적 오류/덤프 생성과
알려진 Sandbox·컨테이너 ID가 포함된 이벤트를 읽는다. 각 시간창의 별도 오류 보고서
식별 필드와 지정된 덤프의 존재·크기·시각도 읽되 덤프 본문은 읽지 않는다.
시간 근접만으로 VM 식별·원인 확정을 주장하지 않는다. 예: WER 세 이벤트가 동일한
ReportId이면 보고 단계 세 개이며 독립 충돌 세 건으로 계산하지 않는다.

수집기는 고정 PC·경로·native PS5.1과 관리자 권한을 확인한 뒤 새 결과 폴더만 만든다.
일반 권한은 결과 생성 전에 거부한다. 실행기는 수집기를 읽기 잠금하고 SHA256을 대조한
상태에서 Windows 관리자 확인을 요청한다. 사용자 준비 응답 전에는 실행하지 않으며,
실제 권한 확인은 사용자가 직접 한다. 결과 파일별 해시와 실제 native 종료 코드를 남긴다.
접근 실패·이벤트 상한 초과는 INCOMPLETE로 기록한다.
설치·업데이트·VM 재실행·보안/ACL 변경·삭제·백업·서버 조작·외부 발송은 범위 밖이다.
외부 유사 사례나 다른 사용자의 업데이트 성공은 이 PC의 원인 또는 해결 증거가 아니다.

### 5.125 별도 Windows VM 준비와 설치 경계

사용자는2026-10-21 같은 개발 PC의 독립 Windows VM 준비를 선택했다. 기존 Windows와
Sandbox 설정을 변경하지 않고, 실행별 Desktop/SmartFactory 폴더에 공식 평가 ISO와
VM 구성 도우미를 준비한다. 다운로드는 전체 크기·공식 SHA256으로 검산하며 부분 파일의
예약 길이를 다운로드 완료로 판단하지 않는다. 이 준비 선택은 실제 VM 생성·설치 승인이 아니다.

제안 구성은 Generation2/4 vCPU/고정8GiB RAM/새 동적64GiB VHDX/secure boot/vTPM이다.
도우미는 고정 PC·native 관리자 PowerShell·실제 경로·reparse 부재·원본 ISO SHA·자원 여유·
동명 VM/대상 폴더 부재를 확인한다. 새 VM GUID를 기록하고 그 객체에만 설정을 적용한다.
기존 VM·물리 디스크·공유 경로·호스트 보안/네트워크/OS 설정은 변경하지 않는다.
오류가 발생하면 만든 VM을 자동 재시도·삭제하지 않고 ID/상태/실패 원문을 남긴다.

최초 준비 범위는 네트워크 연결 없는 정지 VM과 검산한 원본 DVD 연결까지다. OS 설치·
등록/로그인·평가판 인증·시험 실행을 완료했다고 해석하지 않는다. 공식 평가판 안내의 등록과
Microsoft 계정 조건을 사용자에게 알리며 계정 우회 또는 보안/개인정보 동의 자동 응답을 넣지 않는다.
예: 인터넷 연결이 필요한 초기 설정은 별도 확인된 연결 계획으로 진행하고, 성능 측정 전
가상 NIC 해제·외부 통신 차단을 다시 검증한다. 설정을 위해 연결한 상태에서 시험하지 않는다.

새 VM 안의 시험은 기존 동일 후보/입력/1·3탭/120초 warmup·300초 관찰/정상 저장 종료
계약을 유지한다. Sandbox 전용 사용자·경로 guard는 새 VM GUID·게스트 식별·전용 계정·경로
계약으로 명시적으로 대체한 새 묶음에서만 수정한다. 원래 봉인 묶음은 보존한다.
VM 생성 또는 OS 부팅만으로 환경 안정성·R2 성능·전체 출시 PASS를 판정하지 않는다.

### 5.126 승인된 새 VM의 Windows 설치 시작 준비

생성 완료 VM `b7ee8fcd-dd3d-46b5-901a-f465f9e06f6b`에만 적용하는 별도 시작 도우미를 준비한다.
기본 실행은 생성 증거·초기 VHDX·ISO 해시와 호스트 여유의 읽기 검사다. 실제 시작은 새 승인 후
관리자 Apply에서 VM ID/이름/설정/Off·가상NIC0·단일 초기 디스크·공식 DVD를 다시 확인한 뒤 수행한다.
VMConnect 창을 먼저 열고 해당 프로세스가 남아 있는지 확인한 뒤 정확한 VM 객체를 한 번 시작한다.
실제 Running은 Windows 설치 완료나 화면 표시 확인으로 간주하지 않는다.

화면 도구 초기화가 실패하면 별도 입력 주입 방식으로 대체하지 않는다. 사용자가 설치 화면을
조작할 수 있는지 시작 승인에 함께 확인한다. 대상은 VM 안의 빈64GiB 가상 디스크뿐이며
기존 파티션 삭제·호스트 디스크 변경·네트워크 추가·계정/보안/개인정보 동의 자동 응답은 하지 않는다.
예: 초기 설정에서 인터넷 연결이나 로그인 화면이 필요하면 그 지점에서 멈추고 실제 연결 계획을
준비한다. 사용자가 보는 설치 상태를 확인하기 전 완료나 시험 준비 완료로 기록하지 않는다.

시도·결과는 CreateNew로 한 번만 기록한다. 시작 뒤 관찰 오류가 나면 VM을 자동 재시작하거나
강제 종료하지 않고 실제 상태를 재조회한다. 시작 도우미의 일회 실행 완료와 실행 중 VM은 구분한다.

### 5.127 VM 연결 창 지연 생성에 대한 제한된 재개 도우미

실제 시작 도우미는 InputIdle 직후 MainWindowHandle이 0이라는 이유로 종료했고, 같은 프로세스의
창은 뒤에 나타났다. 원래 해시 결합 파일과 실패 결과는 보존하고 R2 파일·시도·결과 경로를 분리한다.
R2는 부팅 후 정지 확인 기록과 현재 VHDX 해시에 결합한다. 기존 Off/NIC0/CPU/RAM/단일 디스크/
DVD·공식 ISO/경로·관리자·자원 검사를 유지한다. 현재 상태 검증 없이 초기 디스크라고 재사용하지 않는다.

같은 세션·정확한 VM 창 제목·공식 실행 경로의 연결 창이 하나 있으면 재사용하고, 여러 개면 중단한다.
새 창을 시작하거나 기존 창을 선택한 뒤 실제 프로세스 종료 여부와 MainWindowHandle을 최대15초 확인한다.
프로세스 종료·시간 초과는 VM 시작 전 실패로 남긴다. 예: 첫 두 번은 handle0, 세 번째에 창이 생기는 경우
수용하고, 영구 handle0이나 이미 종료된 프로세스는 거부한다. 이 분기는 native PS5.1에서 회귀 검사한다.

이번 범위는 준비와 읽기 검사까지다. 사용자가 선택한 화면 도구 입력 복구 선행 조건을 유지하며,
읽기 복구만으로 VM을 다시 켜지 않는다. R2 준비·회귀 검사 통과는 실제 GUI/OS 설치/1·3탭 QA 통과가 아니다.

native PS5.1의 CP949 기본 해석에서 한글 창 제목이 변형되는 것을 확인했다. 한글 문자열을 포함한
R2 시작기는 UTF-8 BOM으로 저장하고 실제 native 파서의 문자열 값을 Unicode 기준으로 대조한다.
구문 오류0만으로 제목이 올바르게 읽힌다고 판단하지 않는다. BOM 변경 후 실행기 해시와 최종 회귀
기록을 갱신하고 이전 검사는 보존한다. 최종 검사는 제목 해석을 포함한6개이며 실제 관리자 GUI는 미검증이다.

### 5.128 실제 동시 조회 요구와 단일 브라우저 탭 시험의 경계

2026-10-21 사용자는 컴퓨터 약3대·각1탭을 사용한다고 확인했다. R2의 동시 조회 요구를
단일 화면 기준과 독립 클라이언트3개의 대시보드 동시 조회 조건으로 구체화한다. 이는 알려 준
운영 규모이며 3대를 최대 지원 수로 선언하지 않는다. 기존1·3탭 비교는 별도 미완료 상태로 보존한다.

| 조건 | 검증하는 내용 | 확대 해석하지 않을 내용 |
|---|---|---|
| 단일 실제 작업 화면 | 기존 Electron15분의 load/오류·화면 상태와 같은 실행의 저장 대응 | 120분 전체 표시나 다중 PC 성능 |
| 같은 브라우저1·3탭 | 보이는 탭1개/뒤쪽 탭2개의 요청·자원 영향 | 3개 화면이 동시에 표시되는 상황 |
| 격리 환경의 독립 클라이언트3개 | 별도 클라이언트별 요청·갱신, 한 backend의 동시 수집·저장 영향 | 3대 실PC의 네트워크·물리 표시·독립 자원 |
| 실제 운영3대·각1화면 | 각 화면의 실제 동시 갱신과 서버 수집/저장·오류 대응 | 확인하지 않은 더 큰 동시 접속 수 |

실행 전 대상 클라이언트의 PC/앱 종류·URL·가시 상태와 서버 작업자 창 포함 여부를 명시한다.
3탭을 만들었다는 사실이나 TCP 연결3개를 클라이언트3개로 세지 않는다. 각 클라이언트의
고유 실행ID·요청 시작/완료/실패, 이미지load/error·가시성, 시간 기준/불확실성을 남긴다.
브라우저 숨김/포커스 상태를 코드로 조작해 전면 화면으로 꾸미지 않는다. 서버와 클라이언트의
wall clock 차이로 단방향 지연을 계산하지 않으며 각 단조 시계와 동일 요청/실행 식별을 사용한다.

서버에서는 같은 build·설정·서비스 세대, health/data·CPU/메모리/디스크·큐·실패 카운터를 대조한다.
같은 설치본·자료·주기를 유지하고 단일/동시 조건의 실제 시작·끝과 간섭 작업을 기록한다.
120초 준비·300초 관찰은 격리 비교의 기존 수집 계약이며 새 운영 허용 지연값이 아니다.
200/500ms를 자동 실패 기준으로 되돌리지 않는다. 미완료 요청·필수 계측 부족은 INCOMPLETE,
요청/저장 오류는 해당 FAIL, 허용 지연·물리 신선도 증거 부재는 NOT_EVALUATED로 분리한다.
정상 종료 후 이번 실행의 fact/CSV/이미지와 저장 잔량을 연결하되 과거120분 시험을 반복하지 않는다.

현재는 요구와 검증 범위만 확정한 단계다. 새 VM의 Windows 설치·계정·격리 상태·실제 화면을
확인하기 전 기존 Sandbox의 사용자/경로 guard를 제거하거나 그대로 실행하지 않는다.
실PC에 새 소프트웨어·제어 접속·운영 부하를 추가하는 단계는 구체 실행 범위와 기존 승인을 대조한다.
기존 봉인 묶음·실패와 설치본을 유지하며 전체 출시HOLD/운영 승격 금지는 바뀌지 않는다.

### 5.129 별도 VM의 읽기 전용 실행 전 식별 검사

Sandbox 전용 WDAG 계정 조건을 단순 제거하지 않고, host VM ID와 실제 게스트의 UUID·이름·
계정SID·세션·Desktop/LocalAppData를 외부 pin된 binding으로 결합한다. VM ID와 게스트 UUID의
동일성을 추정하지 않는다. 실제 설치 전의 합성 identity는 회귀 검사에만 사용하고 실행 승인으로 쓰지 않는다.

`VM21_20261021_83be8a5a/preparation/vm_guest_guard.py`는 native PS5.1로 identity/network를
읽고 알려진 개발·운영 호스트를 거부한다. Hyper-V 모델·제조사, x64, session>0, loopback 주소만,
게스트 Desktop 하위 지정 작업 경로와 reparse 부재, 새 output/work·기존 설치 부재를 확인한다.
session>0을 실제 표시로 간주하지 않으며 별도 UI 관찰 조건은 그대로 남는다.

이 모듈은 제품을 시작하지 않는다. 전체 입력 해시·소유 프로세스 job·정상 종료·timeout/제어기 소실
정리는 별도 실행기에서 결합·검증해야 한다. 예: guard 통과 + manifest 미검산이면 실행 준비 미완료다.
현재 개발 PC 실제 식별의 거부와 합성/파일 경계 검사를 먼저 수행하며 실제 게스트 성공은 별도 남긴다.

### 5.130 확인된 VM 화면에 결합한 Hyper-V 관리 API 대체 경로

2026-10-21 사용자는 화면 도구 실패 시 다른 방법으로 설치·검증을 계속하도록 명시했다.
VMConnect 창 캡처와 별도로 공식 `GetVirtualSystemThumbnailImage`로 지정 VM의 현재
게스트 화면을 읽는다. host/VM GUID/이름/단일 VHDX/NIC0/Running과 native PS5.1 관리자
환경을 검사한다. 응답 크기와 RGB565 길이 prefix를 검산하며 해석 불일치 시 입력하지 않는다.

`Msvm_Keyboard.TypeKey`는 관찰된 화면의 SHA256을 바로 재확인한 뒤 허용된 탐색 키 한 개만
전달하고 다음 화면을 저장한다. 화면 변경 시 키를 보내지 않는다. 명령·비밀번호 입력이나
임의 키열, host 키 입력, 보안/인증 설정 자동화는 제공하지 않는다. UAC는 사용자 응답 영역이다.

DVD의 짧은 키 대기는 직접 확인한 문구의 픽셀 영역과 일치할 때만 Space 한 번을 전달한다.
부팅 전환 중 일시적인 이미지 미제공은 최대10초 안에서 다시 읽되 키를 보내지 않는다.
예: 부팅 실패 화면 → Tab 후 버튼 focus 픽셀 일치 → Enter → 관찰한 DVD 문구 일치 → Space.
재시작 뒤 설치 화면 확인 전에는 성공으로 기록하지 않는다. 자동 설치 재시도는 하지 않는다.

변경 범위는 승인된 빈64GB VM의 Windows 설치다. 네트워크 연결·계정·보안/개인정보 단계에서는
기존 절차대로 멈춘다. 게스트 설치는 제품 QA와 별개이며 실제 게스트 binding과 실행기 통합,
동시 조회 비교 검증을 대신하지 않는다. 기존 실패와 해시 결합 파일은 보존한다.

국가 목록 등 탐색은 `Msvm_SyntheticMouse`의 위치/스크롤/클릭 API를 같은 화면 해시 검사와
결합한다. 좌표는 실제 게스트1024×768 해상도와 대조하고 행동 하나 뒤 다시 읽는다.
OOBE가 공식 `I don't have internet` 선택지를 제공하면 승인된 NIC0 설치를 이어갈 수 있다.
등록/인증 요구를 제거하거나 명령으로 우회하지 않는다. 로컬 계정 이름·비밀번호·개인정보
화면에서는 입력을 멈추고 사용자에게 넘긴다. 관리 KVP의 OS 표기와 설치 화면이 다르면
둘을 원문 보존하고 게스트 내부 확인 전 하나로 단정하지 않는다.

### 5.131 별도 VM 시험의 소유 프로세스 수명 관리

영구 VM에서는 기존 Sandbox 전체 폐기를 시험 정리 수단으로 사용하지 않는다.
실행기는 새 multiprocessing 작업자를 만들고, 이름 없는 Windows job에 생성 핸들로
결합한 뒤에만 작업 gate를 연다. job은 KILL_ON_JOB_CLOSE를 사용하며 breakaway를 허용하지 않는다.
프로세스 이름이나 재조회한 PID로 종료 대상을 고르지 않는다. 결합 실패 시 gate는 닫힌 채
생성한 작업자 핸들만 종료한다. 작업자 이후 자식도 같은 job에 속해야 한다.

정상 종료는 작업자 종료 코드0과 job의 active_processes=0을 모두 확인해야 한다.
시간 제한은 협조 종료 신호와 유예 시간을 먼저 주고, 남은 시험 job만 종료한다.
시간 제한·비정상 종료·남은 자식·정리 검증 오류는 정리 성공 여부와 별개로 FAIL이다.
제어기 소실 시 마지막 job 핸들 폐쇄가 자식을 정리하며, 최종 보고가 없으면 PASS로 읽지 않는다.
예: 백엔드 정상 저장 실패 후 job 정리가 됐어도 데이터 보존이나 제품 QA 통과가 아니다.

개발 PC에서는 제품을 실행하지 않는 짧은 합성 작업자/자식으로 정상 종료, 시간 제한,
제어기 소실, 결합 실패, 비정상 종료와 무관한 프로세스 보존을 검사한다.
실제 게스트 identity·입력 manifest·작업자 협조 종료·화면 조건을 전체 실행기에 연결하기 전에는
이 검사만으로 VM 시험 준비 완료를 선언하지 않는다. 기존 Sandbox 봉인 묶음은 수정하지 않는다.

### 5.132 영구 VM 실행기 통합과 독립 조회 클라이언트

실행기는 실제 게스트 binding과 전체 입력 manifest를 외부 SHA256에 결합한다. 개발·운영
호스트는 결과 파일 생성 전에 거부하고, 기존 설치/work/결과가 있는 경로를 재사용하지 않는다.
manifest는 허용된5개 입력 root의 정확한 파일 집합·크기·SHA256·reparse 부재를 검사한다.
검사한 입력은 읽기 공유 잠금을 유지하며 job의 실제 작업 gate가 열리기 전에 모두 확인한다.

비교 조건은 기존 one/three(한 브라우저1·3탭)와 three_clients(독립 브라우저3개·각1탭)다.
후자는 각각 별도 프로세스·프로필·loopback 진단 포트를 사용하며 실제 visibility/bounds를
기록한다. 최소화·숨김 상태를 강제로 visible로 바꾸지 않는다. 3개 클라이언트의 readiness,
주기 관찰, 오류, 정상 종료 중 하나라도 불충분하면 전체 조건 수집 완료로 읽지 않는다.
기존 한 브라우저3탭의 마지막 탭만 visible이라는 계약은 별도 유지한다.

계측은 기존120초 warmup·300초 관찰과 실제 규모 FACT 입력을 유지한다. 정상 종료 요청은
브라우저 전체에 먼저 전달하고 공통 기한 안에 모두 닫힌 뒤 백엔드를 저장·종료한다.
상위 시간 제한의 협조 종료 신호는 준비/대기/측정 경계에서 확인하여 같은 정리 경로로 들어간다.
예: 수집 중 취소는 부분 결과와 종료 증거를 남기고 FAIL이며 다음 조건을 시작하지 않는다.

이 통합은 실제3대의 네트워크·모니터·물리 프레임 연속성을 증명하지 않는다. 최종 입력 묶음은
계정 설정 후 실제 게스트 정보에 결합하며, 개발 PC 검사는 제품 실행 없이 경계/취소 계약을
검사한다. 게스트 smoke 및 전체 설치/수집/정리의 실증은 별도 필요하다.

### 5.133 동시 조회 시험의 관찰 일정 완전성

동일120초 준비+300초 관찰의 요청 주기는 유지한다. health2초211개·data6초71개·자원5초85개의
예정 번호/시각을 원시 기록과 대조한다. 시작/최종 추가 확인 요청은 예정 수에서 제외한다.
예정 번호는 준비/관찰 단계 구분의 기준이며 실제 시작 지연은 별도 수치다. 누락·중복·범위 밖
번호·시각/단계 불일치가 있으면 관찰 완전성은 INCOMPLETE다. HTTP 오류·타임아웃은 측정된
요청 실패이지 관찰 누락이 아니며, 200/500ms 초과만으로 제품 운영 부적합을 정하지 않는다.

예: 자원85개가 모두 있어도 health3회/data1회가 빠지면 수집 요약은 측정 불충분이다.
이를 온도 행이나 이미지 파일 손실로 환산하지 않는다. 정상 정리된 다른 조건의 수집은 계속할
수 있지만 전체 요약에도 측정 공백이 있는 조건을 반영한다. COMPLETE도 제품 QA PASS가 아니다.

### 5.134 시험 VM의 정식 평가판 인증과 임시 연결 정리

계정 설정 후 확인한 인증 유예0분·라이선스 종료 이벤트·실제 시각 차이를 해결하는 준비다.
인터넷 연결은 기존 승인에서 보류된 범위이므로 실제 스위치와 변경안을 확인받기 전 연결하지 않는다.
대상은 정확한 VM GUID/단일 VHD/SFLQA SID·게스트 UUID/EnterpriseEval TIMEBASED_EVAL 채널이다.
호스트·서버·다른 VM과 라이선스 채널은 거부한다. 호스트의 실제 시각과 게스트를 대조해 현재 시각으로만
정정하며 rearm·키 교체·라이선스 파일 수정·서비스 정지는 하지 않는다.

`VM21_20261021_83be8a5a/preparation/activation-r2`의 기본 실행은 읽기 전용이다. 승인 후 Apply는
기존 Default Switch 하나와 새 임시 NIC 하나만 사용한다. 먼저 미연결 NIC의 실제ID/이름을 lease에
고정하고10분 뒤 정리 작업을 호스트에 등록·검사한 다음 연결한다. 정상/오류 정리 모두 동일한 소유
NIC만 제거하며 무관한 NIC가 있으면 제거하지 않고 격리 미완료로 보고한다. 제어기 소실 시에도
예약 작업은 남는다. 스케줄러의 자체 장애/지연까지 해제 시간을 보장한다고 주장하지 않는다.

게스트 기본 경로45초·공식 `/ato <Activation ID>`180초 제한을 두고, 종료 코드뿐 아니라 실제
LicenseStatus1·남은 유예양수·현재 시각 차이5초 이내를 확인한다. 이어 NIC0/loopback만 남음/
예약 작업 제거/PowerShell Direct 세션 제거를 검산해야 환경 준비를 인정한다. 실패해도 현존
라이선스 정보를 PASS로 바꾸거나 제품 시험을 시작하지 않는다. 인증·Windows 개인정보 입력은
사용자가 직접 수행하며 자격 증명은 메모리에만 유지한다. 적용 결과의 실제 인증/격리 증거는 별도다.

### 5.135 확보된 SPOT 포트의 불필요한 OS 조회 대기 제거

2026-10-23. 별도 보존한 10월 19일 오류 6건은 원 계수 계약상 guard 부재 대기 전의
양수 deadline 분기에 연결된다. OS 조회·lock·스케줄링 중 실제 지연 원인은 미확정이다.
이 근거를 10월 9일 최초 적용 timeout 또는 과거 이미지 drop 원인으로 확대하지 않는다.

로컬 수정의 성공 조건: guard가 이미 있으면 ownership lock 안에서 사용하며, 다른 포트의
재사용을 위한 OS 조회 때문에 그 lease를 지연시키지 않는다. guard가 없을 때만 만료된
quarantine/retry 포트의 OS 점유 상태를 조회하고 기존 배타적 bind 검사를 수행한다.
예: 두 포트 중 하나는 재사용 대기 만료, 다른 하나는 기존 guard 보유 상태이면 후자를
사용하고 OS 조회를 생략한다. 모두 사용했으면 조회 실패·점유 상태를 빈 테이블로 간주하지 않는다.

5초 양수 deadline은 lock 획득 후에도 검사하고 timeout=0의 즉시 시도 계약은 유지한다.
77초 격리·독립 reuse 검사·동시 lease 소유권·query 중 close 및 종료 후 재활성화 금지를 유지한다.
시험은 느린/실패 OS 조회의 불필요 대기 재현, 실제 조회가 필요한 deadline 초과,
lock 지연, 동시 acquire, TIME_WAIT loopback 및 transport 정상 종료를 포함한다.
단일 OS 호출의 hard 시간 상한이나 현장 오류 해결을 입증하지 않으며, 서버 적용은 별도 검증이다.

### 5.136 실제 표시 관찰 v2: 응답 객체 연결과 화면 상태 분리

2026-10-26의 PC_1·PC_2·PC_3 기록은 보존한다. 동일 바이트 응답의 연결 모호성과
`img.complete=false`를 DOM 부재로 합친 계측 한계를 고친다. 기존 v1 파일·해시·판정은
변경하지 않으며 새 v2 schema를 별도로 사용한다. 3대 자료를 승인된 4대 합격으로 바꾸지 않는다.

응답 객체 → 소비한 ArrayBuffer 또는 Blob → 단일 전체 바이트 Blob → object URL →
load → Element Timing presentationTime을 직접 연결한다. C32의 실제 경로인
`new Uint8Array(await response.arrayBuffer())`와 `new Blob([validatedPayload.bytes])`를
지원한다. 복사·부분 배열·여러 조각·출처 없는 Blob은 내용 해시가 같아도 연결을 추정하지 않는다.
해시는 연결의 근거가 아니라 원 응답과 표시 바이트가 같은지 확인하는 추가 검사다.

DOM 연결·크기·스타일·가림과 complete/naturalWidth/로딩 상태를 별도 저장한다.
로딩 중이라는 이유만으로 화면 가림으로 판정하지 않는다. 실제 표시 사건의 공백,
이미지 오류, 숨김·포커스 이탈, 관찰 자체의 공백은 계속 보존하며 물리 화면 무중단을
브라우저 API만으로 확정하지 않는다. 시작 전/측정 중/남은 시간/포커스 경고를 한국어로
표시하고 카메라와 겹치면 시작하지 않는다. 숨김 상태를 강제로 바꾸지 않는다.

성공 조건: 동일 바이트의 서로 다른 응답이 정확히 연결되고, 서로 다른 바이트·부분
버퍼·누락된 연결은 거부되며, 실제 가림·숨김은 미완료로 남는다. 응답·Blob·URL·fetch
후크는 정상/조기 종료/실패 모두 원복한다. 기존 900초·이벤트/바이트 상한과 새 이미지
HTTP 요청 금지, 런타임 전후 동일성, 독립 화면 증거 요구, 출시 HOLD를 유지한다.
격리 브라우저 회귀와 해시 확인된 C32 설치본의 프런트엔드로 호환성을 검사한 뒤에만
다음 현장 관찰 묶음을 준비한다. 기존 120분 시험은 자동 반복하지 않는다.

계측 연결 전에 이미 시작된 요청은 새 계측기의 요청 시작 증거를 갖지 않는다. 이를 정상
연결로 추측하지 않도록 설치 후 최대10초의 준비 구간을 별도로 둔다. 관찰한 요청→응답→
Blob→load에 연결되는 첫 실제 presentationTime을 900초 표시 구간의 시작으로 삼는다.
준비 구간의 요청·load·표시·상태·오류도 원본에 남기고 준비 시간은 제품 시작 성능으로
해석하지 않는다. 준비가 끝나지 않거나 조기 종료되면 INCOMPLETE다. 이미 시작한 측정
구간의 불량 기록을 제외하거나 시작점을 다시 고르는 동작은 제공하지 않는다.

최종 판정기는 요약의 PASS를 신뢰하지 않고 객체 연결, 원 응답/표시 바이트, 단조 시계,
정확한900초, 화면 상태, 같은 build/logger와 외부 화면 확인을 재검산한다. 원시 상태 관찰
간격과 최대 공백도 별도 보고하며 수치가 없거나 설명되지 않은 공백은 완전성으로 인정하지
않는다. 4대 물리 식별, 독립 사용자 화면 확인, 정책 해시와 기존 성능 수치는 그대로 유지한다.

### 5.137 사용자 승인에 따른 총3대 검증 범위

2026-10-26 “계속 총 3대만 가능, 해당 기준으로 변경” 승인을 이후 v2 현장 판정에 적용한다.
서버 PC_1과 조회 PC_2·PC_3의 서로 다른 물리 컴퓨터3대·각1화면을 확인한다. 5.136의
4대 언급과 기존4대 정책은 변경 전 기록이다. 현재 정책은
`approved_release_policy_20261026_three_pc.json`이며 기존 정책 해시를 이전 기준으로 연결한다.
정책 로더는 동시 대수 외 수치·후보·알람·과거 자료·복구 조건이 달라지면 거부한다.

기기 수가2대이거나 같은 PC를 중복 식별한 경우는 미완료다. 세 실제900초 구간 모두에서
세 화면이 함께 조회됐다는 확인과 각 구간의 숨김/가림·흰 화면 기록이 필요하다.
동시 대수 변경만으로 기존 실패·미완료를 PASS로 바꾸거나4대 이상의 성능을 주장하지 않는다.

### 5.138 v2 현장 결과에 따른 계측 보완

PC_2는 시작 전 visible/focus 결합 검사에서 끝났고 두 값을 따로 기록하지 않았다.
사용자는 화면을 전환하지 않았다고 확인했으므로 화면 장애나 사용자 실수로 단정하지 않는다.
다음 묶음은 시작 전 최대30초 동안 visible·focus·DOM 가림을 각각 기록하고,
영상과 겹치지 않는 안내에서 대시보드 빈 곳을 클릭하도록 알린다. 실제 준비 상태가
확인된 뒤에만 기존 첫 표시 경계와900초 관찰을 시작한다. 초점/숨김 상태를 덮어쓰거나
측정 중 불량 구간을 제외하지 않는다. 준비 실패도 JSON에 남긴다.

서버3회·PC_3 48회의 동일 수신 시각/동일 바이트 재응답이 확인됐다. 직접 객체 연결과
표시 시각을 검증한 동일 마지막 프레임 재표시는 별도 반복 기록으로 보존하되 새 프레임
수에는 넣지 않는다. 다음 새 프레임까지의 공백과 마지막 경계 공백에 그대로 반영한다.
같은 식별자의 다른 바이트, 이전 프레임으로 역행, 응답 식별자 중복은 계속 미완료다.
기존 raw·계측 소스·판정은 보존하고 변경된 판정기 버전을 분리한다. 기존 CAPTURE_INCOMPLETE를
자동 PASS로 바꾸지 않는다. 회귀 검증은 반복만 지속될 때2초 공백이 실패함을 포함한다.

### 5.139 PC_2 보완 관찰의 명시적인 시작 조작

사용자가 PC_2만 보완하는 관찰을 승인했으나 새 파일도 준비 단계에서 종료됐다.
`BROWSER_1792986179610_9cae7cdc9049c1ba_PC_2.json`의 284개 상태는 모두 화면 보임·
DOM 존재·DOM 가림 없음·입력 초점 없음이며 실제 관찰 본문은 없다. 초점 부재의 원인은
확정하지 않았고 제품 영상 장애나 사용자 실수로 단정하지 않는다.

보완은 수집기와 판정 기준을 바꾸지 않고 휴대용 실행기의 시작 절차에만 적용한다.
`presentation_manual_start.cjs`는 영상 밖의 안내에 '15분 측정 시작'과 '취소' 버튼을 둔다.
최대5분 동안 준비 상태만 기록하며 실제 클릭(isTrusted)과 기존 visible/focused/DOM 조건이
동시에 확인돼야 다음 단계로 간다. 합성 click, 초점 없음, 숨김, 가림은 시작을 허용하지 않는다.
준비 시간은900초 측정에 넣지 않으며 초점·visibility를 바꾸는 호출을 하지 않는다.

PC_2 전용 실행기 v4는 번호 입력 prompt와 고정10초 지연을 없앤다. 명시적 시작 후
서버 build/logger를 다시 읽어 준비 전과 같음을 확인하고, 기존30초 사전 검사와 첫 표시
경계부터900초인 계측기를 그대로 사용한다. 취소·준비 만료·세대 변경은 미시작으로 보존한다.
이미 측정 중인 구간을 다시 고르거나 기록에서 나쁜 구간을 제거하지 않는다.

검증 조건은 클릭 전 후크 없음, 합성 클릭 거부, 초점/숨김/가림에서 시작 거부, 정상 클릭 후
기존 C32 화면의 응답→Blob→실제 표시 연결, 취소/세대 변경 시 후크 없음과 안내 정리다.
기존 v3 묶음·원시 결과·PC_1/PC_3 통과 기록은 그대로 보존한다. 새 실행기는 준비 검증만
통과한 상태이며 PC_2 현장900초 및 전체 출시 판정 완료를 뜻하지 않는다.

### 5.140 PC_2 보완 결과와 기존 표시 기록의 연결

사용자가 승인한 PC_2만의 보완 관찰은 서버가 일반 실행으로 재시작된 이후다. 따라서 기존
PC_1/PC_3 기록과 새 PC_2의 logger를 같게 바꾸거나 동시에 계측된 한 구간이라고 표현하지 않는다.
`assess_presentation_supplement.py`는 원시 기존3대 기록을 재판정해 PC_1/PC_3 PASS와
PC_2 준비 실패·관찰 본문 없음이 확인된 경우에만 보완을 검토한다. 이미 측정된 실패를
새 좋은 구간으로 교체하는 기능은 제공하지 않는다. 기존 양성 실패는 FAIL로 보존한다.

기존 실행의 사전/사후 서버 정보와 새 실행의 전후 서버 읽기를 고정 해시로 결합한다.
후보 build·config가 같고 새 실행의 logger·PID/생성 시각/사용자·세션이 유지돼야 한다.
서버와 개발 PC의 시계가 같다고 가정하지 않는다. 개발 PC의 SSH 실행 영수증과 PC_2
브라우저 시작/끝 시각을 사용해 새 기록 전후를 읽었음을 확인하며, 실제900초는 페이지의
단조 시계로 재검산한다. 각 파일과 영수증의 해시 결합은 호출 단계에서 완료한다.

새 PC_2 결과의 run_id에 결합된 별도 사용자 확인이 필요하다. 기존과 같은 물리3대가
해당15분 동안 함께 조회했고 PC_2가 보이며 가려지지 않았는지, 흰 화면 수를 기록한다.
서버/PC_3은 재계측할 필요가 없지만3대 조회 부하는 유지한다. 새 원본에도 기존900초,
응답→Blob→표시 바이트/시각, 전체 상태 범위·성능 기준을 그대로 적용한다.
출력에는 각 기기의 별도 logger와 원래 미시작 기록, 원래 판정, 같은 계측 구간이 아님을
명시한다. 구성 요소 PASS도 출시 HOLD·promotion_allowed=false를 유지한다.

관찰 본문 없이 준비 실패한 기록의 오류 표시는 `measurement-not-started`로 구분한다.
after identity가 없다는 이유만으로 서버가 실제 재시작됐다고 해석하지 않는다. 관찰 본문이
있는 기록의 요청 오류를 이 분류로 숨기지 않는다.

### 5.141 승인된 PC_2 한 실행의 화면 가림 예외

사용자가 “이번 화면 가림 예외 수용”이라고 승인했다. 별도
`approved_display_exception_20261026_pc2.json`은 정확한 run_id·원본 SHA256·기존 정책 SHA256과
약3.987~32.111초의 단일 초점 이탈 구간에만 적용한다. 사용자가 확인한 물리적 가림의 정확한
시작·끝을 측정한 것은 아니며, 이 시간 범위는 상태 표본에 근거한다. 원본과 기존 엄격 판정은 보존한다.

보완 판정기는 기존 두 PC PASS와 동일 설치본·설정·새 실행 전후 동일성, 900초 전체 및
응답→Blob→표시 연결을 그대로 검증한다. 승인·파일 해시·구간·사용자 확인이 모두 일치할 때만
해당 구간의 focused=false를 예외로 수용한다. 숨김·DOM 가림·필드 누락·추가 초점 이탈·
요청 오류·흰 화면·짧은 측정·바이트 불일치를 면제하지 않는다. 수치 충족 시 결과는
`ACCEPTED_WITH_TEST_CONDITION_EXCEPTION`이며, 물리 화면 무중단 PASS나 자동 출시 승격이 아니다.
다른 실행·다른 성능 항목에 적용하지 않고 기존 수집기와 설치본도 변경하지 않는다.
