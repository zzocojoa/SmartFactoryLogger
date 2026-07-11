# Gap Analysis: spot-camera-rest-api-conformance

> Date: 2026-07-11 | Design: `docs/02-design/features/spot-camera-rest-api-conformance.design.md`

---

## Match Rate: 96%

## Summary

설계 항목 25개 중 개발 PC에서 검증 가능한 24개를 구현했다. 공식 SPOT REST API의
`GET /image.jpg` 단일 경로, 완료 기반 UI polling, Dashboard/설정 화면 공통 transport에
더해, 이미지·온도·진단·focus·actuator의 장비 전체 요청을 하나의 fair async lock으로
직렬화했다.

서버 실장비에서 direct `/image.jpg`는 60초 동안 2,014/2,014 성공했으나 기존 앱은 같은
기간에 `502 upstream-timeout` 1건을 기록했다. 동시에 diagnostics에서 여러 output timeout이
관찰되어, 장비 요청 경합을 원인으로 판단했다. 이번 iteration은 HTTP timeout을 늘리거나 UI
간격을 임의 조정하지 않고 장비 단위 동시 요청 수를 1로 제한한다.

남은 항목은 새 clean package를 서버 컴퓨터에 설치한 뒤 최소 15분 동안 실장비로 검증하는
운영 AC 하나다. 이 검증 전에는 PDCA를 완료 처리하지 않는다.

첫 15분 서버 검증에서 image 오류 0건, Temperature poll 실패 0건, CSV 3,086행
추가를 확인했지만 모든 신규 행이 `async_partial`이었다. Observation fact 897건을
분석한 결과 유일한 실패는 `appnumber=http_error`였으며, 장비 직접 검증으로 현재
`/output?p=appnumber` 구현이 HTTP 400을 반환하고 공식 `/control?p=appnumber`는
HTTP 200과 값 `7`을 반환함을 확인했다. 해당 PDF 불일치를 수정했으며 새 package와
서버 재검증은 아직 남아 있다.

## Implemented Items

- [x] SPOT image upstream URL을 `http://{SPOT_IP}/image.jpg`로 고정했다.
- [x] 비공식 image/live-image URL override와 legacy 설정 선택 경로를 제거했다.
- [x] JPEG signature를 검증하고 HTML·빈 body·비 JPEG payload를 거부한다.
- [x] backend image cache, stale response, alternate route, retry backoff, prefetch를 제거했다.
- [x] backend image route를 `GET /api/spot/image.jpg` 하나로 통일했다.
- [x] 제거된 live/proxy route는 404를 반환한다.
- [x] `/api/spot/config.image_url`은 단일 route를 반환한다.
- [x] frontend transport는 단일 route만 요청한다.
- [x] 고정 35ms delay와 interval polling을 제거하고 요청 완료 후 다음 요청을 시작한다.
- [x] Dashboard와 설정의 SPOT 카메라는 같은 Blob URL lifecycle을 사용한다.
- [x] display error 후 자동 재요청을 중단하고 명시적 refresh만 허용한다.
- [x] image cache/backoff/stale/age와 internal-temperature 결합 UI를 제거했다.
- [x] 성공한 공식 JPEG만 evidence writer에 전달한다.
- [x] observability는 단일 route의 request, latency, success/failure를 기록한다.
- [x] 운영 진단 문서와 패키지 QA script를 단일 route·완료 기반 관찰로 갱신했다.
- [x] image, temperature, diagnostics HTTP 요청이 하나의 장비 lock을 공유한다.
- [x] 8개 diagnostics output 요청을 병렬 gather가 아닌 순차 요청으로 전환했다.
- [x] diagnostics 각 요청 사이에서 lock을 해제해 대기 중인 image/temperature에 공정성을 준다.
- [x] internal temperature는 temperature request wrapper를 통해 같은 lock을 사용한다.
- [x] focus와 actuator 동기 제어를 async wrapper 뒤에서 실행해 같은 lock을 사용한다.
- [x] 제어 요청 취소 시 worker 완료 전 lock이 해제되지 않도록 했다.
- [x] 테스트에서 image, temperature, diagnostics의 실제 upstream 최대 동시성이 1임을 검증했다.
- [x] API focus/actuator가 serialized wrapper를 호출하는지 검증했다.
- [x] 기존 temperature/diagnostics snapshot 계약을 직렬 실행 의미에 맞게 회귀 검증했다.
- [x] Application Pyrometer `appnumber`를 공식 `/control?p=appnumber`로 요청한다.
- [x] `/output?p=appnumber`가 요청되지 않음을 회귀 테스트로 검증했다.

## Missing Items

- [ ] 새 clean PyInstaller/NSIS를 서버 컴퓨터에 설치하고 최소 15분 동안 실장비 image,
      Temperature, diagnostics, CSV, observability error queue를 함께 검증한다.

## Changed Items (Deviations from Design)

- [x] 최초 설계의 image 전용 single-flight를 서버 증거에 따라 장비 전체 fair lock으로
      확장했다. SPOT 장비의 동시 처리 용량을 추정하지 않고 앱에서 active request를 1개로
      제한하는 보수적 정책이다.
- [x] diagnostics는 하나의 긴 critical section으로 묶지 않고 field별로 lock을 다시 얻는다.
      동일 response atomicity는 만들지 않지만 image starvation을 막고 기존 fact-only 계약을
      유지한다.
- [x] legacy URL key redaction은 과거 export payload 보호를 위해 유지하되 runtime URL 선택에는
      사용하지 않는다.

## Validation Evidence

- Server direct SPOT `/image.jpg`: 60초, 2,014 requests, 2,014 successes, 0 failures,
  0 requests over 1,000ms
- Previous app-only observation: 68.8초, `502 upstream-timeout` 1건
- First serialized server observation: 15분, image errors 0, Temperature poll failures 0,
  CSV +3,086, diagnostics `async_partial` +3,086
- Observation fact root cause: 897/897 `appnumber=http_error`
- Direct SPOT verification: `/output?p=appnumber` HTTP 400;
  `/control?p=info` HTTP 200 `SPOT+ AL`; `/control?p=appnumber` HTTP 200 `7`
- Focused backend SPOT tests: 60 tests PASS
- Device concurrency test: image + temperature + 8 diagnostics, max active upstream = 1
- `npm run health`: PASS
  - frontend typecheck, ESLint, 27 files / 180 tests
  - backend ruff, mypy, 465 tests
- 새 PyInstaller/NSIS package 및 packaged smoke: pending
- Server real-device 15-minute validation: pending

## Recommendations

1. 변경을 clean commit으로 확정한다.
2. clean commit에서 PyInstaller/NSIS를 생성하고 bundled provenance와 packaged smoke를 검증한다.
3. 서버 컴퓨터에 새 installer를 설치해 60초 preflight 후 최소 15분 관찰한다.

## Next Steps

- [x] Device-wide request serialization 구현
- [x] 개발 PC 회귀 테스트 및 전체 health
- [ ] Clean package 검증
- [ ] Server real-device validation 후 completion report 확정
