# 브라우저 추가 계측 OFF/ON 비교

2026-10-13. 같은 후보 코드·입력·화면 조건에서 추가 브라우저 계측을 끈 경우와
켠 경우의 수집 및 독립 검산을 완료했다. 유효 실행은 `r3/off`와 `r4/on`이며
각 producer와 두 review, 조건 대조 `verify-pair` 모두 actual exit 0이다.
전체 R2 및 정식 출시는 **HOLD**, `full_data_gate=NOT_EVALUATED`다.

## 범위와 조건

사용자가 Playwright/CDP 자동시험과 전면 표시 시간을 승인했다. 포커스 이탈 뒤
새 14분 전면 유지 가능 여부도 확인받았다. 새 AppData·프로파일, loopback CSV/SPOT
fixture를 사용했고 운영 서버·장비·설치본은 변경하지 않았다.

- clean 후보 `4cc7393e1bafbf90a329726aed9470fe0daacb21`의 backend와 frontend/dist,
  해당 release-locked Python 환경, Chromium `148.0.7778.96`이다.
  Chromium SHA256: `290fa7018fda22c52ada5eddb0113baf3ebc41fd0fde6085eddb19793606c635`.
- 초기 fact 2,124,377,355바이트·4,145,408행,
  SHA256 `0a1b156c97dc93f7ba2c7a0d70f121803d3e96ddfb771ea9a38457f79a280741`.
  CSV 340,304,366바이트,
  SHA256 `d8f7b769dd57c95d7d730df342a59b9b4175a964cca74aba92c0802b6b0c0f69`.
  원본과 새 비압축 사본의 hash, runtime·환경·Chromium 인자를 대조했다.
- 각 준비 운전 120초와 관측 300초, 5초 간격 85표본 중 관측 61표본이다.
  실제 관측 길이는 OFF 299.9958366초 / ON 300.0038064초다.
  backend·collector 각각 중복 제거 60표본, 296.4542초 / 296.5228초다.
- OFF는 시작 전 CDP 연결을 끊고 종료 후에만 다시 연결했다. 85회 TCP 조사에서
  debugger 연결 0개, ON은 85회 모두 1개였다. OFF의 추가 vitals 객체는 없고
  ON에서는 실제 LCP/CLS 결과와 이미지 이벤트가 누적됐다.
- 유효 측정 구간의 blur/hidden 이벤트는 없었다. 실제 시작·종료 창 상태와
  ON의 15초 간격 화면 상태를 확인했다. viewport 1284×749, DPR1,
  focus/visibility emulation 및 강제 GC는 사용하지 않았다.

양쪽 모두 외부 HTTP·process·backend 지표 수집과 수동적 visibility/focus 이벤트
기록은 남아 있다. 따라서 **추가 브라우저 계측**의 비교이며 관측 부하가 전혀 없는
상태와의 비교가 아니다. OFF에서는 LCP·CLS 및 브라우저 내부 요청 시간을 측정하지 않는다.

## 응답과 화면

계획된 외부 요청은 각 470개, 총 **940개 모두 성공**했다. 원시 본문의 크기·SHA256,
JSON/JPEG decode와 요청 순서·비중첩을 검산했다. 첫 요청과 시작 구간도 보존했다.

| 지표 | OFF | ON |
| --- | ---: | ---: |
| `/health` 전체 수 | 212 | 212 |
| `/health` 첫 요청 ms | 27.2052 | 12.0903 |
| `/health` 전체 최대 ms | 76.4105 | 34.3503 |
| `/health` 전체 p95 ms | 20.4809 | 23.2702 |
| `/health` 관측 구간 평균 ms | 5.695829 | 6.711062 |
| `/api/data` 관측 구간 평균 ms | 4.504570 | 7.009142 |
| 이미지 관측 구간 평균 ms | 6.208339 | 8.463800 |

health 200ms·data 500ms 상한 초과는 0이다. OFF 시작 구간의 두 번째 health 요청
76.4105ms는 **50ms 경고 초과 1건**으로 보존한다. data100ms·이미지500ms 경고 초과는 0이다.
이미지에는 임의 실패 상한을 추가하지 않았다. ON 브라우저 자체 health 211개도
모두200, 최대23.801ms였다. ON의 LCP1964ms·CLS0.0022488658은 목표 이내다.

ON의 준비 이전 `/api/layout` 404 두 건은 별도 보존했다. 격리 환경에 저장된 layout이
없을 때의 응답 경로를 `backend/app.py:2933`에서 확인했다. 이를 삭제하거나 모든
브라우저 요청이200이었다고 보고하지 않는다.

## 자원 차이와 해석

| 프로세스 그룹 | OFF 평균 RSS MiB | ON 평균 RSS MiB | OFF 평균 CPU % | ON 평균 CPU % |
| --- | ---: | ---: | ---: | ---: |
| Backend | 2327.157 | 2326.929 | 0.5000 | 0.5325 |
| Chromium | 633.992 | 713.002 | 8.1821 | 8.9022 |
| 계측용 Node | 91.864 | 153.885 | 0.0234 | 0.3129 |

