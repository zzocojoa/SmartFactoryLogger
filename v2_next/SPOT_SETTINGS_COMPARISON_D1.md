# SPOT 현재 설정 대조와 후보 준비

이 문서는 9월 23일 장비 조회·후보 준비 시점의 기록이다. 후속 [후보 검증](D1_CANDIDATE_RESULT.md),
[현장 결과](D1_FIELD_RESULT.md), [최종 운영 후보 승인](D1_PROMOTION_DECISION.md)은 별도 기록으로 구분한다.
operator/comparator 검증값과 모델 동등성의 미검증 상태는 후속 승인으로 변경하지 않았다.

2026-09-23 16:07–16:12 KST. Chrome 원격 데스크톱의 서버 Chrome을 통해 장비 웹 UI를
직접 읽었다. **화면에서 대조 가능한 설정 14개는 승인 fingerprint 재구성 자료와 일치한다.**
모델 표기 동일성·비교기 적용 조건은 미검증이며 operator/comparator를 true로 변경하지 않았다.

## 확인 방식과 범위

기존 원격 연결을 사용해 장비의 Settings, I/O, Focus, Alarms, Time Functions, Info 화면을
확인했다. 값을 입력하거나 체크박스·드롭다운을 변경하지 않았다. 알람 자극·임계값 변경·
장비 재부팅·펌웨어 갱신·앱 종료는 수행하지 않았다. 조회용 서버 Chrome을 닫고 수집 앱으로
돌아왔으며 Running, 숫자 온도, 조회 전후 Count 증가를 확인했다. 이는 UI 관찰이며 새 CSV
무결성 시험이나 실행파일 식별 시험은 아니다.

스크린샷은 이 Codex 대화의 도구 기록에 남아 있다. 원격 canvas의 화면을 직접 읽어
`artifacts/temperature-diagnostics-reason-d1/spot-readonly-20260923/live-settings-comparison.json`
에 전사했다. 자동 장비 API readback 또는 export로 표현하지 않는다. 운영 주소·MAC·일련번호는
이 문서와 전사 파일에 복사하지 않았다.

## 실제 설정과 승인 자료

승인 기준은 기존 원본 캡처의 fingerprint payload 중 build commit만 v1.0.20으로 바꿨을 때
저장된 승인 hash를 정확히 재현한 값이다. 승인 당시의 독립적인 장비 readback 원문은 아니다.

| fingerprint 입력 | 재구성 승인값 | 현재 장비 UI | 결과 |
| --- | --- | --- | --- |
| App mode | App1: AL E | App1: AL E | 일치 |
| Range min | 200°C | 200°C | 일치 |
| Range max | 900°C | 900°C | 일치 |
| Analog 4mA | 200°C | 200°C | 일치 |
| Analog 20mA | 800°C | 800°C | 일치 |
| Low Signal enabled | OFF | 체크 안 됨 | 일치 |
| Low Signal threshold | 2.0% | 2% | 일치 |
| Peak Picker | OFF | 체크 안 됨 | 일치 |
| Limiter | OFF | 체크 안 됨 | 일치 |
| Averager | OFF | 체크 안 됨 | 일치 |
| ModeMaster | OFF | 체크 안 됨 | 일치 |
| Ratio Raw | OFF | 체크 안 됨 | 일치 |
| Window Obscuration | 12.0% | 12.0% | 일치 |
| Focus | 6071mm | Set/Current Focus 모두 6071mm | 일치 |
| Model text | SPOT+ AL | AL Spot | 표기 다름; 동일 모델/별칭 여부 미검증 |
| Low Signal comparator | lt (`<`) | 화면에 방향/경계 정의 없음 | 미검증 |

추가로 Info의 firmware `V: 40.38`, Output Time `100ms`, Time Functions의 Averager 2 OFF를
읽었다. 이 추가 표시를 원래 14개 일치 수에 합산하지 않았다. 모델 표기는 장비의 현재 화면으로
확인했으나 제조사 Part No/설명서 적용성까지 증명하지 않는다. 기존 앱 문자열을 새 장비명으로
임의 수정하지 않는다. Low Signal OFF와 comparator 미검증 상태에서 수치 원인 추론을 허용하지 않는다.

## 불일치 원인과 남은 한계

현재 생산 함수로 이전 캡처와 최근 120분 후보 metadata의 hash를 재계산한 결과는 그대로 유효하다.
저장된 승인 fingerprint는 build `cd8cfa649203494cf087206cf656dc2197107ea1`에 결합돼 있고,
최근 후보 build `d254871f89c98154b4e32879e29601df78f7e159`와의 22개 payload 입력 중
다른 값은 build commit 하나다. 나머지 21개는 같다. 따라서 **시험 기록의 fingerprint_mismatch는
build identity 차이만으로 재현된다.** 이번 14개 실제 설정 대조에서도 해당 설정의 차이는 없었다.

단, 이 결론은 장비 전체 설정 승인과 다르다. 모델 문자열 차이, 비교 방향의 펌웨어 적용성,
새 operator 확인 및 실행 중 앱의 현재 config/EXE provenance 재수집은 미완료다. 기존
`device_config_readback_status=not_supported`를 UI 전사만으로 다른 값으로 바꾸지 않는다.
이 항목을 해소하려고 장비 설정이나 fingerprint를 맞춰 쓰지 않는다.

