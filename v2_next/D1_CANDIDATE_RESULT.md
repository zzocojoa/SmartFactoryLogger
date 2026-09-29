# D1 새 후보 격리 검증 결과

이 문서는 9월 23일 후보 빌드·격리 시험 당시의 기록이다. 이후 같은 후보의 실제 120분 시험·원본 복귀는
[D1_FIELD_RESULT.md](D1_FIELD_RESULT.md), 9월 29일 잔여 한계 수용·미서명 운영 후보 승인은
[D1_PROMOTION_DECISION.md](D1_PROMOTION_DECISION.md)의 최종 승인 기록을 따른다.
아래의 보류·미실행 문구는 작성 당시 상태이며 새 후보 시험 결과와 혼합하지 않는다.

2026-09-23. **승인된 로컬 커밋·미서명 후보 빌드·Windows Sandbox 설치/실행/원본 복귀 완료. 운영 적용은 보류.**
이 문서는 D1 코드 시험 보고서 뒤의 후보 단계를 기록한다. 이전 120분 현장 결과는 새 후보 결과에 포함하지 않았다.

## 변경과 후보 식별

- 로컬 브랜치: `codex/temperature-diagnostics-reason-d1-20260923`.
- 커밋: `830a89c35d50b71dc56e5c2ac9ec9511f1ef6f77`. 검토된 11개 파일만 커밋했다. push/PR/merge 없음.
- 원래 작업공간의 branch/HEAD/status와 변경 41개 파일 SHA256 일치. 새 빌드 clone도 commit 고정·clean.
- D1은 진단 제외 evidence와 rule v6/검증기/파일 분리만 변경한다. Temperature·상태·cause·안전 gate는 유지한다.
- NSIS SHA256: `7e565dedb6613bc6e01fe7bd1cd39a15f623096e1d9951e3bb495fac31d31d55`.
- Backend EXE SHA256: `7f67b75e3ec67ae39649016d58a1384254d89bcbc4d72381da9da5827e1fa139`.
- Electron EXE SHA256: `8f3e87fbfa98c01b21d43bb32ea018bd2b66d40692457d77e22471ca59b8c014`. 앱 코드는 별도 app.asar의 source identity 검증으로 결합했다.
- 세 EXE의 Authenticode는 `NotSigned`; `UNSIGNED_INTERNAL` 후보다. 버전명 1.0.26만으로 식별하지 않는다.
- 추출한 NSIS payload 1812개를 빌드 산출물과 전수 대조했다. backend bundle manifest·provenance·Electron source identity도 일치한다.

## 검증 결과와 범위

새 clean clone, Windows, CPython 3.12.6, 해시 고정 Windows release lock으로 실행했다.
`npm run health`: backend **836**, Electron **94**, frontend Node **9**, Vitest **301** 통과; 실패/skip 0.
backend Ruff/mypy, frontend lint/typecheck, 5개 QA self-test 포함. 두 npm audit의 알려진 취약점 0.
`scripts/deploy.ps1`, `npm run dist`, 패키지 추출/identity 검사 모두 exit 0.

EXE의 PYZ에서 production 모듈을 직접 읽는 별도 계약 시험 **24개 통과**, 실패/오류/skip 0.
다섯 제외 사유, 실제 driver/service의 미종료·재시작 차단, 실제 writer loop의 v5→v6 분리를 포함한다.
source fallback 0, non-loopback 연결 시도 0. 외부 의존성과 테스트 코드는 고정 source/venv를 사용했다.
이는 frozen EXE 전체 실행과 구분되는 패키지 bytecode 합성 시험이다. `sys.frozen` 위장이나 commit 주입은 없다.

Sandbox에서는 외부 네트워크·클립보드 공유를 끄고 입력 폴더를 read-only로 매핑했다.
설치는 실제 NSIS `/S /currentuser`로 기본 위치에 수행했다. 새 설치→제거→원본 설치/실행→후보 업그레이드/실행→후보 재시작→원본 재설치/실행을 완료했다.
각 설치 payload/등록/바로가기, cold state, PID/시작시각/EXE 해시, 정상 종료·port 해제, 설정/데이터 보존을 확인했다.
폐쇄형 fixture는 실제 앱의 REAL driver에 loopback MELSEC/LS/HTTP 응답을 제공했다. production loop를 교체하지 않았다.

