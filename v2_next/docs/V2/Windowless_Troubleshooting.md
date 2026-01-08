# Windowless (시스템 트레이) 모드 배포 트러블슈팅

## 1. 개요

Smart Factory Logger V2를 **"Windowless (콘솔 창 없음)"** 모드로 배포하여 시스템
트레이 아이콘으로 실행했을 때, 애플리케이션이 실행되지 않거나 웹 대시보드 접근
시 `Connection Refused` 오류가 발생하는 문제를 해결한 과정입니다.

## 2. 발생했던 문제

### 증상 1: PermissionError (Log Rotation)

- **현상:** 로그 파일 로테이션(Rename) 시점에 권한 오류로 인해 애플리케이션이
  크래시(Crash) 발생.
- **원인:** Windows 파일 잠금 특성상, 열려 있는 로그 파일의 이름을 변경할 수
  없음.
- **해결:** `backend/app.py`에 `SafeRotatingFileHandler` 구현. 권한 오류 발생 시
  로테이션을 건너뛰고 기존 파일에 계속 기록하여 크래시 방지.

### 증상 2: Connection Refused (Windowless Mode)

- **현상:** `deploy.ps1`으로 빌드 후 실행 시, 트레이 아이콘은 뜨지만 웹
  브라우저에서 `localhost:8000` 접속 불가.
- **로그 분석:**
  ```text
  AttributeError: 'StreamLogger' object has no attribute 'isatty'
  ```
- **원인:**
  1. Windowless(`noconsole`) 모드에서는 `sys.stdout`, `sys.stderr`가 `None`으로
     설정됨.
  2. 이를 해결하고자 파일로 리다이렉트했으나, `uvicorn` 로거 설정 과정에서
     스트림의 `isatty()` 메서드를 호출함.
  3. 리다이렉트된 커스텀 클래스(`StreamLogger`)에 `isatty()`가 없어 서버 초기화
     중 충돌 발생.
  4. 추가적으로 `sys.stdin`이 `None`일 때 입력을 시도하면 즉시 종료되는 문제
     존재.

## 3. 해결 조치 (`server_entry.py`)

애플리케이션 진입점인 `backend/server_entry.py`에 다음과 같은 안전장치를
적용했습니다.

### 3.1 표준 입력(Stdin) 차단

입력 스트림이 없을 경우 `os.devnull`(Null 장치)로 연결하여 읽기 오류를
방지합니다.

```python
if sys.stdin is None or sys.stdin.fileno() < 0:
    sys.stdin = open(os.devnull, "r")
```

### 3.2 표준 출력/에러(Stdout/Stderr) 리다이렉트 및 호환성 확보

`sys.stdout`, `sys.stderr`를 로그 파일(`Server_stdout.log`)로 연결하되,
`uvicorn`과의 호환성을 위해 `isatty()` 및 `fileno()` 메서드를 구현했습니다.

```python
class StreamToLogger:
    def __init__(self, path):
        self.file = open(path, "a", encoding="utf-8", buffering=1)
    
    def write(self, buf):
        # ... (파일 쓰기 로직) ...
    
    def isatty(self):
        return False  # 중요: 터미널이 아님을 명시
        
    def fileno(self):
        return self.file.fileno()

# 리다이렉트 적용
sys.stdout = StreamToLogger(stdout_path)
sys.stderr = StreamToLogger(stderr_path)
```

### 3.3 Multiprocessing Freeze Support

PyInstaller 단일 파일 실행 시 멀티프로세싱 지원을 위해 진입점 최상단에 호출을
추가했습니다.

```python
if __name__ == "__main__":
    multiprocessing.freeze_support()
```

## 4. 결론

이 조치를 통해 **콘솔 창 없이(Windowless)** 실행되는 환경에서도 서버가
안정적으로 시작되며, 발생하는 모든 로그와 에러는
`%APPDATA%\SmartFactoryLogger\logs` 경로에 안전하게 기록됩니다.
