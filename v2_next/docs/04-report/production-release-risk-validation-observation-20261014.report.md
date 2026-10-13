# 현장 수집기: 통합 관찰과 계측 자식 종료

2026-10-14. 최종 21개 시험과 개발 PC의 420초 합성 앱 관찰을 통과했다.
HTTP 1,960요청, 자원85표본, OS 식별85표본을 같은 시각 기준으로 수집했다.
이는 수집기 개발 검증이며 실제 후보 또는 서버의 성능/현장 QA가 아니다.
R1–R6 HOLD, `full_data_gate=NOT_EVALUATED`, 운영/다음 롤백541d/08C 및 미서명 정책을 유지한다.

## 변경과 검사 범위

기준 HEAD: `24c86f4952188b5c2a7a38656effe5da701b283d`.
[통합 모듈](../../scripts/field-v1028/field_observation.py),
[Windows Job](../../scripts/field-v1028/field_windows_job.py),
[시험](../../scripts/field-v1028/test_field_observation.py)을 추가했다.
제품과 기존 HTTP·자원·payload 식별 모듈의 바이트는 변경하지 않았다.

- 초기 payload/실행 식별을 확인한 뒤 HTTP·자원·OS 조회를 각각 별도 프로세스에서 수행한다.
  시작 전·종료 후 health와 관찰 중 모든 health에 같은 SPOT/logger UUID를 요구한다.
  첫 GET도 200ms 판정에 포함한다. 자원 표본에 같은 backend PID/create-time/exe가 있어야 한다.
- 모든 구성요소의 정확한 파일 집합과 SHA를 검산하고 payload를 종료 전에 재검사한다.
  120분 HTTP 원문 수를 수용하도록 설치 트리의6000항목 제한과 결과 manifest 제한을 분리했다.
  이는 응답 payload/schema 전체 기능 검증이나 표본 사이 무변경의 증거는 아니다.
- 감독자가 직접 만든 자식의 HANDLE을 이름 없는 Job에 등록한 뒤 실행 gate를 연다.
  관찰 대상 앱은 이 Job에 넣지 않는다. 준비/최종화 각각 최대180초, 관찰 최대7200초이며
  finalizing 이벤트는 deadline을 연장하지 않는다. 종료 시 남은 계측 자식도 정리한다.