CPU는 논리12개 기준 전체 머신 용량 비율이다. 합계 평균은 8.705566%→9.747582%,
관측 차이 +1.042016%p다. RSS 합계 평균 차이는 +140.8025MiB이며, Chromium 약79MiB와
Node 약62MiB가 대부분이다. 앞/뒤20% 평균 RSS 합계 증가량은 OFF 약46.989MiB,
ON 약118.717MiB였다. 메모리 안정성 PASS나 제품 누수의 인과 증거로 해석하지 않는다.
RSS 합계는 공유 페이지를 중복 계산할 수 있다.

평균 process read는 1,158,913.90/1,174,897.32B/s, write는
1,367,955.02/1,380,881.64B/s다. 이는 물리 디스크 사용량이 아니다.
관측 health 평균 차이 +1.015233ms, data +2.504572ms, 이미지 +2.255461ms도
단일 OFF→ON 순차 비교의 관측값이다. 준비 검사 보완으로 측정 구간 사이196.358초
간격이 있었다. 실행 순서·호스트 부하·캐시 효과를 분리하거나 일반적인 인과 효과로 확정하지 않는다.

Chromium native stderr의 ERROR 기록도 OFF6/ON10건 보존했다. 실행 파일 접근 오류,
network service 재시작, USB property 오류, GCM registration 오류, on-device model
disconnect가 포함된다. 두 실행의 network 재시작은 화면 준비 전이었고 model service
disconnect는 측정 구간에 있었다. GCM 기록 수는 서로 다르다. **브라우저 환경 무오류를
확인한 시험이 아니며**, 이 백그라운드 활동의 자원 영향은 미확정이다. 관측 자원 차이를
계측만의 인과 효과로 귀속하지 않는다. ACL·sandbox·보안 설정은 변경하지 않았다.
추가 로그 검산은 `Z:/SmartFactory/20261013/records/PDCA_BROWSER_OVERHEAD_c8720a5e_native_logs`의
별도3파일로 보존했고 기존 선택 snapshot manifest는 변경하지 않았다.

## 데이터와 정상 종료

OFF/ON의 새 CSV 1,967/1,941행과 이미지390/388개를 확인했다. CSV 순서·세대 식별값,
metadata/종료 영수증 hash, 새 이미지 전체 바이트·decode, 원래 fact prefix와
추가된 전체 행을 검산했다. 새 이미지 실패·drop은0, queue 표본의 drop도0이었다.
두 backend와 Chromium의 정상 종료는0이며 강제 종료하지 않았다. 수집했던 PID/생성 시각
쌍의 종료와 포트80/8000 반환을 확인했다.

후보1.0.28 installer의 SHA256은 다시 확인한
`8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848`다.
제품 소스·설치본을 변경하거나 rebuild/reinstall/운영 승격하지 않았다.

## 실패 보존과 검증 범위

1. 첫 준비: 도우미의 frontend/dist 복사 누락으로 SPA503/selector timeout.
   controller1, backend0, Chromium0. 준비 운전 이전 실패다.
2. r2 OFF: 계획 HTTP470개는 성공했지만 약155초 뒤 포커스 이탈.
   controller1, backend0, Chromium0. 전면 비교 성공으로 재분류하지 않는다.
   blur만으로 화면이 가려졌다고 단정하지 않는다.
3. r3 ON: 실제 LCP가 생성됐지만 초기화 스크립트의 전역 변수 위치를 잘못 검사해 중단.
   controller1, backend0, Chromium0. r4는 실제 vitals 객체를 검사하도록 그 assertion만
   변경했다. observer 원문·측정 도우미·입력·환경의 동일성을 확인했고 r3 OFF는 재작성하지 않았다.

`final_check.py`의 OFF/ON review 및 조건 대조는 모두 actual0,
추가 프로세스/브라우저 검산 `supplement.py`도0이다. 검산 도우미 Ruff F/E9와
browser `node --check`를 확인했다. 제품 변경이 없어 앞서 통과한 전체 health·빌드를 반복하지 않았다.

초점 변화 없이 완전히 가리는 창의 존재까지 입증하는 시험은 아니다. 격리 Chromium 결과는
실제 장비 프로파일·물리 comparator, 실제 서버 정상 시작3회, 최종 설치본의 현장
15/120분 QA, 전체 성능·데이터 판정 및 과거 timeout/drop의 처리를 대신하지 않는다.

상세 원시 근거와 실행별 경계는
[실행 결과](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_OVERHEAD_20261013_c8720a5e_r4/RESULT.md),
[OFF 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_OVERHEAD_20261013_c8720a5e_r3/off-review.json),
[ON 검산](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_OVERHEAD_20261013_c8720a5e_r4/on-review.json),
[조건 대조](C:/Users/user/Desktop/SmartFactory/PDCA_BROWSER_OVERHEAD_20261013_c8720a5e_r4/pair-verification.json)에 있다.

## 공유 보존

선택한 닫힌 증거 5,187개(manifest 포함), 원본 합계
72,906,997바이트를 `Z:\SmartFactory\20261013\records\PDCA_BROWSER_OVERHEAD_c8720a5e`에 복사하고 전부 hash를 대조했다.
manifest SHA256은 `b42864c1f9bc4ca0cf8d4ef6084a4b43b00d30cf3db8a5eacf2e30693e9e0d0e`다.
반복된 큰 CSV 입력·전체 fact·브라우저 프로파일은 제외하고 준비 기록의 원본 경로와 hash,
fact 전후 hash·보존 prefix·추가 행을 남겼다. 작업 폴더 전체 봉인이나 서버 전달 완료가 아니다.
