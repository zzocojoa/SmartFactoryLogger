# 2026-10-12 장비 시간 필터 직접 대조와 모델 정보의 출처

장비·운영 확인, QA, 릴리즈 판단 담당자는 사용자 본인으로 확정됐다.
승인 장비 프로파일·최종 build attestation·R3 기술 gate는 아직 미완료이며 현재 운영 설정을 변경하지 않았다.

## 직접 확인 범위

서버 Chrome 원격 데스크톱에서 장비 메뉴의 실제 링크에 있는 정보/Time Functions GET 화면을 읽었다.
메뉴의 30초 홈 복귀와 원격 입력/화면 지연을 구분하고, 새 주소가 실제 표시된 응답 화면으로 확인했다.
checkbox·수치·적용·네트워크·인증·펌웨어는 조작하지 않았다.
새 증거 루트는 `C:/Users/user/Desktop/SmartFactory/PDCA_PROFILE_20261012_ae6d45df`이며
정보 화면과 시간 필터 화면을 저장했다. 물리 식별값이 있는 화면은 기존처럼 private 증거에만 보존한다.
8개 증거 파일의 manifest SHA256은 `f391650038cd8be4a14bd6d61068da9186d568052960f8cd244ea784226833a4`다.
이 봉인 뒤의 사용자 “미정” 답변은 새 압축 조사 루트의 별도 원문 기록과 현재 PDCA 상태에 연결한다.

| 시간 필터 화면 | 관측값 | 이전 운영 metadata와 대조 |
|---|---|---|
| Output Time | 100ms | 앞선 정보 화면의 출력 시간과 일치; 현재 provenance의 별도 필드는 아님 |
| Limiter | unchecked | `limiter_enabled=false` 일치 |
| Averager | unchecked, 1 values | `averager_enabled=false` 일치; values 1의 별도 승인 판정 없음 |
| ModeMaster | unchecked | `modemaster_enabled=false` 일치 |
| Peak Picker | unchecked | `peak_picker_enabled=false` 일치 |
| Averager 2 | unchecked, 1 values | 현재 snapshot에 별도 필드 없음; 임의로 동일한 검사 완료 항목을 만들지 않음 |
| Ratio Raw | unchecked | `ratio_raw_enabled=false` 일치 |

정보 화면은 AL Spot, App1: AL E, 200–900°C, Emissivity App, Focus 6071mm,
Output Time 100ms, Cal 1024, V 40.38을 표시했다.
앞선 I/O·Alarms·Core의 7필드 대조와 이번 5개 필터 bool 대조는 관측 시점이 다르다.
동일 시각의 전체 장비 snapshot이나 최종 attestation으로 확대하지 않는다.

## 모델 정보와 미확정 항목

운영 metadata의 `spot_model_info=SPOT+ AL`은 장비 모델 readback의 증거가 아니다.
`backend/config.py`의 `DEFAULT_SPOT_MODEL_INFO`가 같은 문자열이며 회수한 config.ini에 `modelinfo` override가 없다.
환경 변수 override의 실제 서버 상태는 별도 미확인이다. 기본값으로 실제 하드웨어 SKU를 확정하지 않는다.
후속 모델명/부품번호 질문에 사용자는 “미정”이라고 답했다. 답변 대기는 종료하고 실제 모델은
`UNDETERMINED`로 기록한다. 같은 질문을 반복하지 않으며 기본값/범위만으로 실제 모델을 추정해 승인하지 않는다.

제조사 [SPOT 교체 안내](https://www.ametek-land.com/obsolete-products/spot)는 구 SPOT AL과
SPOT+ AL을 구분하며 SPOT+ AL의 200–900°C 범위를 제시한다.
[현행 SPOT+ AL 설명](https://www.ametek-land.com/products/non-contact-infrared-thermometers-pyrometers/spot-aluminium-extrusion-quench-strip-pyrometer)의
범위도 화면과 부합하지만 이것은 모델 추론의 보조 정보이며 해당 장비의 라벨/부품번호 증명이 아니다.
링크의 구 장비 user guide는 로그인으로 이동했으므로 미열람으로 기록하고 인증 절차를 우회하지 않았다.

저장소의 `docs/reference/ametek_land_spot.pdf`는 SHA256
`c8d315fafd796075545558afcca894e0f1855fc3ba6ebc2f875e95ca1d39bf22`, 24페이지의 프로토콜 자료다.
alarm status bit 4를 확인했지만 실제 Low Signal 임계값 동일 시점의 `<`/`<=` 동작을 입증하지 않는다.
현재 소프트웨어 `lt`/`lte` 분기와 물리 장비의 경계 판정 근거를 구분한다.

| 남은 항목 | 다음 확인 근거 |
|---|---|
| 정확한 모델명/부품번호 | 실제 장비 라벨 또는 구매/교정 기록과 private 장비 식별값 연결 |
| 승인된 전체 프로파일 | 아래 검토 기록과 사용자 본인의 실제 승인 기준 대조 |
| 물리 Low Signal comparator | 해당 모델/펌웨어의 명시적 계약 또는 승인된 물리 경계 시험 |
| 최종 attestation | 최종 미서명 후보 build·fingerprint·관측/승인 근거·실제 적용·동일 세대 종료 연결 |

검토 기록 양식: 실제 모델/부품번호 · App mode/범위 · analog 4/20mA · Low Signal enabled/threshold/comparator 근거 ·
Peak Picker/Limiter/Averager/ModeMaster/Ratio Raw · Focus/Window Obsc · 승인 기준 근거/담당자/시각 ·
최종 build/fingerprint · 일치/미확인 필드.

이번 단계는 읽기/문서 작업이며 제품 소스를 변경하지 않아 통과한 최종 health를 반복하지 않았다.
전체 후속 PDCA는 active, R1~R6 출시 HOLD이며 미서명 정책/기존 운영본·롤백 installer identity를 유지한다.

## 2026-10-13 App1 세부 화면의 추가 관측

서버 Chrome의 기존 장비 탭에서 메뉴 → Settings → `>>>`로 `10.1.10.50/app.ssi`를 읽었다.
화면 제목은 `APP1: AL E`이며 다음 값을 표시했다.

| 항목 | 화면의 실제 표시 | 판정 범위 |
|---|---|---|
| Thermocouple | 입력란 비어 있음, 옆에 C 표시 | 입력하지 않음 |
| Offset | 305 | 단위·보정 의미를 임의 추론하지 않음 |
| Emissivity Low Limit | checked, 0.015 | 관측값, 승인된 기준 아님 |
| Emissivity High Limit | unchecked, 1.000 | 관측값, 승인된 기준 아님 |

Advanced 화면에는 Language/LED/Demo LED/Test Output/Reboot/Factory Settings/Name/Lock이 있었으나
정확한 모델명·부품번호·일련번호 표시는 확인하지 못했다. 입력·체크박스·재부팅·공장 초기화 항목은
조작하지 않았으며 조회 뒤 기존 측정 탭으로 돌아갔다. 모델 `UNDETERMINED`와 승인/attestation HOLD는 유지한다.
추가 화면은 `Desktop/SmartFactory/PDCA_STREAM_COPY_20261012_5a7ed041/device-app1-details-20261013-0048.jpg`에
보존했다. 앞선 봉인된 장비 증거 폴더에는 새 파일을 추가하지 않았다.
