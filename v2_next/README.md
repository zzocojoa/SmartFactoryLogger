# SmartFactoryLogger V2 (v2_next)

이 문서는 v2_next 폴더를 현장 이식 PC로 복사(Z:)하여 실행하는 기본 절차를
정리합니다.

## 1) Z: 드라이브로 복사

아래 명령은 **개발 PC**에서 실행합니다. (이식 PC로 직접 복사하지 않는 경우)

```powershell
# 전체 v2_next 복사 (권장)
robocopy C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next Z:\v2_next /E /XD node_modules .git __pycache__ /XF *.pyc

# 백엔드만 복사 (필요 시)
robocopy C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\backend Z:\v2_next\backend /E /XD __pycache__ /XF *.pyc

# 프론트엔드만 복사 (필요 시)
robocopy C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\frontend Z:\v2_next\frontend /E /XD node_modules .git /XF *.log
```

## 1-1) NAS(Z:) -> Desktop 복사 (이식 PC)

Z: 드라이브가 NAS일 때는 **작은 파일이 많으면 복사가 매우 느립니다**.
`node_modules` 등 불필요 폴더를 제외하고 Desktop으로 복사한 뒤, 필요한 의존성은
로컬에서 다시 설치하는 방식을 권장합니다.

```powershell
# 백엔드만 빠르게 복사
robocopy Z:\v2_next\backend C:\Users\user\Desktop\v2_next\backend /E /MT:32 /R:2 /W:1 /XD __pycache__ /XF *.pyc

# 프론트까지 필요할 경우 (node_modules 제외)
robocopy Z:\v2_next C:\Users\user\Desktop\v2_next /E /MT:32 /R:2 /W:1 /XD node_modules .git __pycache__ /XF *.pyc *.log
```

복사 후 프론트가 필요하면 Desktop에서 다시 설치합니다.

```powershell
cd C:\Users\user\Desktop\v2_next\frontend
npm install
```

이후 업데이트는 증분 복사로 빠르게 동기화합니다.

```powershell
robocopy Z:\v2_next C:\Users\user\Desktop\v2_next /E /XO /XN /XC /MT:32 /R:2 /W:1 /XD node_modules .git __pycache__
```

## 2) 실행 환경 변수 (이식 PC)

이식 PC에서 아래와 같이 환경 변수를 지정합니다.

```powershell
$env:SFL_CONFIG_PATH="C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini"
$env:V2_MODE="REAL"
```

## 3) 백엔드 실행 (이식 PC)

반드시 `v2_next` 루트에서 실행해야 합니다. (`backend` 폴더 안에서 실행하면
import 오류가 발생합니다.)

```powershell
# Z:에서 실행할 때
cd /d Z:\v2_next
python -m backend.main

# Desktop에서 실행할 때
cd /d C:\Users\user\Desktop\v2_next
python -m backend.main
```

정상 실행 시 `http://127.0.0.1:8000/health`에 응답이 나옵니다.

## 4) 프론트엔드 실행 (이식 PC, 선택)

```powershell
# Z:에서 실행할 때
cd /d Z:\v2_next\frontend
npm start

# Desktop에서 실행할 때
cd /d C:\Users\user\Desktop\v2_next\frontend
npm start
```

브라우저에서 `http://localhost:3000`을 확인합니다.

## 5) 참고

- `config.ini`는 **이식 PC의 경로**를 사용해야 합니다.
- SPOT 카메라/포커스 관련 값은 `[SPOT]` 섹션을 사용합니다.

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

cd frontend; npm run build; cd ..; npm run dist
