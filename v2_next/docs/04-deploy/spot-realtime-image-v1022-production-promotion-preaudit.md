# SPOT v1.0.22 production 승격 사전감사

> 작성일: 2026-09-02
> 대상: 소유자가 통제하는 비공개 내부 서버
> 상태: `EVIDENCE_PASS_PROMOTION_HOLD`
> 최종 production 승격 허용: `false`

## 1. 결론

v1.0.22 제품과 v10 Canary의 commit-bound identity, 15분 선행 검증,
120분 현장 관찰 및 정정 사후감사 증거는 서로 일치한다. 제품 hard failure,
신규 앱 오류, ping 실패, TCP reset, SYN 재전송, 75초 미만 동일 four-tuple
재사용은 확인되지 않았다. 종료 경계에서 진행 중이던 요청 1건도 실패가 아니라
정상적인 in-flight 요청으로 정정 대조됐다.

기술 증거의 최대 판정은
`SPOT_V1022_V10_120M_PASS_WITH_SWITCH_LIMITATION_CORRECTED_POSTRUN`이다.
관리형 스위치 자료가 없으므로 물리 스위치 장애 가능성은 배제되지 않았다.

원본 controller 판정은 `SPOT_120M_ROLLBACK_REQUIRED`였고, 관찰 직후 운영자
확인 prompt의 답은 빈 문자열이었다. 또한 종료 스냅샷에 진행 중 요청 1건이 남아
앱 결과 무결성 관련 evidence hold 3건이 기록됐다. 이후 사후감사는 원본 결과를
덮어쓰거나 관찰을 재실행하지 않고, 종료 경계 1건을 정상 in-flight 요청으로
정정 해석하고 지연된 과거 구간 확인 `YES`를 별도 기록했다. 따라서 이 문서의
pass는 `corrected interpretation only`이며 원본 즉시 판정을 pass로 바꾸지 않는다.

이 문서는 production 승격 전 필요한 사실과 제한을 고정하는 사전감사 기록이다.
PR CI 통과, 변경 검토, 승인자 신원과 위험 수락 기록이 끝나기 전에는
production 승격을 허용하지 않는다.

## 2. 제품과 복구본 identity

| 항목 | 값 |
|---|---|
| 제품 버전 | `1.0.22` |
| 제품 build commit | `5cc34b4fffd70195ec7fdd9d27acf4880cecbd80` |
| 검증 도구 commit | `62f6d2df4922d0b47d154632c5d21fa3972e4515` |
| 설치본 SHA-256 | `77577ABB08BD901365B2D366B5ABAF101217E90B8AA5F2E9CB47971FF03123E2` |
| release identity SHA-256 | `3AB24AE19B127C3344DE59A345E668ED429B77D29F5C2BE8EE032B7B15262F32` |
| `app.asar` SHA-256 | `B13909D1A6067E94EC945750C82F17948FC597D3A29060323E807193650F0327` |
| backend bundle SHA-256 | `E171DF1C3EB3C8DB78700E95913E87E7B1EE95460990F6B342AD4E0165448C2C` |
| backend bundle 파일 수 | `1501` |
| `config.ini` SHA-256 | `6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E` |
| 복구 버전 | `1.0.20` |
| 복구 build commit | `cd8cfa649203494cf087206cf656dc2197107ea1` |
| 복구 설치본 SHA-256 | `F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19` |

## 3. 검증 증거 결속

| 증거 | SHA-256 또는 결과 |
|---|---|
| v10 Canary ZIP | `57945774EE2531F921A3B74D9D736C93D5DBF5952C86C111E78903FC592150D9` |
| v10 Canary controller | `6F0EE613E43C2E3518D6FC08881100E298F9F79092FE54EA59D29C583F0561E7` |
| 15분 정정 사후감사 | `A0B50C31D2E7120291F9BD5A65F5FB95D3C2CB2AFE92D05AF28974E0607355EA` |
| 120분 sanitized 공유 ZIP | `93EAFF8D57F18475E24461C6F17B3CBD069406A24B90905DF22EC3B5C84251C2` |
| 120분 control ZIP | `670002C998DA0E74B049ACEDE481EB41826B1D291EE3B161C750F4D24661683A` |
| 120분 정정 사후감사 JSON | `BF6070BDAD02632E51B122C57F3F8D31AA01D9237732A386AEB6A9549715E9DC` |
| 원본 manifest 검증 | `4691/4691` |
| 사후감사 결속 검사 | `21/21` |
| 사후감사 논리 검사 | `20/20` |

원본 `raw_private`와 정제 공유 ZIP은 저장소에 커밋하지 않는다. 이 문서는
개인 경로, SPOT 주소, source port 또는 이미지 payload를 포함하지 않는다.

## 4. 120분 관찰 결과

| 항목 | 결과 |
|---|---|
| 관찰 구간 | 2026-09-02 09:04:46~11:04:47 KST |
| 관찰 시간 | `7200.908`초 |
| 화면 확인 | 전 구간 영상 갱신, 신규 앱 오류 없음 |
| 원본 controller 결과 | `SPOT_120M_ROLLBACK_REQUIRED` |
| 원본 즉시 화면 확인 답 | 빈 문자열 |
| 정정 방식 | 사후 정정 해석만 수행, 관찰 재실행 없음 |
| transport 시작/성공 | `39762 / 39761` |
| image 시작/성공/upstream | `19816 / 19815 / 19816` |
| 종료 경계 보정 | 진행 중 요청 1건, reconciliation 통과 |
| 실패 counter 증가 | `0` |
| 신규 HTTP 5xx | `0` |
| ping | `7088/7088`, 실패 `0` |
| SYN 재전송 / RST / 응답 전 reset | `0 / 0 / 0` |
| 동일 four-tuple 최소 재사용 간격 | `76017.085`ms |
| 75초 미만 재사용 | `0` |

