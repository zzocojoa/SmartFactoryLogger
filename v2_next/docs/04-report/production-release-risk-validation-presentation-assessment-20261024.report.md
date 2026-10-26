# PC별 표시 원시 기록과 승인 판정의 연결

2026-10-24. 추가 수치 계측의 **판정 코드 준비 완료**, 실제 현장 계측은 미실행이다.
기존 PC 4대의 동시 조회·육안 연속 갱신과 120분 관찰 결과는 보존·재사용한다.

## 이번 변경

`scripts/field-v1028/assess_presentation_capture.py`는 서버 CDP 기록 1개와 조회 브라우저
기록 3개를 승인된 C32 정책에 연결한다. 제품과 서버의 실행·설정은 변경하지 않는다.

- 입력 목록 자체와 개별 결과·화면 확인 기록을 SHA256으로 고정한다. 중복 JSON 키,
  비유한 숫자, 경로 이탈, 기존 출력 덮어쓰기는 거부한다.
- PC_1~PC_4가 서로 다른 물리 PC에 해당하는지, 서버 1대·조회 PC 3대인지 확인한다.
  PC 이름이나 서로 다른 run ID만으로 물리 대수를 추정하지 않고 사용자 확인과 대조한다.
- C32 build·동일 logger·정확한 페이지·고정 관찰기 버전·실제 현장 context를 확인한다.
- 저장된 summary의 PASS를 신뢰하지 않고 응답 hash→Blob load→Element Timing 표시를
  원시 기록에서 다시 연결한다. 각 900초 단조 시계 구간의 시작/끝 공백도 평가한다.
- 확인된 HTTP 오류/요청 실패와 2초 이상의 표시 공백·흰 화면은 FAIL이다.
  빠진 측정·가림/초점 이탈·미확인 화면·다른 실행/시험 자료는 INCOMPLETE다.
- p95/p99/최대 공백 계산은 기존 `approved_release_assessment.assess_display`를 사용한다.
  이번에 새 성능 수치나 추가 120분 조건을 만들지 않았다.

서로 다른 PC의 벽시계가 동기화됐다고 가정하지 않는다. 각 PC의 900초 구간을 따로 보존하고,
**각 구간 동안 네 화면이 모두 조회 중이었다는 별도 현장 확인**을 결합한다. 순차 실행을
동일 시각 시작으로 표시하지 않으며, 짧은 교집합을 900초 공통 계측이라고 표시하지 않는다.
브라우저 시각과 사용자 화면 확인은 서로 다른 증거로 표시한다.

## 실행 입력 계약

현장 결과를 회수한 새 폴더에 `index.json`을 만든다. `schema`는
`sfl-four-client-capture-index-v1`, `logger`는 실제 공통 실행 UUID다.
`clients`에는 정확히 네 항목을 기록하고, 각 항목에 다음 값을 둔다.

```json
{
  "client_id": "PC_2",
  "physical_id": "실제 확인한 조회 PC 식별자",
  "role": "browser",
  "page_url": "http://192.168.0.7:8000/dashboard",
  "image_origin": "http://192.168.0.7:8000",
  "path": "PC_2.json",
  "sha256": "회수한 원본의 실제 SHA256"
}
```

서버 항목은 `role=server`, 실제 file 페이지, 실제 loopback 이미지 origin을 사용한다.
각 경로는 index 폴더 기준이다. `screen_confirmation`은 별도 JSON의 상대 path/SHA256이며,
화면 확인이 없으면 null로 두고 INCOMPLETE로 판정한다.

별도 화면 확인 JSON에는 `schema=sfl-field-screen-confirmation-v1`, `confirmed_by=user`,
사용자 실제 응답인 `user_statement`, PC별 실제 `client_run_ids`와 `physical_client_map`,
`all_four_visible_during_each_capture`, `all_windows_unobscured`, PC별 `white_screen_events`를 둔다.
**실제 응답 없이 true/0을 채우지 않는다.** 예전 육안 확인을 새 실행의 확인으로 재사용하지 않는다.

```powershell
python scripts/field-v1028/assess_presentation_capture.py `
  --index '<새 회수 폴더>\index.json' --index-sha256 '<검산한 목록 SHA256>' `
  --policy 'docs/V2/05_운영_배포/approved_release_policy_20261023.json' `
  --out '<새 회수 폴더>\display-assessment.json'
```

이 명령은 파일만 읽고 새 결과를 쓴다. PASS/exit0도 표시 구성 요소의 판정이며,
전체 출시 HOLD·promotion_allowed=false를 유지한다. 최종 통합 QA와 운영 승격은 별도다.

## 최종 변경 상태의 확인

- `python -m unittest test_assess_presentation_capture test_approved_release_assessment -v`
  (작업 폴더 `scripts/field-v1028`): **23 tests, exit0**, 실행 chunk `e58306`.
- 실제 보존된 브라우저 격리 결과 3개를 해시 확인 후 읽어 모두
  `not-approved-field-capture-context`로 거부했다. exit0, chunk `e289f0`.
- 합성 데이터로 정상 입력, 중복 PC/실행, 다른 세대/context, summary 위조, 원시 대응 누락,
  불완전한 시간/가시성, HTTP 오류, 표시 끝 2초 공백, 흰 화면, 출력 덮어쓰기를 확인했다.
  이 합성 PASS는 현장 성능 결과가 아니다.

실행·해시 기록은
`C:\Users\user\Desktop\SmartFactory\PRESASSESS32_20261024_a70e9c16`에 보존한다.
현재 남은 선행 조건은 조회 PC 3대 조작 가능 여부와 현장 시간 조율이다. 서버의 실제 진단
실행 세대 결합은 시작 직전 확인해야 한다. 그 뒤 실제 표시 수치, 최종 통합 판단·운영 승격과
롤백 기준 갱신을 진행한다. 설치본과 기존 기록은 이번 변경으로 재빌드하거나 재판정하지 않았다.