- Windows Job의 자식 상속·KILL_ON_JOB_CLOSE는 [Microsoft 문서](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
  생성한 프로세스 HANDLE 사용은 [Python 3.12 문서](https://docs.python.org/3.12/library/multiprocessing.html#multiprocessing.Process.sentinel)에 따른다.
- 원문 손실·첫 응답 지연·세션 변경·시간 초과·사용자 중단·과대 IPC·결과 누락은 FAIL/HOLD다.
  부모 자체의 파일 저장을 감싸는 보호된 외부 launcher는 아직 필요하다.

## 재현과 실제 결과

증거: [PDCA_OBS128_20261014_682a9de3](C:/Users/user/Desktop/SmartFactory/PDCA_OBS128_20261014_682a9de3).
시험 앱은 로컬 Python 바이너리를 복사해 만든 HTTP fixture다. 이름과 합성 metadata가 후보 형식을
따르지만 실제 Electron/후보 backend가 아니며 별도 fixture reference SHA로만 허용했다.

| 검사 | 실제 결과 |
| --- | --- |
| r1, 16시험 | exit1/실패1. 예정 시각보다1ms 미만 빠른 요청과 이미지1슬롯 누락을 보존 |
| r2, 17시험 | exit1/실패1. 실제 monotonic deadline 재확인으로 음수 지연은 없어졌으나 이미지2슬롯 누락 |
| 프로세스 분리 r3, 17시험 | exit0/skip0 |
| 추가 종료 r4, 21시험 | exit1/실패1. Job의 고정 프로세스 수2 기대가 실제3과 달랐음. 최소 자식 존재와 실제 자식 소멸·Job 잔존0을 검사하도록 시험 수정 |
| 최종21시험 | exit0/skip0. 감독자 손실, 고아 자식, Job 등록/조회 실패, 앱 생존, 첫 응답 지연, 서비스 변경, manifest 변조와 IPC/원문 오류 확인 |
| GIL 유지 native 호출350ms 주입 | 이전 thread 구조 이미지25슬롯 중4누락/FAIL, 새 구조25요청·누락0/PASS. 두 실행의 기대 판정 확인 명령은 exit0 |
| 최초420초 시도 | 약27초에 실제 ENOSPC. 세 구성요소 오류·빈 부분 파일·불완전 manifest를 보존. 감독 결과FAIL, 계측 Job 활성 프로세스0 |
| 공간 계측을 더한420초 재시험 | exit0/PASS. health210/data70/image1680, 각 누락·오류·timeout0. 1960레코드 저장·적체0 |
| 경계 GET 포함 health | 총212개, 첫1.6449ms/최대17.2064ms. 첫 요청 제외 없음 |
| 자원·OS 식별 | 각각85표본. 준비120초 이후61표본/299.9897588초, coverage SUFFICIENT. 자원 성능 gate 자체는 NOT_EVALUATED |
| 결과 쓰기 | 최대 파일 저장36.3257ms, 최종 저장 배출4.3706ms |
| 정상 종료 | 계측 프로세스4개 모두 종료, 강제 종료 없음. 합성 앱의 정상 종료 exit0 |
| 공간 표본 | 200ms 목표 간격2094표본, 사용자 가용·volume 여유 최솟값13,723,275,264바이트. 이전 ENOSPC 순간은 관측하지 못해 원인 미확정 |
| Ruff | 최종 직접 의존6파일과 외부 검증 도우미 F/E9 exit0 |

GIL 주입 결과는 제어된 재현에만 인과 근거가 있다. 주입하지 않은 r1/r2 또는 과거 서버
timeout/drop을 같은 원인으로 확정하지 않는다. 재시험 통과도 앞선 ENOSPC 원인의 해결을 뜻하지 않는다.
관리자 권한이 필요한 `fsutil quota query C:`는 접근 거부(exit1)였고 해당 할당량 조회는 미검증이다.
후속 공간 기록은 [GetDiskFreeSpaceExW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdiskfreespaceexw)의
사용자 가용 공간과 volume 전체 여유를 별도로 읽었다. 기존 자료 삭제나 ACL 변경은 수행하지 않았다.
최초 GIL 재현 launcher의 의존 모듈 누락(exit1)도 보존한 뒤 별도 입력 폴더로 수정했다.

재검증 절차:

1. `source-final`의6파일과 저장소 소스 SHA가 일치하는지 확인한다.
2. 새 출력 폴더를 `SFL_OBSERVATION_TEST_ROOT`로 지정하고
   `python -m unittest discover -s <source-final> -p test_field_observation.py -v`를 실행한다.
3. `run_observation_probe.py`의 `--gil-stall`로 보존된 이전/최종 구조를 각각 검사한다.
4. `run_space_probe.py --source <source-final> --output <새 폴더> --duration 420 --expect PASS`로
   같은 최종 소스의 관찰·공간 기록을 얻는다. 이미 사용한 출력 경로는 재사용하지 않는다.
5. 각 구성요소의 manifest와 worker-result SHA, 실제 exit, 원문 health/session/표본 수,
   Job 활성 프로세스0을 함께 확인한다. 실패/누락 시 다음 단계로 승격하지 않는다.

검증 로직과 입력·원문 검산은 묶음의 runner, `source-final.json`, `verification-reviewed.json`에 있다.
제품 입력이 바뀌지 않았으므로 전체 제품 health·NSIS·서버 설치 시험은 이번에 반복하지 않았다.

최종 통합 모듈 SHA256은 `b1bd5038cfe100e2ed2fab0a7901c087e76e4c2478e0fb3108e2870bbfaa09c9`,
Windows Job은 `b3c70f89553601b1b91277b52ff36646993d84ce15518a2242e6e49aae02c302`,
시험은 `7c3190e1c03d06bc9563e5d1d1d46bd832626d29be34e31c32babad40658d4b2`다.
36,050개 기록 파일을 `Z:/SmartFactory/20261014/records/PDCA_OBS128_682a9de3`에 복사하고
전부 원본/사본 SHA를 대조했다. manifest 제외356,759,819바이트이며 manifest SHA256은
`e55d15e947c04f304c00a5cafde5ff934f6417ffb3795009e0a2958eaf179487`이다.
봉인 이후의 전송·문서 갱신·저장소 최종 확인 영수증은 별도 로컬 기록으로 보존한다.

## 설계 대비 남은 조건

설계5.8의 동시 원점·첫/마지막 GET·파일/실행 식별·시간 상한·계측 자식 정리는 위 개발 범위에서
확인했다. 전체 출시 계획의 완료율이나 현장 PASS로 계산하지 않는다.

- 보호된 외부 launcher와 잠긴 동일 실행 바이트, 최종 backend generation/fingerprint attestation.
- UI/web vitals·packet·정상 앱 종료·최종 데이터 delta를 포함한 전체 현장 수집.
- 서버 설치/복구·세 번 시작·현장 QA·초기15분/120분 canary 및 과거 finding 영향/처리.
- 제조사 경계 근거·물리 시험, 전체 데이터 gate와 운영 승격·실제 적용 후 롤백 기준 갱신.

00:58 KST 원격 Explorer에서 `FREAD128_20261013_06df50b9`를 새로 고쳤으나 기존5파일만 보였다.
실제 서버 명령 실행 여부와 로컬 해시는 미확정이며 실행 요청을 중복 발행하지 않았다.
새 모듈은 서버에 전달/실행하지 않았고 운영 앱의 종료·설치·설정 변경도 수행하지 않았다.