패킷만으로 보인 연결 전 실패 후보 9건과 응답 없음 후보 25건은 전체 앱 요청
성공 counter, 실패 counter 증가 0, 정상 capture 경계, RST·SYN 재전송 0을 함께
대조해 `capture-or-flow-attribution-discrepancy`로 분류했다. 이를 실제 제품 실패로
승격하지 않는다.

## 5. 남은 제한과 수락 경계

1. 관리형 스위치 시작·종료 counter가 없어 switch drop, CRC, link flap을
   독립적으로 배제하지 못했다.
2. 운영자 화면 확인은 관찰 종료 약 2시간 24분 뒤 기록된 사후 확인이다. 원본
   prompt 답은 비어 있었으며, 사후 `YES`는 원본 즉시 확인을 소급 대체하지 않는다.
3. 현재 설치본과 Canary는 `PRIVATE_UNSIGNED_INTERNAL_CANARY_ONLY`다.
4. 미서명 예외는 소유자가 통제하는 비공개 내부 서버에만 적용한다.
5. 고객·협력사·제3자 전달, 공개 다운로드, 상용 납품 또는 조직 차원의 배포에는
   공개 신뢰 Authenticode 서명이 필요하다.
6. 현재 JPEG 검증은 decoder 검증을 수행하지만 명시적인 가로·세로·총 픽셀 상한을
   강제하지 않는다. 신뢰 경계 밖 장비나 네트워크 응답에 대해서는 과대 이미지로
   인한 메모리 고갈 가능성을 별도 제품 버전에서 차단하고 재검증해야 한다.

위 제한의 최종 수락은 승인자의 이름, 역할, 승인 시각과 함께 별도 기록해야 한다.
대화의 작업 진행 승인은 해당 서명 기록을 대신하지 않는다.

## 6. PR과 CI 게이트

- [ ] `codex/spot-realtime-image-performance` 브랜치를 원격에 게시한다.
- [ ] `master` 대상 PR을 생성하고 정확한 head commit을 고정한다.
- [ ] Frontend CI의 typecheck, lint, test, build를 통과한다.
- [ ] Windows PR Artifact의 backend, Electron, release gate 및 패키지 identity를
      통과한다.
- [ ] PR 검토에서 제품 commit과 Canary tooling commit의 역할을 구분한다.
- [ ] 승인자가 관리형 스위치 제한과 지연된 화면 확인을 명시적으로 수락한다.
- [ ] 승인자가 원본 `ROLLBACK_REQUIRED`, 빈 prompt 답, 정정 해석만 수행됐고
      관찰 재실행이 없었다는 경계를 명시적으로 수락한다.

PR CI는 새 head commit에서 빌드하므로 현장 검증 설치본의 제품 commit
`5cc34b4...`와 동일한 설치 파일이라는 증거가 아니다. PR CI는 소스 병합 가능성과
재현 가능한 패키징을 검증하고, 현장 120분 증거는 이미 설치된 제품 identity의
운영 동작을 검증한다. 두 증거를 혼합하지 않는다.

현장 Canary tooling identity는 `62f6d2df...`에 고정한다. 이후 PR에서 추가된
launcher 신뢰 경계와 QA fail-closed 테스트 강화는 제품 runtime을 변경하지 않으며,
과거 120분 증거의 tooling identity로 소급하지 않는다.

검토에서 확인된 live route 접근 로그 샘플링과 설정 화면의 refresh 명칭 개선은
검증된 제품 identity를 바꾸지 않기 위해 이 PR의 사후 보강에서 제외한다. 두 항목은
후속 제품 버전에서 수정하고 해당 새 build를 별도로 검증한다. JPEG 크기·픽셀 수
상한과 decompression-bomb 거부도 같은 후속 제품 보안 gate로 관리한다.

## 7. 롤백과 운영 실패 조건

다음 제품 hard failure가 새로 확인되면 승격을 중지하고 v1.0.20 복구 절차를
검토한다.

- 신규 `spot_image ConnectTimeout` 또는 앱 실패 counter 증가
- backend PID 변경 또는 앱 비정상 종료
- source-port pool exhaustion, 75초 미만 재사용 또는 reuse violation
- TCP reset, SYN 재전송, 보정되지 않은 HTTP 무응답
- 영상 갱신 중단 또는 전체 앱 화면의 신규 오류

관리형 스위치 자료 부재나 계측 불확실성만으로 자동 롤백하지 않는다. 이 경우
`EVIDENCE_HOLD` 또는 `PASS_WITH_SWITCH_LIMITATION`을 유지한다.

## 8. 최종 승인 기록

다음 항목이 모두 채워지고 PR CI가 통과한 뒤 별도 최종 승인 기록을 만든다.

| 항목 | 상태 |
|---|---|
| 승인자 이름 | `PENDING` |
| 승인자 역할 | `PENDING` |
| 승인 시각 | `PENDING` |
| 관리형 스위치 제한 수락 | `PENDING` |
| 지연된 화면 확인 수락 | `PENDING` |
| 원본 결과와 정정-only/no-rerun 경계 수락 | `PENDING` |
| JPEG 크기 상한 미적용 위험 처리 | `PENDING` |
| 승인 범위 | `OWNER_CONTROLLED_PRIVATE_INTERNAL_SERVER_ONLY` |
| PR 번호와 merge commit | `PENDING` |
| production 승격 결정 | `HOLD` |
