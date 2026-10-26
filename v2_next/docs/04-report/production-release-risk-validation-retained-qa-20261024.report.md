# 보존된 C32 현장 기록의 QA 조건 대조

## 2026-10-26 최종 상태 — 승인 범위의 운영 승격 완료

사용자의 “세 항목 처리안 승인”을 정확한 C32와 실행 기록에 연결하고 최종 통합 QA를 마쳤다.
판정은 `PROMOTED_WITH_DOCUMENTED_LIMITATIONS`다. 원래 기술 FAIL·INCOMPLETE는 유지한다.
실제 서버 설치 payload 1,867개·설치본·설정·일반 사용자 프로세스·수집 증가를 다시 확인했고,
`v1.0.32` 태그가 build `cd46692ac9c551080c57d8168fa9ea5abd530206`을 가리킴을 로컬/원격에서 검산했다.
현재 운영본과 다음 변경의 롤백 기준을 동일 C32/installer SHA256으로 갱신했다.

[최종 보고서](production-release-risk-validation.report.md)가 현재 판정이다.
아래 이전 날짜·단계의 HOLD, 승인 대기, 미완료 문구는 당시 이력이며 현재 상태를 덮어쓰지 않는다.
알람 OFF·물리 NOT_TESTED, 과거 자료 학습 사용 보류, 초기15분 health6건과 PC_2 약28초 가림의
한 실행 예외, 원인 미확정의 제한을 유지한다. 새 설치·앱 재시작·전체 백업·15/120분 반복은 없다.


## 2026-10-26 검사 수와 실행 의미 보충

[원문 구문 분석·보충 감사](C:/Users/user/Desktop/SmartFactory/R1QA32_20261026_c18b42f6/audit.json)에서
같은 QA 원문의47개 호출 위치/42개 고유 이름을 확인했다. 승인 범위의 정상 경로 검사 이름은
40개이고, 아래 회고 감사의41조건에는 오류 처리 전용 `Finalized artifact inspection`에 대한
파생 확인1개가 포함된다. 원래 명령에서 이 항목이 PASS로 실행됐다는 의미가 아니다.
물리 comparator의 승인 제외1개와도 구분한다. 기존 review.json·해시·회고41조건은 수정하지 않았다.

기존 현장/종료/소비자 근거는 유지하지만 이름 수 대조만으로 원래 명령 실행과 의미가 완전히
동일하다고 주장하지 않는다. 원래 one-command의 새 실행 기록은 없다. 최종 QA 절차에 보존
근거를 사용하는 [처리안](C:/Users/user/Desktop/SmartFactory/R1QA32_20261026_c18b42f6/decision-review.md)은
승인 전이며, 이 문서 보충으로 필수 실행 조건을 자동 변경하지 않는다. 아래 날짜의 표시 미완료는
당시 상태이고 현재 표시 항목은 별도 승인된 한 실행의 가림 예외를 포함해 수용됐다.

2026-10-24. 완료한 4대 동시 조회·120분 관찰·CSV 검사를 반복하지 않고, 승인된 출시
범위에서 기존 QA 조건을 실제 원시 기록과 연결했다. **42개 검사 이름 중 41개 조건 충족,
Low Signal comparator 1개는 승인된 사용 제외 조건에 해당한다. 전체 출시는 HOLD다.**

이는 `qa_spot_temperature_v25.ps1`을 새로 현장에서 실행했다는 뜻이 아니다.
기존 현장 실행·정상 종료·상세 소비자 결과의 회고 대조이며 실제 화면의 새 수치 기준이나
모든 출시 조건을 이 결과만으로 통과시키지 않는다.

## 대상과 직접 확인한 근거

- 후보: 1.0.32 / `cd46692ac9c551080c57d8168fa9ea5abd530206`.
- 닫힌 실행: logger `9a245aa0-46ad-4ac3-b908-69c334f49835`,
  `Factory_Integrated_Log_v2_20261023_172545.csv`.
- 120분의 정기 health 3,600개와 처음/마지막 2개의 manifest·요청 기록·본문 SHA256,
  응답 완료·요청 순서·동일 build/logger/CSV를 직접 대조했다.
