# D1 추가 현장 시험 준비

이 문서는 준비부터 실행 인계까지의 순차 기록이다. 실행 완료 결과는 [D1_FIELD_RESULT.md](D1_FIELD_RESULT.md),
후속 운영 후보 승인은 [D1_PROMOTION_DECISION.md](D1_PROMOTION_DECISION.md)를 따른다.
아래 준비 중·미실행·승인 대기 문구는 각 단계 당시 상태로 보존한다.

2026-09-28. 사용자 선택: **120분 관찰 후 원본 복귀**.
준비 승인으로 진행했으며 서버 설치·후보 실행·운영 적용은 아직 수행하지 않았다.
현재 branch `codex/temperature-diagnostics-reason-d1-20260923`, HEAD `830a89c35d50b71dc56e5c2ac9ec9511f1ef6f77` 유지.

## 준비 결과

- 새 읽기 전용 사전점검 묶음: `C:\Users\user\Desktop\SmartFactory\D1_IP1`.
- 개발 QA/전체 변경 diff/새 시험계획: `C:\Users\user\Desktop\SmartFactory\D1_FIELD_PREP_R1`.
- 공유 전송: `Z:\SmartFactory\20260928\send\D1_IP1`의 18개 파일, 329,557,565 bytes 해시 비교 통과.
- 전송 명세 SHA256: `DD91EA26B84A6A9887770DE69A321155253C067D51F38D345CA545ADCD96BD45`.
- helper SHA256: `4A5BBB1E375EF6BCB27AED3C4DC131C972A08ABCDC4158BFFC3287F373FACEFC`.
- 서버 로컬 `C:\Users\user\Desktop\SmartFactory\D1_IP1` 복사 완료. 08:38경 원격 탐색기 속성에서 경로·18개 파일·2개 폴더·329,557,565 bytes를 확인했다. 서버 로컬 SHA 검증은 preflight 실행 전이므로 대기 상태다.

## 최소 변경과 검증

기존 P2_IP1을 수정하지 않고 새 helper/launcher를 만들었다. D1의 후보 commit/NSIS/payload/격리 QA 근거에 새 해시를 결합했다.
설치 파일과 원본 프로세스를 읽기만 하며 로컬 API 표본 3개를 저장한다. 표본의 SPOT stale/오류·PLC 오류·미연결을 진행 중이라는 이유만으로 통과시키지 않는다.
원격 화면의 SPOT STALE/이미지 timeout 표시 후 SPOT OK·영상 갱신도 관찰되었다. 원인이나 지속 장애를 확정하지 않았다.

| 새 검증 | 환경/실행 | 결과 |
| --- | --- | --- |
| helper 경계/새 freshness·오류 판정 | Windows PowerShell 5.1.26100.9549, test-preinstall.ps1 -Bundle D1_IP1 -Evidence D1_FIELD_PREP_R1 | 51 pass, 0 fail, 0 skip; exit 0 |
| 해시 결합 실행기·특수문자 경로·누락/변조·개발 PC 차단 | C:\Python312\python.exe test-launchers.py | 6 pass, 0 fail, 0 skip; exit 0; 거부 사례의 기대 exit 1 유지 |
| 독립 검토 | 읽기 전용 subagent d1_preflight_review | Blocking 없음. 코드·실행 로그·4개 QA proof hash·구 helper 보존 확인 |
| 원본 작업본 보존 | 기존 original-baseline.json의 branch/HEAD/status/41개 파일 hash 재비교 | 일치 |

