# SPOT Realtime Image Performance Do Checklist

> Date: 2026-08-21 | Scope: local implementation and validation

## 1. Implementation

- [x] 장비 상류 호출을 `GET http://{SPOT_IP}/image.jpg`로 고정한다.
- [x] host/path/query/credential 주입을 네트워크 호출 전에 거부한다.
- [x] snapshot 3-10초 정책을 유지한다.
- [x] 동일 cache/single-flight를 사용하는 operator-live 프로필을 추가한다.
- [x] 비이미지 요청률을 차감한 동적 6 requests/s 예산을 적용한다.
- [x] 기본 설정에서 4 FPS, 최소 poll 설정에서 1.2 FPS로 자동 조정한다.
- [x] `/api/spot/live_image.jpg`와 profile 응답 헤더를 추가한다.
- [x] 프런트엔드 완료 기반 스케줄, hidden pause, 단일 in-flight, bounded retry를 유지한다.
- [x] marker와 실제 JPEG decoder 검증을 모두 통과한 payload만 허용한다.
- [x] raw IP, URL, source port를 노출하지 않는 진단 카운터를 추가한다.
- [x] 설정 화면에서 live 통계를 우선하고 snapshot 통계를 호환 fallback으로 사용한다.
- [x] 패키지 현장 QA가 snapshot/live 경로와 profile 헤더를 모두 검사하게 한다.

## 2. Tests

- [x] canonical URL 및 악성 host 입력 테스트를 추가한다.
- [x] snapshot/live cache 및 single-flight 테스트를 추가한다.
- [x] 동적 request budget 테스트를 추가한다.
- [x] 두 앱 경로와 제거된 과거 경로 테스트를 추가한다.
- [x] marker-wrapped invalid JPEG 거부 테스트를 추가한다.
- [x] 프런트엔드 route mapper 및 cadence 테스트를 추가한다.
- [x] observability route attribution 테스트를 추가한다.

## 3. Local Validation

- [x] 집중 백엔드 테스트: 182 tests PASS.
- [x] 프런트엔드 전체 테스트: 35 files, 265 tests PASS.
- [x] 백엔드 전체 테스트: 711 tests PASS.
- [x] Electron startup tests: 94 tests PASS.
- [x] Ruff 및 mypy PASS.
- [x] 프로덕션 프런트엔드 build PASS.
- [x] Windows QA self-test PASS.
- [x] 현장 QA PowerShell 구문 검사 PASS; 실제 호출은 운영 게이트로 남긴다.
- [x] 10초 localhost HTTP/1.0-close guarded-transport benchmark PASS.

## 4. Performance Result

| Metric | Result |
|---|---:|
| Duration | 10.140 s |
| Successful frames | 37 |
| Displayed/upstream cadence | 3.6489 FPS |
| Effective live cap | 4.0 FPS |
| Response latency p95 | 31.0 ms |
| Maximum upstream concurrency | 1 |
| Port pool exhaustion/reuse/transport failures | 0 / 0 / 0 |

## 5. Promotion Gate

- [x] 로컬 구현 및 transport 성능 검증을 완료한다.
- [ ] identity-bound installer를 생성하고 서명/해시를 검증한다.
- [ ] 실제 SPOT 장비에서 `/image.jpg` 응답과 앱 두 경로를 smoke test한다.
- [ ] 15분 관찰 및 120분 canary에서 요청률, old-ACK/RST, port pool을 확인한다.
- [ ] 운영 승인 전에는 로컬 PASS를 production/field PASS로 승격하지 않는다.