## 새 후보 검증의 구체적 범위

D1은 로컬 diff만 있고 새 commit/EXE는 없다. 다음 승인 대상은 아래 개발 PC 작업이다.
서버 설치·전환·운영 승격은 이 범위에 포함하지 않는다.

1. 현재 D1 브랜치의 검토된 코드·시험·문서만 로컬 commit한다. private artifacts와 원래 작업공간 변경은 포함하지 않는다.
2. 해당 commit에서 깨끗한 별도 빌드 디렉터리를 만들고 `UNSIGNED_INTERNAL` 후보를 만든다.
   저장소 `scripts/deploy.ps1`와 Windows artifact workflow의 source identity/bundle 검증을 기준으로 한다.
   기존 사용자 dist·이전 후보·설치 파일을 덮어쓰지 않는다.
3. commit, backend provenance/bundle manifest, Electron EXE, NSIS installer의 SHA256을 함께 고정한다.
   서로 다른 commit이 섞이거나 검증값이 비어 있으면 진행하지 않는다.
4. 새 commit에 대한 backend·frontend·Electron 및 계약 QA를 실행하고, 격리된 MOCK/loopback 경로로
   5개 D1 제외 사유·Temperature blank·cause 유지·v5→v6 파일 분리·재시작·정상 drain/closeout을 확인한다.
5. 개발 PC Windows Sandbox에서 후보 설치·실행·원본 복귀를 검증한다. 운영 AppData와 실제 장비는
   사용하지 않는다. NSIS 설치 경로/등록/payload와 이전 CSV 바이트 보존을 확인한다.
6. 모든 결과를 **새 commit/EXE**에 결합한 뒤 서버 현장 검증·운영 적용 여부 판단 자료를 제출한다.
   예전 120분 결과를 새 후보의 시험으로 표시하지 않는다.

복귀 대상은 이미 검증된 원본 build `d7a1b20f96711fb07fc7add0867e79ee36506fce`다.
원본 NSIS 기록 SHA256은 `1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F`이며,
실제 사용 직전에 파일과 payload를 다시 검증한다. 정상 종료가 확인되지 않으면 HOLD하고
강제 종료나 자동 재설치로 진행하지 않는다. rollback 시 다른 rule의 wide CSV에 구버전 writer가
append하지 않도록 새 수집 파일을 사용한다.

## 운영 판단에 남길 항목

| 항목 | 현재 근거 | 새 후보 단계의 처리 |
| --- | --- | --- |
| D1 행 evidence·값/상태/cause 불변 | 로컬 836개 및 5,200건 비교 | 새 바이너리에서 재검증 |
| 모델 표기·comparator | 현재 UI 대조와 미검증 gate | gate 유지; 검증 완료로 승격하지 않음 |
| 자정 전환 | 코드 회귀, 새 후보 현장 미실행 | 추가 시험 또는 명시적인 위험 수용 |
| 실제 OS clock 보정 | 합성 clock 회귀, 새 후보 실환경 미실행 | 격리 시험/별도 승인 범위; 운영 OS 조정 금지 |
| 미종료·재시작 차단 | production lifecycle 합성 시험 | 새 패키지의 모의 정체·closeout 검증 |
| over-range | 합성 안전 회귀, 새 후보 자연 현장 미실행 | 모의 패키지 시험과 현장 공백을 구분 |
| 서명·운영 설치 | 기존 미서명 내부 경로 승인만 있음 | 정식 운영 승격 별도 결정 |

모델/비교기 미확인을 D1 코드 검증이나 미서명 내부 후보 준비의 새로운 선행 조건으로 만들지 않는다.
미검증 gate를 유지한 채 해당 후보 시험은 가능하다. 운영 적용과 미검증 항목의 위험 수용은 별도다.

## 현재 승인 경계

사용자 목표의 “로컬 수정·테스트·결과 보고까지만”과 “commit·push·PR 생성·merge·설치·배포는
별도 승인 없이 수행하지 마라”에 따라 지금까지 로컬 commit·후보 빌드/설치·push·PR·merge·서버 전환을
수행하지 않았다. 위 개발 PC의 로컬 commit·미서명 후보·격리 설치/실행 검증을 다음 승인 대상으로 준비했다.

위험은 아직 실현되지 않은 패키지/설치 호환성에 있다. 현재 단계는 읽기 전용 장비 조회와 문서 추가로,
데이터 이관·운영 설정 변경·서버 중단이 없다. 관측성은 실제 설정 일치/표기 차이/미검증을 분리해 개선했다.

## 후속 승인 기록

2026-09-23 사용자가 “로컬 커밋·후보 빌드·격리 검증 승인”을 선택했다. 위 1–5의 로컬 commit,
개발 PC 미서명 후보 및 Windows Sandbox 설치·실행·원본 복귀 검증을 진행할 수 있다.
push·PR·merge·서버 설치·운영 적용은 이 승인에 포함하지 않는다. 이 승인 기록만으로 후보 시험이
통과하거나 미검증 설정이 승인된 것으로 처리하지 않는다.
