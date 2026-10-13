# 후속 PDCA 현재 완료 범위와 남은 조건

2026-10-13. 완료된 실행의 최종 영수증 7개를 현재 PDCA 요약과 대조했다.
PLC 작업 `78990`과 서버 이미지 작업 `88251`은 이미 끝났다. NAS ZIP 원본 최종
재해시도 완료됐다. 이 작업들을 다시 실행하거나 “진행 중”으로 취급하지 않는다.
이번 작업은 기록 정합성 확인이며 제품·설치본·서버 데이터 검사를 새로 실행한 것이 아니다.

현재 후보는 **1.0.28**, clean build
`4cc7393e1bafbf90a329726aed9470fe0daacb21`, installer SHA256
`8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848`다.
사용자의 미서명 내부 운영 정책을 유지한다. 서명 인증서·담당자 확인은 남은 작업이 아니다.
현재 운영본과 다음 롤백 기준은 여전히 `541d701d… / 08C061EE…`다.

## 완료된 범위

| 범위 | 최종 근거와 판정 | 확대 해석하지 않는 범위 |
| --- | --- | --- |
| 서버 cold 사본 | 314,675파일·680 추가 스트림, 닫힌 사본 검증 완료 | 이후 생긴 운영 데이터·최종 후보 종료 delta |
| 서버 이미지 | 312,985파일 / 3,053,203,168바이트의 hash·전체 decode 완료, exit 0 | 과거 누락 3,830,540참조·미참조 16파일의 원인/처리 |
| PLC 사본 | 127,158파일, 원본 최종 hash·목록·사본 대조 완료, producer/review exit 0 | NAS 전체의 원자적 snapshot |
| PLC 값 | 데이터 15,329,516행·숫자 107,306,612개 문법 검사 완료 | 시각 역전·동일 행의 원인, 생산 의미·전체 연속성 |
| NAS ZIP | 439개 원본/사본 최종 hash 확인, copy exit 0; 내용 검사 exit 1 | BadZipFile 2개·역사 자료의 의미/처리 미해결 |
| NAS 선택 이미지 | 20,157개 중 decode 20,154통과·0바이트 3실패; 복구 후보 7개 별도 보존 | 원래 위치 복원·과거 누락 종결 |
| 같은 브라우저 탭 비교 | 1개/3개 각각 준비 120초+관측 300초 완료, 계획 HTTP 실패 0 | 3화면 동시 전면 표시·계측 OFF·최종 설치본 현장 성능 |
| 추가 backend 계측 비교 | OFF→ON→ON→OFF, 계획 요청 2,920개 확인, exit 0 | browser/CDP/web-vitals OFF·제품 귀속 물리 디스크 사용량 |
| 후보 1.0.28 | health/build/payload 및 격리 NSIS 설치·복구 완료; 후보 정상 종료 2회 새 이미지 502=0 | 실제 장비·현장 QA·운영 승격 |
| 추가 SpotViewer DB | 사본 874,827,776바이트·17,966,329행, SQLite integrity_check ok·전체 집계 정산 exit0 | 서버 원본 해시/원자성·데이터 의미·모델/승인 프로파일 |

후보 전체 health는 backend 919통과/비공개 F01 fixture 1생략, Electron 100,
frontend Vitest 437이며 actual exit 0이다. 격리 NSIS 누적 오류 review는
114/118·exit 1을 보존한다. 기존541d의 종료502 2건과 후보 두 실행의 신규 오류0을
분리한 후속 검산을 전체 오류 없음으로 바꾸지 않는다.

세부 근거:
[서버 사본](production-release-risk-validation-stream-copy-20261012.report.md),
[이미지](production-release-risk-validation-image-recovery-20261013.report.md),
[PLC](production-release-risk-validation-plc-csv-20261013.report.md),
[성능](production-release-risk-validation-runtime-performance-20261013.report.md),
[최종 후보](production-release-risk-validation-shutdown-image-20261013.report.md).

## 최신 서버 관찰

Chrome 원격 데스크톱 `DESKTOP-Extrusion` 연결 화면의 14:42/14:44 KST 표본에서
앱은 Running, EX/LS/SPOT/Temp/Comm OK와 작업 정보 OK였다. 제품 `60322`·금형 `10`,
최근 적용 시각 `2026-10-13 13:39:05 KST`가 표시됐고 두 화면 사이 생산 값이 변했다.
이는 화면 관찰값이며 사용자에게 새로 확인받은 생산 지시나 build/logger 동일성 검증이 아니다.
Codex는 작업 정보·설정·앱 실행 상태를 변경하지 않았다.
앞선 `60332/6`·`60192/17` 기록은 당시 증거로 보존한다.
이 두 표본으로 지속 무오류 운전·과거 오류 해소를 주장하지 않는다.

후속 [receipt 검사 보완](production-release-risk-validation-receipt-test-20261013.report.md)에서 로컬 검사 시간 의존성을 재현·수정했다. 아래 과거 서버 원인·호스트 하위 원인 미확정과 현장 조건은 유지한다.

후속 [브라우저 추가 계측 비교](production-release-risk-validation-browser-overhead-20261013.report.md)에서 유효 OFF/ON 전면 시험과 검산을 완료했다. 계획 HTTP940개 성공, 시작50ms 경고1건·준비/표시 조건 실패3건은 보존했다. 공통 probe·순차 실행 한계와 메모리 상향 추세가 있어 전체 성능 PASS로 확대하지 않는다.

