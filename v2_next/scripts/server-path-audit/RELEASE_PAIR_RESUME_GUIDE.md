# ACL 정정 후 22파일 정리 재개

## 이번 승인과 준비 상태

사용자의 “다음 단계 승인”은 보류된 R1 중복 사본 22파일 정리 재개에 해당한다.
ACL 정정 결과는 사용자 제공 콘솔 출력에서 PASS를 확인했다. 이는 개발 PC가 서버의
원본 파일을 직접 읽어 재검증한 결과가 아니다. 이번 실행문이 서버의 원래 ACL 백업과
완료 journal을 외부 고정 SHA256으로 다시 확인한 후 현재 ACL도 대조한다.

기존 삭제 ZIP·helper·core·launcher는 수정하지 않았다. 새 파일 전송이나 ZIP 생성은
필요 없다. 아래 기존 두 파일이 서버 전송 폴더에 있어야 한다.

```text
C:\Users\user\Desktop\SmartFactory\v1019-release-pair-cleanup-ready-r1.zip
C:\Users\user\Desktop\SmartFactory\v1019-release-pair-cleanup-ready-r1.zip.sha256.txt
```

ZIP: 22,604bytes / SHA256
`62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3`.
이전 1차 중복 폴더 삭제나 ACL 정정 도우미는 재실행하지 않는다.

## 실행 방법

관리자 **64비트 Windows PowerShell 5.1**에서 이번 `RUN_RELEASE_PAIR_CLEANUP_RESUME.txt`
내용 전체를 붙여넣는다. Markdown의 인용 기호나 코드 블록 표시를 포함하지 않는다.
새 `-NoProfile` 자식에서 승인된 재개 코드가 실행되므로 이전 창의 함수/정적 타입을
재사용하지 않는다. `-EncodedCommand`는 실행문에 표시된 코드를 전달하는 용도이며,
네트워크에서 코드를 가져오거나 서명/백신 설정을 변경하는 동작이 아니다.

별도 YES 입력은 없다. 승인된 범위 내 검증이 모두 통과하면 삭제까지 진행한다.
앱은 그대로 두고, 정리 대상이나 SFLOps 폴더를 다른 도구에서 동시에 변경하지 않는다.
탐색기의 권한 부여 안내를 승인하거나 ACL 정정 명령을 다시 실행하지 않는다.

## 정확한 삭제와 보존 범위

고정 부모:

`C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302`

- 삭제: `release_private_unsigned_v1_0_19_0c1ad4f_20260810_R1`의 중복 파일 22개
- 보존: `release_private_unsigned_v1_0_19_0c1ad4f_20260810_R2_clean` 전체 23개 파일
- 보존: 양쪽 고유 JSON, 모든 디렉터리, 기존 metadata/정리 기록
- 회수 예상: 157,989,430bytes(약 150.7MiB)

제품 설치·설정·수집 데이터·복구 설치본·v1.0.25/26 자료는 건드리지 않는다.
운영 API 호출, 앱 재시작, 설치, 관측, ACL 변경을 수행하지 않는다.

## 서버에서 다시 검증하는 내용

1. ACL 정정 백업/journal과 현재 관리자/SYSTEM 전용 권한을 확인한다.
2. 원래 558파일 manifest와 1차 88파일 삭제 완료 journal을 검증한다.
3. 남은 470개 원본 파일의 경로/종류/크기를 확인한다.
4. 두 배포 폴더의 46개 파일을 해시·파일 ID·ADS까지 확인하고 보존본을 잠근다.
5. 제한된 프로세스/서비스/작업/바로가기/잔존 문서 참조를 검사한다.
6. R1의 22개 삭제 핸들을 모두 확보한 다음 파일별 의도 기록을 남기며 삭제한다.
7. 보존 24파일 재해시, 전체 잔존 목록과 디렉터리 보존을 확인한다.

ACL 기록 경로:
`C:\ProgramData\SFLOps\tmp\acl-repair-72d495ebd11e41eda80603d9093a2cfe`

- before-acl.json: `90EE9F49517AF299AB7A0DBA38053C3B80806DF6E7C662BA765FA754260D9CAD`
- acl-repair.jsonl: `507678162C3521D2F7909137A92308C2C1F48EACA380865CE97B5C7D8C387C57`

이전 실행에서 일부 파일이 삭제돼 있었다면 470파일 계약이 맞지 않아 중단한다.
부분 완료를 추측해서 계속하는 기능은 없다. 참조 검색은 범위/깊이가 제한되며 전체
서버의 미사용 증명이 아니다. 대상 외 모든 잔존 파일을 전후 재해시하는 작업도 아니다.

## 결과와 복구

정상 결과: `V1019_RELEASE_PAIR_DUPLICATES_REMOVED`.
새 기록은 `C:\ProgramData\SFLOps\inventory\q19-pair-<시간>-<식별자>\cleanup.jsonl`에 저장한다.
최종 기준은 22파일 삭제, 디렉터리 삭제 0, 원본 448파일+metadata 6개 보존이다.
서버 전체 자료 정리 완료는 아니다. 완료 출력과 JOURNAL SHA256을 모두 제공한다.

영구 삭제이므로 휴지통 복원은 아니다. 삭제 파일의 주 데이터 바이트는 R2 보존본에서
PLAN의 `retained_relative_path`에 따라 복원할 수 있다. ACL·생성 시간 등 모든
메타데이터 복원을 보장하지 않으며 앱 버전 롤백과도 관계없다.

일부 삭제 후 잠금/권한/디스크/기록 오류로 HOLD될 수 있다. 해당 경우 출력과 journal을
보존하고 재실행·자동 복원·추가 삭제하지 않는다. 서버 실행 전 관리자 전체 통합 시험은
수행하지 않았으며, 로컬 합성 테스트 통과를 실제 서버 성공으로 대신하지 않는다.
