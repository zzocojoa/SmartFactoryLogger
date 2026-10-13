# 개별 이미지 검사 실행 파일과 CSV 계약의 검증 범위

작성일: 2026-10-14. 문서 기준 HEAD: `d2e1e89047acceb8e41e8c43edbf14387cb66d3c`.
후보4cc의 기존 이미지 검사기를 독립 Windows 실행 파일로 패키징했다. 보존된 격리 후보
설치/재시작 사본과 오류 사본에서 Python·EXE 결과가 일치했다. 서버 최종 폴더까지 복사했다.
서버 실행, 전체 운영 데이터 PASS 및 출시 승격은 미완료다. R1–R6 HOLD를 유지한다.

## 빌드와 식별

[기존 검사 소스](../../scripts/validate_spot_image_files.py)를 사용했다. 제품 코드·설치본과
기존 CSV 검사기는 변경하지 않았다. clean 후보 checkout의 tracked 1,009파일, 설치본 SHA,
설치된41개 의존성 버전을 빌드 전후 대조했고 최종 원본 대조도 통과했다.
Python3.12.6/PyInstaller6.20.0/hooks2026.5의 실제 빌드 exit0이다.

| 대상 | 식별 |
| --- | --- |
| 후보 build | `4cc7393e1bafbf90a329726aed9470fe0daacb21` |
| 후보 installer SHA256 | `8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848` |
| 이미지 EXE | 16,208,474바이트 / `5601b347637bd0dcb9971839ec93bdc2860ad4594e5ba328acd4e70fa91d5f14` |
| 동봉 원본 Python | 14,149바이트 / `067f2a50f69d44e7665020ebd64898964f215f32cbf7fc2caca72cea1edc79db` |
| 기존 CSV EXE SHA256 | `e728730ad841dd4a754a6c0880e0e1216de5e3d0cd5646c22de9245fc85b0b2f` |

`--add-data`로 같은 Python 원문을 EXE에 넣어 frozen 실행에서도 `tool_sha256`을 보존했다.
CArchive76항목에서 entry script, 원문, Python/SQLite/Pillow 런타임을 확인했다. 모든 이미지
실행 결과의 tool SHA가 동봉 원문과 같다. 선택적/다른 OS 모듈의 빌드 경고는 원문 보존했다.
JPEG 실행 검증을 모든 선택적 이미지 형식 지원으로 확대하지 않는다.

Authenticode는 `NotSigned`, 정책은 `UNSIGNED_INTERNAL`이다. 인증서 조건을 다시 추가하지 않는다.
현재 checkout의 LF와 후보 checkout의 CRLF 원문을 같다고 가정한 보조 비교는 exit1이었다.
후속 비교에서 줄바꿈 정규화 후 후보 Git 소스와 내용이 같고 후보/동봉 원문은 바이트까지
같음을 확인했다. 이 진단 실패와 수정 근거를 `source-eol-comparison.json`에 보존했다.

## 실행 검증

증거: [PDCA_IMG128_20261014_6cac921a](C:/Users/user/Desktop/SmartFactory/PDCA_IMG128_20261014_6cac921a).
`verification-result.json`에 24개 실제 실행 명령·exit·시간을 기록했다. 각 stdout/stderr와
이미지 결과 원문을 검토했다. Python/EXE의 summary는8조건 모두 완전히 같다.

| 입력 조건 | CSV EXE exit | 이미지 Python / EXE exit | 검출 결과 |
| --- | ---: | --- | --- |
| 보존 I4 설치 종료 사본 | 0 | 0 / 0 | v1/v2 각327행, 이미지133개, 오류0 |
| 보존 I5 재시작 종료 사본 | 0 | 0 / 0 | v1/v2 각296행, 이미지199개, 오류0 |
| 이미지1개 누락 | 0 | 1 / 1 | missing_file1 |
| 동일 크기 JPEG 바이트 변조 | 0 | 1 / 1 | sha256_mismatch1, decode_failed1 |
| fact SHA/크기까지 맞춘 디코딩 불가 파일 | 0 | 1 / 1 | decode_failed1 및 가로·세로/MIME 불일치 |
| fact에 없는 고립 이미지1개 | 0 | 1 / 1 | orphan_file1 |
| 최종 manifest SHA 불일치 | 1 | 0 / 0 | CSV 검사기가 fact SHA 불일치 검출 |
| 상대경로 이탈 `../escape.jpg` | 1 | 1 / 1 | CSV 경로 오류, 이미지 unsafe_image_path1/orphan_file1 |

원본344파일을 기존 native `data-after.json`의 크기/SHA와 대조하고 시험 후 재확인했다.
오류는 새 사본에만 만들었다. 각 조건의 입력 파일과 검사기를 Windows 읽기 공유 핸들로
유지하며 검사 종료 전 원문을 다시 대조했다. 두 정상 이미지 집합은 누적되므로332개의
서로 다른 이미지로 합산하지 않는다. 격리 앱의 합성 JPEG 자료이며 실제 장비 촬영 검증이 아니다.

