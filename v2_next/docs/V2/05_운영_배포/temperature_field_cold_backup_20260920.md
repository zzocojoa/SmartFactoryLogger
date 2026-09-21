# Temperature 현장 전환 백업 준비

2026-09-20 사용자의 “지금 승인하니까 진행해”를 기존 앱 정상 종료, 복구 가능한 백업 확인,
후보 `72a41033`의 짧은 현장시험 진행 승인으로 기록한다. 모델명 확인을 추가 선행 조건으로 두지 않는다.
처음 전달한 실행 단계는 **지정 3루트 전체 파일 백업과 별도 파일 복원 검산까지**였다.
이후 아래 범위 조정에 따라 운영 수집 재개를 우선한다.

## 현재 방침: 전체 백업 중단·운영 재개

2026-09-20 20:46~20:47 서버 화면에서 R4의 5/7 backup-copy 진행을 확인했다.
47초 동안 541개/13,995,513,197바이트에서 700개/20,354,847,805바이트로 증가했다.
중간 관측 기록은 R4 개발 검증 폴더의 `interim-check-20260920-2047.json`이다.
이 단계는 정상 종료·closeout·cold inventory 검사를 거친 뒤이며, 운영 앱 수집은 중단 상태다.
이는 파일 백업 진행 관측이며 백업 완료·복원 검산 완료·현장 검증 통과를 뜻하지 않는다.

사용자가 전체 백업 필요성을 지적했다. 기존 운영 설치/데이터를 보존하고 후보 경로를 분리하는 짧은 시험에
전체 누적 이력을 두 벌 복사하는 범위는 과도했음을 인정했다. 현재 우선순위는 다음과 같다.

1. 진행 중인 백업 helper만 중단한다. 원본과 부분 사본은 보존하며 부분 사본을 복구 검증 완료로 취급하지 않는다.
2. helper 종료 및 파일 핸들 해제를 확인한 뒤 기존 d7a1b20 설치 앱을 일반 권한으로 재시작하고 수집 상태를 확인한다.
3. 후속 후보 시험은 필요한 설정/상태의 제한된 백업과 별도 profile/data/image/fact/spool 경로로 준비한다.
   전체 이력 백업 완료를 다시 선행 조건으로 만들지 않는다.

20:54경 사용자가 실행 중인 backup 콘솔에서 Ctrl+C를 한 번 눌러 중단하도록 요청했다.
Computer Use의 터미널 UI 조작 금지 때문에 이 키 입력은 사용자에게 맡긴다.
사용자가 “백업 출력이 멈추고 작업이 종료됨”이라고 확인했다. 백업 콘솔이 사라졌고,
작업 관리자에는 과거 대화형 PowerShell 하나만 남았으며 재시작 전 smart 프로세스는 없었다.
기존 설치 폴더의 `smart-factory.exe`를 탐색기에서 일반 더블클릭해 운영 앱을 재시작했다.
후보/NSIS 실행, 원본 덮어쓰기, 미완료 사본 삭제는 수행하지 않았다.

### 운영 재개 확인: 21:07

- 21:05 앱 Diagnosis: REAL, Driver OK, Thread Alive, v1.0.26, 최근 60초 332요청/오류 0/ErrorQ 0.
  `Runtime: frozen`은 패키징 유형 표시다.
- 시작 직후 SPOT STALE/Comm 경고와 카메라 설정 로딩을 관측했다. 이후 카메라 영상과 온도가 갱신되고
  Running/EX OK/LS OK/SPOT OK/Comm OK로 회복됐다. 지연 원인은 확정하지 않았다.
- 서버의 새 `Factory_Integrated_Log_v2_20260920_210223.csv`를 탐색기로 Z에 복사하여 개발 PC에서 검산했다.
  1,914,342바이트, schema 2.5.0, 1,389행, sample_seq 1~1389의 인접 불연속 0, logger service 1개다.
  행 시각 범위는 21:02:23.453~21:07:18.465이며 첫 valid 온도 행은 21:06:09.197이다.
  마지막 30행은 모두 `success / fresh / valid`, 마지막 행 온도 quality는 ok, 이미지 연결은 fresh다.
