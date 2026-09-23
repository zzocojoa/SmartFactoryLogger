# D1 진단 제외 사유 기록

2026-09-23. 로컬 코드·시험·결과 보고 범위. commit/push/PR/merge/설치/배포는 수행하지 않는다.

## 기준과 작업 분리

- 원래 작업공간: `codex/temperature-history-p2-20260922`, HEAD `1cd48e6457637e97ca77787c0744579cc1479dfb`.
- staged 0, unstaged 3, untracked 38개 파일의 상태·해시와 diff를 별도 보존했다.
- 원격 master fetch 기준: `501d26245f14d7a4325048f17616a431cca1e7e7`.
- 이 기준에서 별도 worktree의 `codex/temperature-diagnostics-reason-d1-20260923`를 생성했다.
- 강제 checkout/reset/clean/stash 없이 원래 파일을 보존한다.

## 추적과 최소 변경 계획

`spot_diagnostics.evaluate_diagnostics_eligibility`는 이미 fact_only/previous_poll/stale/
capture_missing/required_field_failed 등을 구분한다. `temperature_operational`은 이 판정과
metadata 집계용 상세 사유를 유지하면서, row evidence에 모두 `diagnostics_missing_or_stale`를
넣는다. 현재 production 경로에서 이를 재현한 뒤 해당 행 표현만 구체화한다.

기존 eligibility 순서·suppressed 집계 대상·Temperature·출력 상태·cause·안전 gate는 유지한다.
행 evidence는 `diagnostics_excluded_<기존 reason>`으로 기록하고, 이전 rule v5와 새 v6를
구분한다. 새 validator는 v5 안전 검사를 유지하며 v6의 모호하거나 잘못된 제외 표기를 거부한다.
외부 입력의 제외 표기는 현재 판정으로 재계산한다. CSV 열과 schema 구조는 변경하지 않는다.

## 검증 순서

1. 5개 사유와 정책 우선순위의 현재 실패 재현.
2. 최소 수정 후 실제 PLCService·CSV writer의 임시 파일 확인, output contract 검사.
3. 기존 G/T/C/L1/P2 및 backend 통합·lint/typecheck/계약 QA와 diff 자체 검토.
4. 기존 현장 증거의 fingerprint_mismatch를 승인 설정과 대조할 자료를 확인.

장비 설정과 운영 후보 단계는 별도 상태로 기록한다. 새 실행파일을 만들거나 이전 120분 결과를
새 D1 코드의 현장 결과로 사용하지 않는다. 이후 실제 후보 commit·실행파일 고정/패키지 검증과
운영 적용 결정에는 별도 승인이 필요하다.

## 실행 결과

- 사유 시험은 fixture 타입 오류를 바로잡은 뒤 기존 코드에서 6개 시험 / 12개 assertion 실패로 재현했다.
- `diagnostics_excluded_<reason>`으로 표현을 변경했다. eligibility·기본 우선순위·집계 범위는 유지했다.
- rule v6와 validator를 맞췄으며, 같은 열의 v5 CSV에 append되는 문제도 별도 실패 시험으로 확인하고 rule별 rollover로 막았다.
- 실제 service→writer→임시 CSV 및 metadata 경로와 기존 파일 보존/충돌 거부를 검증했다.
- 최초 전체 backend: 834개 실행, 실패 0, skip 1(비공개 F01 fixture 환경변수 없음).
- 원본 F01 fixture 해시 확인 및 경계시험 2개 추가 후 최종 전체 backend: **836개 통과 / 실패 0 / skip 0**.
- lint·typecheck와 종료/설치 준비 QA 자체검사 5종 통과. 기준 코드와 5,200개 합성 입력을 대조해 evidence 외 모든 decision 필드가 같음을 확인했다.
- 원래 변경 파일 41개 전부 해시 동일, Git status/branch/HEAD 동일. 독립 검토는 하지 않았으며 최종 diff는 자체 검토했다.

## 후속 단계 상태

저장된 승인 fingerprint는 이전 캡처의 21개 필드를 그대로 두고 build commit만 v1.0.20으로
되돌렸을 때 재현됐다. 최근 120분 후보 metadata와 비교해도 22개 중 build commit만 다르다.
이는 **기록된 불일치 원인**의 재현이며 현재 장비의 설정 확인은 아니다. 실제 readback은
`not_supported`였고 operator/comparator effective verified는 false로 유지했다.

D1 로컬 코드·회귀 검증은 완료했다. 현재 장비 설정 대조, D1 후보 commit/EXE 고정,
패키지 검증과 운영 적용 결정은 미완료이며 이전 120분 결과로 대체하지 않는다.
최종 결과는 `DIAGNOSTICS_REASON_RESULT_D1.md`, 실행 행렬과 원문은
`artifacts/temperature-diagnostics-reason-d1/`에 남긴다.

## 실제 장비 읽기 전용 대조

2026-09-23 16:07–16:12 KST, 서버 Chrome으로 SPOT Settings/I/O/Focus/Alarms/
Time Functions/Info를 읽었다. 승인 fingerprint 재구성 자료와 설정 14개가 일치했다.
장비 모델 표기는 `AL Spot`, 설정 문자열은 `SPOT+ AL`이며 동일성은 미검증이다.
비교기의 `<`/경계 정의도 화면에 없으므로 검증값을 변경하지 않았다. firmware 표시는 V: 40.38이다.
조회용 Chrome을 닫은 뒤 원래 앱의 Running·숫자 온도·Count 증가를 확인했다.

기존 D1 코드 완료 시점의 diff/manifest/행렬은 artifacts의 `d1-local-complete-snapshot/`에 보존했다.
현재 단계의 대조·한계·로컬 commit과 개발 PC 격리 후보 검증 승인 범위는
`SPOT_SETTINGS_COMPARISON_D1.md`에 기록했다. 운영 적용은 여전히 미승인·미실행이다.

## 후보 준비 승인

2026-09-23 로컬 commit·미서명 후보 build·Windows Sandbox 설치/실행/원본 복귀 검증 승인을 받았다.
검토한 11개 파일만 commit한 뒤 그 commit에서 별도 소스 사본을 생성한다. 이전 worktree와
후보/증거는 보존한다. push·PR·merge·서버 설치·운영 승격은 범위 밖이다.