16:22/16:30 KST [서버 직접 재확인](production-release-risk-validation-field-entry-20261013.report.md)에서
같은 운영 build541d·logger `e9a785c0…`·SPOT `efca4313…`의 image drop이173건이었다.
같은 세대의03:58 기록은0건이며, 기존15/다른 세대44와 별도 사건이다.
마지막 두 표본 사이469.566390초 동안 CSV 카운터+2,082·image written+410,
drop 증가0이었다. 원인·프레임/행 식별·복구 가능성은 미확정이다.
프로파일 fingerprint mismatch와 effective operator/comparator false도 유지된다.

후속 [승인 자료 탐색](production-release-risk-validation-profile-search-20261013.report.md)에서
기존 metadata 411,798행의 지정 파일명 검색과 제조사 폴더를 확인했다.
새 SpotViewer DB를 발견했으나 설정/시스템 정보는 비어 있었다. Temperature의 NULL
1,689,070행은 의미·원인 미확정으로 보존한다. 제조사 공식 색인 설명의 Name은
사용자 지정 명칭이며, `AL Spot` 문구만으로 실제 모델을 확정하지 않는다.
이 추가 DB는 기존 CSV/이미지 snapshot과 별도 범위이며 전체 gate 통과가 아니다.

17:27–17:45 KST [장비 직접 조회](production-release-risk-validation-device-profile-20261013.report.md)로
장비 정보 응답 `SPOT+ AL`과 설정 HTML의 `7 = App1: AL E` 대응을 확인했다.
모델 미정 상태를 보완했으며 현재 관찰 설정표를 USER_SELF 승인 대상으로 준비했다.
이 확인으로 앱의 readback 구현이나 fingerprint_mismatch, 물리 경계 미검증이 해소되지는 않는다.

## 남은 조건과 실행 순서

| 항목 | 남은 조건 | 다음 증거 |
| --- | --- | --- |
| R1 | 원래 timeout/223ms 사건의 인과, 격리 검사에서 간헐적으로 발생한 receipt timeout 원인 미확정 | 원래 시점의 근거 또는 재현 순간 상태와 수정 전후 검증. 반복 통과만으로 종결하지 않음 |
| R2 | 실제 서버 정상 시작3회, 최종 설치본 현장15분/120분·물리 디스크·전체 성능 계약 | 첫 요청을 포함한 현장 원시값·오류·종료 증거. 브라우저 추가 계측 비교는 아래 후속 보고서에서 완료 |
| R3 | 장비 직접 응답 SPOT+ AL 및 모드7=App1: AL E 확인; 관찰 프로파일의 USER_SELF 승인·물리 경계 comparator·최종 fingerprint/attestation 미완료 | 관찰 설정표의 운영 기준 승인, 물리 경계 시험, 같은 build/세대의 시작·종료 대조 |
| R4 | 과거 누락·미참조·손상·시간 순서의 원인/영향/처리, 최종 현장 종료 delta 미완료 | 항목별 원시 증거와 데이터 책임자 처리 기록, 새 후보 데이터 전체 검증 |
| R5 | 이전4c drop15·다른541d 세대 drop44·현재e9a785c0/efca4313 세대 drop173의 원인/처리 미확정 | 별도 세대별 수량·영향·복구 가능성·처리 결정; 저장실패16과 합산 금지 |
| R6 | 최종 installer의 현장 설정·one-command QA·정상 종료·승격 미실행 | 정확한 동일 installer의 FINAL PASS·현장 결과·적용 확인 후 기준 갱신 |

실행 체크리스트:

1. 완료된 계측·receipt 보완의 범위와 한계를 유지하고 남은 현장·과거 사건 조건을 조사한다. 완료된 대규모 사본·이미지 검사와
   기존 동일 후보 NSIS matrix를 새 실패나 변경 없이 반복하지 않는다.
2. 장비 승인 근거와 과거 finding 처리의 미확인을 명시한다. 담당자 USER_SELF,
   유지보수 언제든 가능, 미서명 운영이라는 기존 답변을 다시 요구하지 않는다.
   모델은 직접 응답으로 보완됐으며 과거 “미정” 답변은 당시 기록으로 남긴다.
   화면값이나 포괄 승인을 기술 검증 PASS로 바꾸지 않는다.
3. [출시 계획](../01-plan/features/production-release-risk-validation-codex-production-release-risk-validation-20261010.plan.md)의
   적용 전 조건을 충족한 동일 후보에 현장 검증을 연결한다. 예외는 해당 범위의 실제 승인
   기록이 필요하며 이 문서는 예외 승인이나 설치 지시가 아니다.
4. 현장 실패 시 원본과 결과를 보존하고 다음 승격을 중단한다. 자동 복구·강제 종료를
   추가하지 않는다. 실제 승격·적용 확인 뒤에만 운영/다음 롤백 기준을 갱신한다.

R1–R6 정식 출시 **HOLD**, `full_data_gate=NOT_EVALUATED`, 전체 목표 active다.
완료된 하위 검사와 정식 출시 미완료를 함께 유지한다.

## 이번 정합성 확인

[검산 기록](C:/Users/user/Desktop/SmartFactory/PDCA_GATE_REVIEW_20261013_a8079c24/reconciliation.json)에
기존 최종 영수증 7개의 경로·크기·SHA256과 검사 범위를 고정했다. 도우미 Ruff F 및
실제 정합성 검산 exit 0. R2/R4 현재 요약과 새 검토 기록, 갱신 시각만 바꾸고 다른
PDCA 상태·모든 과거 단계 기록의 동일성을 확인했다. 제품 변경이 없어 health를 반복하지 않았다.
새 원본 전수 재해시, 새 성능 시험, 서버 설치·승격을 수행했다는 뜻은 아니다.