- CSV SHA256: `D5AA0F9736F5615F10FC7215D464A52B184F05802A1C3D1DEAF709F8174D59A1`.
- 개발 증거: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_BACKUP_R4_evidence\resume-20260920-2107\resume-observation.json`.

이는 기존 운영 수집 재개와 회수 구간의 쓰기 확인이다. 세션 전체 종료 검산, 전체 백업/복원 검증,
후보 현장 검증 통과를 의미하지 않는다. 중단 중 수집 공백을 복원했다고 보고하지 않는다.
부분 백업은 그대로 보존하고 미완료로 취급한다. 다음 전환 준비는 위 제한된 범위로 진행한다.

## 이전 R4 준비와 R3 실행 기록

사용자가 R3를 실행했다. 2026-09-20 17:45:25 +09:00 결과는
`HOLD / live-capacity-inventory / path-length`다. `normal_close_requested=false`,
`stopped_confirmed=false`, `candidate_started=false`, `installation_started=false`를 확인했다.
결과를 서버 탐색기로 회수했으며 파일 SHA256은 화면/sidecar와 일치한다:
`597A867380E325B7739762E0E284312B1A90CCACD071EE2314A934566AA9706F`.
R3 실패 당시 운영 앱은 계속 실행 중이었다. 화면의 약 50만 파일·41GB는 실패 전 중간 집계이며 전체 용량이 아니다.
R3 영수증은 원본/목적지 중 어느 경로가 길었는지 구분하지 않으므로 원인을 확정하지 않는다.

새 **R4**는 결과를 `Desktop\SmartFactory\B<6자리>`에 만들고 `b`(백업), `r`(복원 검산)을 사용한다.
현재 사용자 경로에서 사본의 `r0` 포함 접두부는 47자, 원본 루트는 48/53/60자다.
상수를 믿지 않고 실제 경로 길이를 각 원본과 비교한다. 따라서 엔진이 지원하는 240자 이하 원본은
복사 때문에 더 길어지지 않는다. 원본 자체가 240자를 초과하면 기존 제한대로 종료 전에 HOLD한다.
새 자식에만 기존 ReportAcl을 적용하고 부모 ACL·원본·R3 증거는 유지한다.
이름 충돌 시 기존 폴더를 재사용하지 않는다. `B*`라는 이름은 삭제/정리 근거가 아니다.

- 보존된 서버 실행 폴더: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_BACKUP_R4`
- 실행 파일: `RUN_COLD_BACKUP.cmd` — 전체 백업 범위 중단에 따라 재실행 안내 대상이 아니다.
- helper SHA256: `4819A6A2C19FA1AA638779C2AC221ED1D13D1B10A386FC51E13601A25E9223F7`
- CMD SHA256: `791D8DC691FDAB00F114A945096A5B5470B6D1707E6636BE6926C1BF738DAA7E`
- 개발 기록: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_BACKUP_R4_evidence`

R4 경계 시험 45개, CMD 정상/변조/누락 3개가 통과했다. 실제 240자 원본이 긴 목적지에서 거절되는 상황을
재현하고, 짧은 목적지에서 Inventory→Backup→Restore→원본/복원본 전수 재해시를 수행했다.
기존 엔진 DLL은 동일하며 이전 58개 엔진 시험 근거를 유지한다. 읽기 전용 독립 R4 검토에서도 차단 결함이 없다.
`run-info.json`과 HOLD에 bundle/helper hash/runRoot/원본 매핑을 남긴다.
서버 최종 로컬 복사와 사본 왕복 해시 검산도 완료했다. 최종 영수증은 R4 개발 기록의 `server-delivery-receipt.json`이다.
이 전달 기록 작성 시점에는 R4 미실행이었다. 이후 실제 실행은 5/7 backup-copy에서 사용자 중단했고,
기존 운영 앱을 재개했다. 현재 상태는 문서 상단 기록을 따른다. 후보 현장시험은 아직 수행하지 않았다.

## 이전 R3 묶음과 전달 기록

- 서버 최종 폴더: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_BACKUP_R3`
- 실행 파일: `RUN_COLD_BACKUP.cmd` — 사용자가 우클릭하여 관리자 권한으로 실행.
- 개발 검증 기록: `C:\Users\user\Desktop\SmartFactory\SFL_TRC_BACKUP_R3_evidence`
- helper SHA256: `5341B1CF24E8BB1CD6CC203B14DA523DB9B89714B5C51EACF7B0B71F0C356E7A`
- CMD SHA256: `973AE810B4218FE5107560B08F98FF74F10C4CEC0BEC86C29178E48FD48CE79E`
- 엔진 SHA256: `3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71`

개발 PC → Z 전송 → Chrome 원격 데스크톱 탐색기에서 서버 로컬 복사 → 별도 Z 폴더로 서버 사본 회수를 완료했다.
6개 파일, 530,372바이트를 개발 원본과 대조해 크기·SHA256 불일치 0을 확인했다.
최종 근거는 개발 검증 폴더의 `server-delivery-receipt.json`이다.
R1/R2는 개발 검증 중간본이며 서버에 전달하지 않았다. 기존 해시 결합 묶음은 수정하지 않았다.

## 이전 전체 백업의 실행 순서와 실패 처리

1. PS5.1 관리자/운영 계정, Desktop 로컬 NTFS, d7a1b20 설치 1,646개 파일, 설정 해시,
   실행 경로·PID·시작 시각·사용자 토큰·backend 부모·8000 소유자, 복귀 NSIS를 확인한다.