정확한 명령/환경/종료코드는 `D1_FIELD_PREP_R1\qa-result.json`, 원문은 `boundary.log`, `launchers.log`, `launcher-tests\`에 있다.
프로덕션 소스 변경이 없어 기존 source 1,240/PYZ 24/Sandbox 89개를 재실행하지 않았다. 그 증거는 9월 23일 후보 검증이며 이번 서버 시험 증거가 아니다.

## 범위와 남은 실행

준비의 위험도는 낮다. 새 결과 폴더만 쓰고 운영 설정·데이터·프로세스는 바꾸지 않는다. 대형 생산 데이터 백업·이관 없음.
새 결과 폴더 사용자 접근권한과 부모 ACL 보존은 시험했다. 설정/비밀번호 원문은 회수하지 않는다.
HOLD 시 기존 앱을 그대로 유지하고 표본/실패 단계 기록을 검토한다. 장치 설정·operator/comparator 검증값을 변경하지 않는다.

서버의 새 사전점검 결과를 받은 뒤 PID/시작시각/설정에 결합한 실제 120분 시험 도우미와 복귀 절차를 완성하고 격리 검증한다.
실제 시험은 정상 종료·전체 소유 worker/프로세스/포트 종료를 확인한 다음 설치한다. 미종료나 설치 실패 시 강제 종료·재설치로 밀어붙이지 않는다.
검증된 원본 d7a1b20 NSIS로 복귀하며 현재 metadata를 보존/확인한다. fact 54↔55 및 D1 evidence 의미 전환은 기존 파일 보존 검증 대상이다.
자정·실제 OS 시계 사건·실장비 정체·자연 over-range는 120분만으로 보장되지 않으며 미발생은 미관찰로 남긴다. 운영 승격/위험 수용은 별도다.

## 고정 파일

- 후보 NSIS: `7E565DEDB6613BC6E01FE7BD1CD39A15F623096E1D9951E3BB495FAC31D31D55`.
- 복귀 원본 NSIS: `1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F`.
- 원본 build: `d7a1b20f96711fb07fc7add0867e79ee36506fce`.

이 기록은 과거 D1_PROMOTION_DECISION.md의 선택 대기 상태 이후 사용자 선택을 추가한다. 과거 판단·후보/현장 증거는 덮어쓰지 않는다.
새 commit/push/PR/merge는 수행하지 않았다.

## 120분 실행 도우미 초안 추가 준비

`C:\Users\user\Desktop\SmartFactory\D1_N120_PREP_R1`에 기존 P2_N120를 보존한 새 비활성 초안을 만들었다.
초안 SHA256 `DDFF87CD9560A5D5381EBD14A20156C1911943B059EB1D05B2AD60BD1517952B`.
후보 identity·manifest/tree·경로를 변경하고, 이전 서버 receipt/config/values 해시를 UNBOUND로 교체했다.
`-Execute`도 초기화·I/O 전에 무조건 거부한다. launcher와 실제 서버 실행 묶음은 생성하지 않았다.

`python test-draft.py` exit 0: 경계 41개와 추가 7개, 총 **48 pass / 0 fail / 0 skip**.
AST의 79개 함수 중 77개 본문 동일. 나머지 두 함수는 결과 폴더 접두사와 새 payload 검증 상수 변경뿐이다.
기존 종료·복귀·metadata/provenance gate 및 모든 timeout/관찰 예산은 유지한다. 읽기 전용 독립 검토 결과 Blocking 없음.
이는 최종 helper 전체 workflow QA 또는 현장 120분 결과가 아니다. 새 D1_IP1 서버 receipt를 결합한 후 전체 격리 실행 검증이 필요하다.
자세한 변경 diff/명령/원문/미검증은 위 폴더의 DRAFT_RESULT.md, draft-tests.json, workflow.diff에 있다.

## 2026-09-28 사전점검 회수 및 실행 준비 완료

서버 08:59 기록 READ_ONLY_NSIS_PREINSTALL_PASS / console exit0 확인.
결과26개 회수·해시일치, 검토43 pass. 현재3회 SPOT fresh·PLC snapshot/rows/poll 증가.
원본 누적 과거 오류/복구 이력과 unavailable telemetry는 그대로 보존했다.
서버 receipt SHA256 `120D561E4E3CA0468770061C544700AFCAEA117ADFE03F3911185B0A832490FF`.

새 helper SHA256 `602B0F53A5BBC99D3672C7882E0C3BC1E409310CF96C97B6D70A1DE31CA41E3B`. 실제receipt/config/values로만 binding했다.
경계41·launcher5·actual offline NSIS workflow/CSV검토115 pass,0fail/skip.
후보 정상종료9단계·54↔55 archive보존·원본 재설치/수집·QA정상종료·testport0 확인.
QA는 observation clock96배로 실제관찰약79.42초이며 실제120분현장시험이 아니다.
독립정적검토 blocking없음; 실행결과 자체검토. 기존제품소스·QA/현장기록 보존.

서버 최종 `C:\Users\user\Desktop\SmartFactory\D1_N120` 폴더 복사확인. 공유전송·서버속성·파일존재 증거 보존.
**실제 서버 설치/후보시작/120분관찰은 아직 미실행·실행승인 대기**.
기간/세대gate 불일치 시 새점검필요. 준비완료와 운영승격은 다르다.
상세 `artifacts/temperature-diagnostics-reason-d1/n120-ready-20260928-r1/prep/RESULT.md`.
개발원문 `C:\Users\user\Desktop\SmartFactory\D1_N120_PREP_R1`.

## 2026-09-28 서버 실행 승인

사용자 “승인”으로 준비된 D1 후보 설치·실제120분 관찰·정상 종료·원본복귀 실행을 승인했다.
09:45KST 사전점검은24시간내이며 helper/launcher pin 일치. 서버 UI수집 진행과 실행파일 존재를 확인했다.
실제 PID/시작시각·설정·입력SHA는 helper가 원본종료 전에 다시 확인한다. 화면만으로 재검증 완료를 주장하지 않는다.
실행 파일은 서버탐색기에 선택해 두었고 사용자 실행 대기이다. 설치/관찰이 시작됐다고 기록하지 않았다.
서버 실행 승인과 운영승격·미관찰위험수용은 별개다. 봉인된 이전준비자료의 미승인 상태는 당시 기록으로 보존한다.
승인/인계 기록: C:\Users\user\Desktop\SmartFactory\D1_N120_EXEC_R1\approval-and-handoff.json.

## 2026-09-28 실제 실행 완료와 결과 회수

사용자 실행 완료 후 서버 콘솔 `INSTALL TRIAL EXIT 0`과 실제 7,201.5초 관찰·원본 복귀 receipt를 확인했다.
서버 결과 `C:\Users\user\Desktop\SmartFactory\D1N120-07e8a86b`의 receipt/shutdown과 선택한 후보 원문을
`Z:\SmartFactory\20260928\return` 아래에서 개발 PC `D1_N120_REVIEW_R1`으로 회수했다.
회수 원문 해시·종료·복귀 검토 41 pass, 수집 저하 없음 조건 1 fail을 그대로 보존했다.
추가로 종료 전 약22분의 이미지 쓰기 공백을 확인했다. 설치 workflow PASS를 전체 무오류로 확대하지 않는다.
최종 원문 검증·미관찰 항목·콘솔 인계 상태는 새 [D1_FIELD_RESULT.md](D1_FIELD_RESULT.md)에 기록한다.
기존 준비/승인 대기 문단은 당시 기록으로 보존하며, 운영 승격·위험 수용·push/PR/merge는 수행하지 않았다.
