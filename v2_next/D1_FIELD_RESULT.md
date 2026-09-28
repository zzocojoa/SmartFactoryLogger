# D1 120분 현장 관찰 결과

2026-09-28. 후보 `830a89c35d50b71dc56e5c2ac9ec9511f1ef6f77`.
사용자가 승인·실행한 새 D1 NSIS 후보의 실제 서버 기록이다.
이전 P2 후보의 120분 결과, 과거 7시간 결과, Sandbox의 가속 관찰과 구분한다.
**판정: 설치·120분 관찰·정상 종료·원본 복귀 완료, 후보 데이터 계약 검사 통과.
복귀 후 작업 정보·콘솔 종료 후 앱 실행 유지·관찰 중 최소화의 사용자 확인까지 완료했다.
이미지 공백은 최소화 시 갱신 중단이라는 기존 동작과 부합한다. 관찰 조건 2개 실패의 원문은 보존하며,
내부 시험과 복귀 결과의 정리를 마친다. 남은 현장 공백의 처리·운영 승격 결정은 별도다.**

## 설치·관찰·복귀

- 서버 결과: `C:\Users\user\Desktop\SmartFactory\D1N120-07e8a86b`.
- 콘솔 `[INSTALL TRIAL EXIT] 0`, 상태 `NSIS_INTERNAL_120_MINUTES_COMPLETED_ORIGINAL_RESTORED`.
- 실제 관찰 7,201.5017985초, 454개 표본. 첫 표본 09:52:56.406, 마지막 11:52:56.821 KST.
- 후보 최종 CSV 31,883행, observation fact 7,281행. CSV finalized, fact drain 완료.
- 원본·후보 정상 종료 exit 0, 강제 종료 없음, 프로세스·포트 해제 확인.
- 후보 종료 9단계 성공, 원본 `d7a1b20f96711fb07fc7add0867e79ee36506fce` 재설치와 3회 수집 진행 확인.
- 후보 payload 1,812개/설치 1,813개 파일 해시 검증, 원본 설치 tree 해시 복귀 확인.
- 기존 CSV와 54↔55열 fact schema archive의 해시 보존 확인. 소형 상태·프로필 보존, 대형 생산 이력 백업 없음.
- 운영 승격 없음. 현재 원본 운영을 유지한다.

## 온도와 D1 관찰

| 원문 항목 | 건수/결과 |
| --- | --- |
| valid | 22,827행 |
| under_range | 8,846행 |
| startup_pending / stale / source_error | 15 / 165 / 30행 |
| Count 0 / 1 / 2 | 3,252 / 1,332 / 887행 |
| SPOT 요청 success / connection_error / timeout | 7,278 / 1 / 2건 |
| fact poll 순번 누락·중복·잘못된 identity | 모두 0 |
| fact 쓰기·링크 실패 / origin decision mismatch | 모두 0 |
| 관찰 writer queue 최대 / pending 최대 | 0 / 1 |

비정상 상태의 Temperature는 모두 빈칸이다. under-range 8,846행 모두 cause `unknown`, confidence 0과
`diagnostics_excluded_fact_only`를 유지한다. 그중 1,903행은 기존 공정 규칙에 따라
`phase_setup_candidate`도 함께 기록한다. 이 공정 주석을 제외 사유 오류로 세지 않는다.
`diagnostics_missing_or_stale`의 잘못된 표시와 non-under-range의 진단 제외 사유가 없음을 확인했다.
rule v6, `async_fact_only`, operator/comparator `verified=false`, readback `not_supported`를 유지한다.
현장에서는 fact_only만 관찰했으며, 다른 네 제외 사유의 증거는 기존 합성 production-path 시험으로 구분한다.

## 실패·공백을 그대로 보존