- 초기/최종 payload 기록의 installer SHA256은 승인 정책의 `558658cf…232f`와 같다.
  native main/backend의 PID·생성 시각·실행 경로가 종료 기록과 일치한다.
- 실제 상세 CSV 소비자의 입력 5파일(약3.62GB), 사용한 검사 EXE, projected metadata,
  stdout/stderr·terminal·기존 review를 재검산했다. 상세 소비자는 다시 실행하지 않았다.
- metadata의 승인 프로파일 fingerprint, 운영자 확인, drift 없음, 알람 OFF 및 comparator
  false를 확인했다. 물리 시험은 계속 `NOT_TESTED`다.

| 대조 항목 | 결과 |
|---|---|
| health 원문 3,602개 | 모두 성공 응답. 같은 logger·build·CSV |
| CSV 행 수 | 관찰 시작5,693 → 끝35,815, 역전 없음. 최종 마감37,944 |
| 원장 쓰기/참조 실패·origin 불일치·시계 이상 | 모든 health 표본에서0, 필드 누락 없음 |
| 원장 마감 | 쓰기 실패0·미저장 spool0 |
| 실제 프로세스 종료 | native handle을 유지한5개 프로세스 exit0·강제 종료false |
| 상세 CSV 소비자 | 기존 실제 exit0·입출력 해시·현재 닫힌 실행 결합 확인 |
| 기존 QA 검사 이름 | 소스에서 추출한42개와 대조 목록 일치. 41충족·1범위 제외 |

`current_observation`은 응답의 출처이며 모두 유효한 온도라는 뜻이 아니다.
기존 invalid sentinel·과거 사용 보류·초기 두 후보 실행의 실패/증거 부족은 그대로 유지한다.

## 검사와 재현

실행 파일:
[audit_retained_qa.py](C:/Users/user/Desktop/SmartFactory/QA32_JOIN_20261024_647fe08a/audit_retained_qa.py).
`C:\Python312\python.exe audit_retained_qa.py` 실행은 종료 코드0(`a724eb`)이며,
7,219개 사용 파일의 크기·SHA256을 [review.json](C:/Users/user/Desktop/SmartFactory/QA32_JOIN_20261024_647fe08a/review.json)에 기록했다.
기존 결과를 덮어쓰지 않도록 새 결과 파일만 생성한다.

검증 과정에서 실제 입력의 복사본에 중간 표본 오류·필드 누락·다른 build/logger·카운터 역전,
알람 ON·문자열 false·다른 마감 세대·미저장 잔량·강제 종료·PID 재사용·소비자 증거 누락을
넣은13가지 경우가 모두 거부됨을 확인했다. 원시 파일은 변경하지 않았다.

결과 SHA256: `4a1034f5736ffb2621ed1fafdaff90488be11544b9164a6ff274b81a9721ac48`.
감사 스크립트 SHA256: `afc5816f43a0676a95ca02f532c4bbdd4163a4635205518840f9cd891496533b`.

## 현재 서버와 남은 조건

00:07:18 KST 승인 SSH 읽기에서 C32 Running, 같은 일반 실행 logger
`5be11b2f-d2cc-42b9-b8ce-3d19fdc72b7e`, 자정 이후 `20261024_000000.csv`,
원장 쓰기/참조 실패0, 당시 `valid_temperature`를 확인했다. 19221 listener는 없다.
00:07 이후 원격 화면에서 Smart Factory가 맨 앞에 있고 카메라·온도·작업60073/7이
표시됨을 직접 확인했다. 표시된 최근 적용 시각은10월23일23:58:01이며 작업값은 수정하지 않았다.

남은 것은 실제 각 PC의 표시 시각과 독립 화면 증거, 이를 기존 설치·복구·시작·수신·저장
자료와 결합한 최종 출시 판단 및 승격 후 롤백 기준 갱신이다. 기존 PC4대 육안 확인은 완료로
유지한다. 추가 수치 계측 가능한 시간·각 PC 접근이 아직 확인되지 않아 현장 계측은 시작하지 않았다.
서버 설정·설치·재시작·파일 삭제·전체 백업을 이번에 수행하지 않았다.
