# SmartFactoryLogger

## 개요

스마트 팩토리 데이터 수집 및 모니터링 시스템. Melsec PLC와 LS PLC 데이터를 0.2초
주기로 수집하여 대시보드 시각화 및 CSV 로깅을 수행합니다.

## 실행 방법 (Execution)

### 1️⃣ 가상 환경 활성화 (권장)

터미널에서 아래 명령어로 가상 환경을 활성화합니다.

```powershell
# Windows PowerShell
.\venv\Scripts\activate
```

### 2️⃣ 프로그램 실행

가상 환경이 활성화된 상태에서 메인 스크립트를 실행합니다.

```powershell
python src/main.py
```

### 3️⃣ 간편 실행 (Windows)

프로젝트 루트 폴더의 `start.bat` 파일을 더블 클릭하거나 터미널에서 실행하면 가상
환경 활성화와 실행을 자동으로 수행합니다.

```cmd
start.bat
```

## 주요 기능

- **실시간 대시보드**: 속도, 압력, 온도(SPOT, Mold, Billet) 모니터링.
- **상태 알림**: 시스템 연결 상태 및 이상 징후(Glow Effect) 시각화.
- **이력 조회**: 우측 상단 알림 센터를 통한 에러/경고 이력 확인.

## 개발 환경 설정

- Python 3.12+
- Dependencies: `requirements.txt` 참조
  ```bash
  pip install -r requirements.txt
  ```

## 개발 빌드 배포 (Windows)

```bash
python -m PyInstaller --clean --noconfirm SmartFactoryLogger.spec
```