1. **수집 저하 없음 조건 실패.** 454개 표본 중 1개가 SPOT timeout/stale이다.
   전수 fact에는 11:30:50~11:30:58 KST의 연속 3건 요청 실패가 있다.
   이 세 fact에 연결된 46행은 source_error 30행/stale 16행이며 Temperature는 모두 빈칸이다.
   poll 5967에서 응답 복구(under-range sentinel), 11:31:07.289의 행 26136에서 유효 온도 438.5가 재개됐다.
   다음 관찰 표본 11:31:17도 success/fresh이다. PLC 입력의 실패는 해당 표본에서 확인되지 않았다.
   실제 물리 원인이나 D1이 발생 원인이라는 주장은 하지 않는다.
2. **종료 직전 이미지 기록 조건 실패.** 이미지 최종 manifest의 마지막 쓰기는 11:30:49.173 KST,
   후보 종료 11:52:59.965보다 1,330.792초 앞선다. 세션 이미지 쓰기 5,499건, writer failure/dropped 0.
   이 조건은 `last_write_at`이 종료 10초 이내인지 검사한 것으로, manifest 작성 시각을 뜻하지 않는다.
   종료 시 이미지 3,334,820행/해시 일치는 별도로 확인됐다. 무결성 성공으로 연속 수집을 주장하지 않는다.
   writer failure/dropped 0은 이미지 upstream 요청이 모두 성공했다는 증거가 아니다.
   이번 회수는 이미지 연결 CSV의 검증이며 실제 JPEG 바이트와 당시 화면 상태의 전수 검증은 아니다.
   후보 소스는 창이 hidden일 때 이미지 refresh/retry를 취소하고 visible일 때 재개한다
   (`frontend/src/domains/FacilityData/hooks/useSpotViewModelEffects.ts:83`,
   `backend/FacilityData/drivers/spot_api.py:3227`). 2026-09-29 사용자가 해당 시간대 앱을 최소화했다고 확인했다.
   `main.js:392`의 BrowserWindow는 backgroundThrottling을 끄지 않는다.
   [Electron 공식 visibility 설명](https://www.electronjs.org/docs/latest/api/browser-window#page-visibility)과
   위 코드에 비추어 공백은 최소화 시 이미지 갱신 중단과 부합한다는 해석이다.
   정확한 최소화 시작·종료 시각과 당시 renderer visibility 로그가 없어 전체 공백의 단독 원인까지 입증하지 않는다.
   이 확인을 온도 요청 3건 실패의 원인이나 실제 화면 복원 후 이미지 재개를 검증한 증거로 확대하지 않는다.

두 검사를 삭제하거나 임계값을 완화하지 않는다. 설치 workflow PASS는 이 조건들까지 통과했다는 뜻이 아니다.
이미지 공백은 확인된 사용 조건과 부합하는 관찰 한계로 분류하고, 이 자료만으로 D1 결함·저장 유실로 판정하지 않는다.
이미지 동작 변경은 이번 D1 소스 수정 범위 밖이다. 서버 설정·운영 코드 수정은 하지 않았다.

## 회수와 검증 근거

개발 PC: `C:\Users\user\Desktop\SmartFactory\D1_N120_REVIEW_R1`.
서버→공유→개발 PC 회수는 Codex가 수행했다.

- receipt/shutdown: `Z:\SmartFactory\20260928\return\D1_N120_RESULT_R1`.
- 선택한 CSV·metadata·fact·이미지 manifest: `Z:\SmartFactory\20260928\return\D1_N120_DATA_R1`.
- receipt 원문 5,529개(그중 JSON 2,764개)의 공유/로컬 전체 해시·목록과 JSON SHA sidecar 일치.
- 콘솔 result SHA256: `4E17C59D3F30878EB11BFEA33679C17E98377A994D03F8AFEAEE5FAF96140A02`.
- 닫힌 CSV SHA256: `973128860F885B88FB1781895F4CE2EFBDBBA1714C4CDEA75C63A2D53119A033`.
- metadata SHA256: `EC3CFE482C7BABF74F216E28B8FAD592523569C256350C1112E25A153DC6A8CC`.
- fact SHA256: `4468BC68240BB875AC656FED65449C0849446508F859853FDAD64E086D560BDC`.
- 이미지 종료 prefix SHA256: `36976BE824F00108066B40870F7039A7F4BF8121E4BB148BE9AAFCCBBDD208CC`.

이미지 연결 검증을 위해 append-only CSV 사본에서 종료 행수의 정확한 원문 prefix를 추출했다.
시작 metadata의 prefix 해시와 종료 manifest 해시를 모두 요구했다. 원문 manifest를 다시 만들거나 완화하지 않았다.
복귀 후 원본이 쓴 사본의 tail은 후보 증거에 포함하지 않는다. 이 사본은 검증 자료이며 복귀용 백업이 아니다.
운영 AppData/설치 폴더·ACL·설정은 바꾸지 않았다. `SFLOps`/Z 루트의 새 폴더 사용도 없다.

## 실행 검증

환경: 개발 PC Windows 11 build 26200, CPython 3.12.6 x64.
Python: `C:\Users\user\Desktop\SmartFactory\D1_CANDIDATE_R1\src\v2_next\backend\.venv\Scripts\python.exe`.
검증기 소스는 해당 후보 SHA의 clean clone이다. 아래 스크립트 경로는 회수 폴더 기준이다.

| 명령 | 종료코드 | 결과 |
| --- | --- | --- |
| `python review_receipts.py` | 1 | 41 pass / 1 fail / 0 skip; 수집 저하 없음 조건 실패 원문 보존 |
| `python analyze_events.py` | 0 | 전수 fact 실패 3건·빈칸·복구·이미지 공백 분석; 테스트 건수로 합산하지 않음 |
| `python review_preservation.py` | 0 | 원래 작업본 41개 파일·상태·branch/HEAD 보존 |
| `python review_data.py` | 1 | 22 pass / 1 fail / 0 skip; 종료 직전 이미지 기록 조건 실패 원문 보존 |
| 후보 `scripts/validate_csv_v2_shadow.py` + 실제 CSV/metadata/fact/이미지 종료 prefix/final manifest | 0 | PASS; 실제 전체 명령·cwd·시각은 `data-review.json`/`EXECUTION_JOURNAL.json` |

검증기 실행은 12:54:21.764~13:23:05.177 KST(약28분43초)이다.
`current_server_promotion_profile_required=False`인 내부 관찰 데이터 검사이며, 운영 승격 profile 검증을 주장하지 않는다.
V1 대조와 제공되지 않은 선택적 posthoc fact/linkage 보고서는 검사하지 않았고 로그의 not checked/not available/unknown을 보존했다.

자체 검토이다. 이번 턴은 코드 변경이 없어 기존 1,240개 소스 QA·PYZ 24개·Sandbox 89개 등을 다시 실행한 것으로 세지 않는다.
후보 빌드·서버 helper 준비 QA의 기존 실행 근거는 `D1_CANDIDATE_RESULT.md`, `D1_FIELD_PREPARATION.md`에 그대로 남긴다.

검토 스크립트·원문 로그·주요 receipt·전체 회수 명세·입력 파일 해시는
`artifacts/temperature-diagnostics-reason-d1/field-n120-20260928-r1/`에 보관한다.
`RETRIEVAL_MANIFEST.json`은 전체 receipt/trace 5,529개를, `DATA_INPUT_MANIFEST.json`은 실제 CSV 입력을 식별한다.
전체 원문 receipt와 대형 CSV 사본은 위 개발 PC 회수 폴더에 보존하고, 저장소에는 필요한 검토 증거와 해시를 둔다.

## 남은 인계와 운영 판단

- 콘솔 종료 후 원본 앱 생존: 2026-09-29 사용자 “콘솔 닫았고 앱도 계속 실행중이다.”로 확인 완료.
  앞서 2026-09-28 13:17 KST 화면은 콘솔 종료 전 Running, Count44·Temperature544.1 기록으로 보존한다.
  종료 후 실행 유지는 사용자 회신에 근거하며 별도의 새 PID·수집 진행 검사를 실행한 것으로 세지 않는다.
- 표시 제품 60568·금형 5의 실제 작업 일치: 2026-09-29 사용자 명시 확인 완료. 현장 시험 중 60568/4→빈 metadata→60568/5 기록을 보존했다.
- 11:30~11:53 KST의 창 최소화 여부: 2026-09-29 사용자 “최소화했었다.”로 확인 완료.
  정확한 최소화 지속시간·카메라 화면 이탈 여부까지 확인한 것은 아니다.
- 실제 자정·실제 OS 시계 보정·장비 I/O 미종료·over-range는 이번 주간 관찰로 확인되지 않았다.
- 요청했던 작업 정보·콘솔 종료 후 실행 유지·최소화 상황 확인을 모두 마쳤다.
  남은 현장 공백의 처리·위험 수용·미서명 운영 배포 여부는 별도로 결정해야 한다.

rollback은 이미 원본 NSIS 재설치·동일 설치 tree 검증·수집 재개로 실행됐다. 데이터 이관은 없다.
관측성은 D1의 제외 사유 구분을 확인했고, 장애 시 Temperature blank와 기록 보존을 확인했다.
최소화 상황은 확인됐지만 이미지 연속 수집·전체 공백의 인과와 현장 시험 범위의 한계는 남는다.
따라서 전체 무오류나 운영 승격 승인으로 표현하지 않는다.
이번 검토에서 commit/push/PR/merge·후보 재설치·추가 현장 시험은 수행하지 않는다.

## 2026-09-29 작업 정보 확인

사용자 회신: “제품 60568·금형 5 가 맞다.” 작업 정보 일치 항목을 확인 완료로 갱신했다.
이 회신은 콘솔 종료 후 앱 생존이나 이미지 공백 당시 화면 상태의 확인으로 확대하지 않는다.
2026-09-28의 봉인된 증거·해시·당시 pending 기록은 보존하고 별도 확인 기록을 추가했다.

## 2026-09-29 콘솔 종료 후 실행 확인

사용자 회신: “콘솔 닫았고 앱도 계속 실행중이다.” 콘솔 종료 후 앱 실행 유지 항목을 확인 완료로 갱신했다.
앞선 제품 60568·금형 5 일치 확인과 함께 원본 복귀 후 인계 확인을 마쳤다.
이 회신은 이미지 기록 공백의 원인 확인이나 운영 승격·위험 수용 승인으로 확대하지 않는다.
기존 봉인 자료는 보존하고 `field-n120-20260929-console-confirmation-r1`에 별도 확인 기록을 추가했다.

## 2026-09-29 최소화 확인과 공백 판단

9월 28일 11:30~11:53 사이의 최소화/화면 이탈 여부에 사용자가 “최소화했었다.”라고 답했다.
확인된 최소화 상황과 후보의 hidden 시 이미지 refresh/retry 취소 코드를 함께 근거로,
이미지 공백을 기존 동작과 부합하는 것으로 분류했다. 정확한 시간대별 인과 확정이나 연속 이미지 검증 통과는 아니다.
온도 요청 실패 3건과 빈칸 보호·복구는 별도 사건으로 보존한다.

`field-n120-20260929-visibility-confirmation-r1`에 별도 확인 JSON을 추가하고 개발 PC·공유 records에 같은 해시로 보관했다.
이전 봉인 자료·당시 pending 기록·두 관찰 조건의 실패 결과는 수정하지 않았다.
이번 확인은 문서·증거 갱신이며 테스트 재실행, 코드 수정, 설치·운영 승격 또는 위험 수용 승인이 아니다.

## 2026-09-29 후속 운영 후보 승인

이후 사용자가 “잔여 한계를 수용해 미서명 운영 후보로 승인”이라고 명시했다.
이 보고서의 현장 미관찰 항목·두 관찰 예외와 미서명 상태를 보존한 채, 고정된 D1 후보의 운영 여부 결정을 완료했다.
상세 승인 대상과 권한 범위는 `D1_PROMOTION_DECISION.md`의 최종 승인 기록을 따른다.
서버 적용을 실행한 것은 아니며, 원본 복귀와 기존 pass/fail·해시 기록은 그대로 유지한다.