2. 운영 앱이 실행 중인 상태에서 세 루트 전체를 집계하고 최종 복원 경로의 길이와 실제 여유 공간을 확인한다.
   필요한 공간은 `2.1 × 원본 bytes + 항목 수 × 16 KiB + 10 GiB`다. 부족하면 종료 요청 전에 HOLD한다.
3. 새 결과 폴더 ACL/기록 생성까지 성공한 뒤, 설정·프로세스·용량을 다시 확인하고 정상 창 닫기를 1회 요청한다.
   앱의 390초 종료 예산에 여유를 둬 450초 기다린다. helper의 강제 종료는 없다.
4. 보존한 프로세스 핸들의 exit 0, 같은 세션의 fresh shutdown-complete/forced=false,
   실패 이벤트 부재, 모든 앱/backend/8000 부재, 이미지 final manifest/fact SHA를 확인한다.
5. 중단 상태에서 다시 집계·용량 확인 → 새 backup 복사 → 별도 restore 복사 → 원본과 restore 전수 재해시·구성 검산.
6. `result.json` 또는 `hold.json`과 SHA를 남긴다. 종료 이후 실패하면 앱이 중단된 채 남을 수 있다.
   자동 재시작·설치·후보 실행·삭제·원본 복원·설정/attestation 변경은 없다.

세 루트는 backend AppData `SmartFactoryLogger`, Electron profile `smart-factory-logger-v2`,
설치 폴더 `smart-factory-logger-v2`다. 설정 API의 log/snapshot/image 경로가 이 루트에 해당하는지 확인한다.
이 검사는 모든 활성 runtime 저장 경로를 독립 증명하지 않으므로 `all_runtime_storage_paths_proven=false`를 유지한다.

## 검증 결과

- 기존 검증 엔진 DLL 그대로 사용: native Windows PowerShell 5.1 엔진 시험 58개 통과.
- 새 생성 helper 경계 시험 38개 통과: runtime/config/용량/창 실패 시 close 0회, 정상 1회,
  close false 반환·조회 실패·잔류 프로세스/포트·강제 종료·다른 PID/session·오래된 closeout·fact 해시 불일치 거절.
- 실제 guard AST를 CMD와 같은 중첩 scriptblock 호출에서 실행하고 실제 Engine.Inventory의 Live→Cold 전환을 확인.
- 실제 CMD 구조를 무해한 fixture로 시험: 정상 실행, 변조 거부, 누락 거부 3개 통과.
  공백·한글·특수문자 경로, 다른 현재 디렉터리를 포함한다.
- 읽기 전용 독립 검토에서 발견한 callback 상태 범위 불일치를 수정했다. R3 재검토에서 추가 차단 결함 없음.
- 제품 소스/빌드 변경이 없어 전체 제품 health를 반복하지 않았다.
- 실제 서버 도우미 실행, 정상 종료, 실제 운영 ACL 생성, 현장 백업, 앱 기능 복원은 아직 수행하지 않았다.

## 위험과 후속 시험

운영 영향은 높다. 누적 이미지·CSV가 크면 백업이 수십 분 이상 중단 시간을 차지할 수 있다.
대략 원본 크기의 4배 읽기·2배 쓰기가 필요하다. 공간 검사는 예약이 아니며 복사 중에도 여유를 확인한다.
원본과 두 사본은 같은 디스크에 있다. 파일 복원 검산은 실제 앱 기능 복원·재해 복구·VSS·원본 ACL 복원을 대신하지 않는다.
주기적 프로세스 확인은 적대적인 파일 경로 교체나 순간 실행을 완전히 막지 못한다.

후보 단계는 기존 d7a1b20 설치와 데이터를 보존하고, 별도 config/state/profile/CSV/fact/spool/image 경로를 사용한다.
일반 권한으로 실행하며 8000 포트는 기존 앱 종료 후 사용한다. 복귀는 원래 d7a1b20 설치·데이터 기준이며
후보 schema 2.5.1 파일에 구버전이 append하지 않도록 한다. NSIS 설치/데이터 migration은 이 단계에서 수행하지 않는다.
fingerprint_mismatch, effective verified=false, comparator 검증 상태와 async_fact_only 제한을 유지한다.

## 수동 실행이 필요한 이유

Computer Use의 [SKILL.md](C:/Users/user/.codex/plugins/cache/openai-bundled/computer-use/26.915.31945/skills/computer-use/SKILL.md)가
요구하는 [guidance.md](C:/Users/user/.codex/plugins/cache/openai-bundled/computer-use/26.915.31945/docs/guidance.md)는
“Do not run Windows terminal commands via UI automation directly or indirectly.”라고 제한한다.
따라서 Codex는 서버 최종 복사·검산까지 완료하고, 사용자가 CMD 실행을 한 번 시작해야 한다.
이는 진행 승인을 다시 요구하는 절차가 아니다. 실행 후 Codex가 결과 파일을 회수·검토한다.
