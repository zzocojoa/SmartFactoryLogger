# CSV daily rollover 운영 메모

## 변경 요약

- CSV writer는 서버 로컬 calendar day 기준으로 파일을 나눈다.
- 자정 이후 첫 row는 새 v1 CSV, 새 v2 CSV, 새 v2 metadata sidecar로 기록된다.
- 파일명은 각 daily 파일에 처음 쓰인 row timestamp를 사용한다.
- v2 `sample_seq`는 앱 실행 세션 단위로 계속 증가하며, 자정에 1로 reset하지 않는다.

## 운영자가 확인할 것

- 하루를 넘긴 수집 폴더에는 날짜별 CSV 파일이 여러 개 생기는 것이 정상이다.
- downstream 수집, Excel 작업, replay parser는 v1 daily CSV 전체와 v2 daily CSV 전체를 분리해서 모두 읽어야 한다.
- v1 대상은 `Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv` 형식이고, v2 대상은 `Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv` 형식이다.
- v2를 사용하는 경우 각 `Factory_Integrated_Log_v2_*.csv`와 같은 timestamp suffix의 `.metadata.json` 파일이 같이 있어야 한다.
- 자정 직전 write/flush 실패가 있으면 새 날짜 row는 기존 날짜 파일에 섞이지 않고 보류된다.
  복구 후 새 날짜 파일에 기록되므로, warning 로그와 queue 적체 여부를 같이 확인한다.
- 종료 중 보류 row가 있으면 앱은 이전 날짜 final flush를 먼저 시도한다.
  final flush가 성공하면 보류 row를 새 날짜 파일에 기록한다.

## 장애 신호

- 새 날짜 row가 전날 CSV에 들어간 경우.
- v2 CSV는 있는데 같은 timestamp suffix의 metadata sidecar가 없는 경우.
- `CSV v1 daily rollover delayed`, `CSV v2 daily rollover delayed`, `CSV log queue full` warning이 반복되는 경우.
- `CSV daily rollover delayed because flush raised an exception` warning이 발생한 경우.
- `CSV deferred shutdown row was not written` warning이 발생한 경우.
- 날짜별 v1 row 합계와 v2 row 합계가 맞지 않는 경우.

## 롤백

- 가장 단순한 롤백은 daily rollover 변경 커밋을 revert하는 것이다.
- 이미 생성된 날짜별 CSV는 자동으로 합쳐지지 않는다.
- 롤백 후 downstream 처리가 단일 파일을 기대한다면 날짜별 파일을 병합하거나 해당 기간을 재수집해야 한다.
- 병합할 때는 header 중복 제거, row timestamp 순서, v1/v2 row count parity를 확인한다.