환경은 별도 AppData/Temp와 시스템 디렉터리만의 PATH, 저장소 밖 cwd를 사용했다.
Python 프로세스와 EXE에 같은 환경을 적용했다. 기존 단위 시험
`python -m unittest -v backend.tests.test_spot_image_file_validation`은10개/exit0/skip0,
최종3개 작업 도우미의 `ruff check --isolated --select F,E9`도 exit0이다.
단위 시험이 portable EXE의 모든 형식을 시험한 것으로 해석하지 않는다.

정상 CSV 결과의 위치 필드2개 `no populated values` 경고는 유지했다.
metadata의 부가 fact 경로2개는 옛 `C:/Users/WDAGUtilityAccount/...` 절대경로를 가리켰으며
실행 전후 모두 없었다. 중간 전체 시간의 경로 부재를 보호한 것은 아니다.
따라서 `BEFORE_AFTER_ONLY_NOT_A_PROTECTED_CONSUMER_CLOSURE`로 기록한다.
이 결과로 CSV 검사기가 소비할 수 있는 모든 외부 입력의 잠금이 완성됐다고 주장하지 않는다.

## 전달과 사용 계약

최종 개발 묶음은 증거 루트의 `IMG128r2`다. 실행 파일, 원문, README, build-provenance,
verification-summary, manifest의6파일/16,240,297바이트다.

- 공유: `Z:/SmartFactory/20261014/send/IMG128_20261014_6cac921a_r2`
- 서버: `C:/Users/user/Desktop/SmartFactory/IMG128_20261014_6cac921a_r2`
- manifest SHA256: `d9a631f128226cc09b6964fabc843bd6134fb28ca764249ce8d6bdb04eabb072`

개발→공유6파일의 크기/SHA를 비교했고 Chrome 원격 탐색기로 서버 로컬에 복사했다.
03:11 KST에 실제 절대경로와 파일6개의 존재를 확인했다. 서버 로컬 SHA 검산과 도구 실행은
수행하지 않았다. 기존 결과 파일명을 잘못 적은 첫 설명서 묶음은 재작성하지 않고 보존했다.
r2는 설명서의 `issues.csv`를 실제 `image-checks.jsonl`과 `inventory-before/after.jsonl`로
고친 별도 묶음이다. EXE/원문·빌드 provenance·시험 결과 바이트는 같다.

후속 실행자가 적용할 체크리스트:

1. 닫힌 검증 사본의 전체 목록과 fact·이미지를 고정하고 새 출력 폴더를 지정한다.
2. 같은 사본에 CSV 검사기와 이미지 검사기를 모두 실행하고 원문/실제 exit를 보존한다.
3. 실행 전후 목록·해시와 선택적 외부 fact의 소비 경계까지 확인한다.
4. 관찰 종료/최종 설정/정상 프로세스 종료 증거와 같은 입력 바이트에 결합한다.

CSV 검사기는 JPEG 파일 바이트를 검사하지 않고, 이미지 검사기는 최종 manifest를 검사하지
않는다. 어느 한 도구의 성공으로 다른 조건이나 전체 QA를 대신할 수 없다.

## 남은 조건

보호된 외부 실행기·선택적 fact 입력 경계·최종 delta와 정상 종료 결합, 실제 최종 attestation·
물리 comparator·UI/packet·서버 설치/복구/3회 시작/15분/120분 QA와 승격이 남는다.
기존 FREAD 실행 요청을 반복하지 않았다. 이번 작업으로 서버 앱 설정·생산 정보·설치본을
변경하지 않았다. 화면에는 Running과 제품60185/금형8이 관찰됐으며 과거60332/6을 강제로
다시 적용하지 않았다. 이는 화면 관찰이며 실제 build나 실행 세대의 재검증은 아니다.

제품 소스·설치본이 같아 전체 health/build/NSIS를 반복하지 않았다. 전체 데이터 gate는
NOT_EVALUATED, R1–R6은 HOLD, 현재 운영본과 다음 롤백은541d/08C다. 목표는 active다.

## 증거 보존

`Z:/SmartFactory/20261014/records/PDCA_IMG128_6cac921a`에 증거1,430파일,
원문62,285,518바이트의 ZIP과 manifest를 보존했다. 봉인 시점 증거 루트의 모든 일반 파일을
포함하며 새 `sealed` 디렉터리와 이후 commit 영수증은 제외한다. ZIP 내부 전 파일의 크기/SHA,
CRC 및 공유 ZIP/manifest SHA를 대조했다. 실제 봉인 명령은 exit0이다.

- ZIP: 52,196,525바이트 / `e1d951d9299be163f4edc084fd2118e3416b74f49aff074073c97e77354d2c60`
- manifest: 302,120바이트 / `7f801887d7a7e3795aac5a0610220ebb52df49dec688520d9593f0d9d80d8c86`

UI 전달 근거는 증거 루트의 `server-delivery-r2.json`, `server-delivery-r2.jpg`(절대경로),
`server-delivery-files-r2.jpg`(6개 파일 목록)다. 공유 파일 해시와 서버 화면 관찰을 구분한다.