| 실행 | wide 행 | 해당 서비스 fact | 상태별 행 |
| --- | ---: | ---: | --- |
| I2-original-runtime | 355 | 24 | {'startup_pending': 15, 'valid': 340} |
| I4-candidate-runtime | 264 | 24 | {'startup_pending': 11, 'valid': 134, 'under_range': 54, 'over_range': 65} |
| I5-candidate-restart | 334 | 24 | {'startup_pending': 12, 'valid': 163, 'under_range': 72, 'over_range': 87} |
| I6-original-restored-runtime | 356 | 24 | {'startup_pending': 16, 'valid': 340} |

후보 두 실행에서 정상500→under-range6553.4→over-range6553.5→정상500 복귀를 관찰했다.
under-range는 Temperature blank·cause unknown·confidence0과 `diagnostics_excluded_fact_only`를 유지했다.
over-range blank, 복귀 후500, 비 under-range의 제외 evidence 부재를 확인했다.
다른 네 제외 사유는 위 PYZ 합성 시험의 근거이며 설치 EXE의 장비 응답만으로 재현됐다고 주장하지 않는다.
각 후보 CSV에 현재 commit의 production validator를 새로 실행해 exit0을 확인했다. 이전 validator 결과 재사용 없음.
총 **89개 검사 통과, 0개 실패**. 네 logger/SPOT 세대, 서비스별 fact 연속성·중복 없음·정상 drain/finalized,
실제 P2 API와 재시작 cursor reset, 후보의 9개 shutdown stage, 정상 WM_CLOSE 및 프로세스/포트 잔존 없음을 검증했다.

## 복귀·호환성·위험

위험도는 중간이다. evidence 의미 변경에 따른 rule 분리로 파일이 추가될 수 있으나 기존 데이터 변환은 없다.
이전 wide CSV/sidecar와 schema rollover된 fact의 바이트 보존을 확인했다.
복귀 원본은 build `d7a1b20f96711fb07fc7add0867e79ee36506fce`, NSIS SHA256 `1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F`다.
원본 재설치 뒤 새 수집 파일로 정상 수집/저장/종료했고 후보 기록을 보존했다. 서버는 변경하지 않았다.
관측성은 정책 제외와 결측/오래됨/필드 실패를 구분한다. 호환되지 않는 rollover target은 덮어쓰지 않고 실패를 기록한다.
미종료 발생 시 설치/복귀를 자동 진행하거나 강제 종료하지 않는 절차를 유지했다.
독립 검토는 QA 도우미에 대한 읽기 전용 정적 검토로 차단 이슈 없음. production diff는 기존 자체 검토 범위다.

## 남은 판단과 다음 작업

새 후보의 실장비 현장 관찰, 실제 자정 전환·OS clock 보정·미종료·over-range 현장 사건은 **미검증**이다.
합성 회귀/모의 패키지 시험을 현장 사건 증거로 바꾸지 않는다. 운영 OS 시각·장비 설정 변경 없음.
실제 설정 14개 일치, 기록상 fingerprint mismatch는 build identity 차이로 재현됐지만 모델 표기와 comparator 경계/전체 operator 승인은 미검증이다.
operator/comparator 검증값을 true로 변경하지 않았다. 자세한 설정 대조는 `SPOT_SETTINGS_COMPARISON_D1.md`를 따른다.
서명·운영 승격과 잔여 현장 공백의 위험 수용도 승인되지 않았다.

**다음 작업은 이 해시의 새 후보에 대한 서버 내부 현장 시험 범위와 복귀 조건을 확정하는 것이다.**
서버 설치/운영 적용은 이번 승인에서 제외됐으므로 실행하지 않았다. 승인 시 개발 준비부터 `Z:\SmartFactory\날짜\send`와 서버 로컬 최종 폴더 복사까지 Codex가 담당한다.

## 증거와 명령

작업 루트: `C:\Users\user\Desktop\SmartFactory\D1_CANDIDATE_R1`.
명령/환경/cwd/시간/종료코드/로그 해시는 `logs/*.json`; 빌드 입력은 `approval-and-source.json`과 `source-commit.json`.
패키지 proof: `extraction.json`, `paths.json`, `signature-status.json`, `electron-source-identity.json`.
실행 행렬: `candidate-regression-matrix.json`. 결과: `candidate-result.json`.
PYZ 시험: `packaged-contract/`. Sandbox 입력 manifest·bootstrap·설치/실행/closeout 원문: `sandbox/`.
커밋 전체 diff: `committed-full.diff`; 이전 단계 증거를 덮어쓰지 않고 `candidate-830a89c-r1/`에 새 증거 사본과 해시 목록을 보관했다.
본 보고서는 후보 빌드 후 별도 문서로 작성했다. 후속 문서 커밋은 시험 후보의 production source나 실행파일 identity를 바꾸지 않는다.
