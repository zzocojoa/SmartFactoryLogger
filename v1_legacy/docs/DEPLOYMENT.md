# 스마트팩토리로거 배포 및 이식 가이드 (Deployment Guide)

본 가이드는 **개발 PC에서 실행 파일(.exe)을 만든 후**, 이를 **현장 설비 PC로
복사하여 실행**하는 절차를 설명합니다.

> 🚨 **핵심 요약**
>
> - **개발 PC**: Python 설치, 라이브러리 설치, 빌드(`pyinstaller`) 수행 필요.
> - **현장 PC (유저)**: Python 설치 **불필요**. 오직 생성된
>   `SmartFactoryLogger.exe` 파일만 있으면 됩니다.

## 1. 개발 PC에서 수행: 실행 파일 만들기 (Build)

이 단계는 Python 3.12가 설치된 **개발자의 컴퓨터**에서 수행합니다.

### 1-1. Python 환경 및 라이브러리 준비

반드시 **Python 3.12** 환경이어야 합니다.

```powershell
# 개발 PC 터미널에서 실행
# 1. pip 업그레이드
python -m pip install --upgrade pip

# 2. 필수 패키지 및 PyInstaller 설치
pip install -r requirements.txt
pip install pyinstaller
```

### 1-2. 빌드 실행

프로젝트 루트 폴더(`SmartFactoryLogger`)에서 아래 명령어를 실행하여 실행
파일(.exe)을 생성합니다.

```powershell
python -m PyInstaller --clean --noconfirm SmartFactoryLogger.spec
```

### 1-3. 결과물 확인

빌드가 성공하면 프로젝트 내 **`dist`** 폴더 안에 **`SmartFactoryLogger.exe`**
파일이 생성됩니다. 이 파일 하나에 모든 프로그램 기능이 압축되어 있습니다.

---

## 2. 현장 PC에서 수행: 이식 및 실행 (Deploy)

이 단계는 **현장 설비 컴퓨터**에서 수행합니다. **Python 설치가 필요 없습니다.**

### 2-1. 파일 복사

개발 PC의 `dist` 폴더에 있던 파일들을 USB나 네트워크를 통해 현장 PC로
복사합니다.

1. **`SmartFactoryLogger.exe`** (필수)
   - 이 파일을 현장 PC의 원하는 폴더(예: `D:\SmartFactoryLogger`)에 넣습니다.
2. (선택) **`config/config.ini`**
   - 기본 설정값을 변경해서 배포하고 싶다면 이 파일도 같이 `config` 폴더를
     만들어 넣어주세요. (없으면 실행 시 자동 생성됩니다.)

### 2-2. 프로그램 실행

현장 PC에서 `SmartFactoryLogger.exe`를 더블 클릭하여 실행합니다.

### 2-3. 초기 설정

프로그램이 실행되면 우측 상단의 **설정(⚙️) 버튼**을 눌러 현장 상황(PLC IP 등)에
맞게 환경 설정을 마칩니다.

### 2-4. 주의 사항

- **방화벽**: 프로그램이 네트워크 장비(PLC)와 통신할 수 있도록 방화벽 팝업이
  뜨면 '허용'을 눌러주세요.
- **해상도**: 본 프로그램은 1920x1080 해상도에 최적화되어 있습니다.
