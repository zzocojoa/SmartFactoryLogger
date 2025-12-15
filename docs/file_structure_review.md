# 파일 구조 재정비 검토 보고서

**작성일**: 2025-12-15 **작성자**: Antigravity (AI Intelligent Assistant)

## 1. 현황 분석 (Current Status)

현재 루트 디렉토리(`./`)에는 실행 코드, 설정, 문서, 리소스 파일이 혼재되어
있습니다. 프로젝트 초기에 빠른 개발을 위해 필요한 구조였으나, 기능이 확장되고
파일 수가 20개를 넘어가면서 관리 효율성이 저하될 우려가 있습니다.

### 주요 문제점

1. **가독성 저하**: `main.py`와 `gui.py`, `config.py` 등 핵심 소스 코드가 루트에
   노출되어 있어, 프로젝트의 진입점을 찾거나 전체 구조를 파악하기 어렵습니다.
2. **설정 관리의 모호함**: `config.ini` (배포 설정)와 `config.py` (로직 설정),
   `repro_config.py` 등이 섞여 있어 설정의 성격 분리가 명확하지 않습니다.
3. **리소스 분산**: 아이콘 파일(`icon.ico`, `icon.png`)과 문서 파일(`PDF`)이
   루트에 흩어져 있습니다.

## 2. 재정비 제안 (Restructuring Proposal)

실무 관점에서 유지보수성과 확장성을 고려하여 다음과 같은 구조 변경을 제안합니다.

### 제안 구조 (Proposed Tree)

```text
Project_Root/
├── src/                    # [New] 소스 코드 전용 폴더
│   ├── main.py             # 진입점 이동
│   ├── gui.py
│   ├── settings_gui.py
│   ├── config.py
│   ├── config_schema.py
│   └── modules/            # 기존 modules 이동
├── config/                 # [New] 설정 파일 관리
│   ├── config.ini          # 배포용 기본 설정
│   └── repro_config.py
├── assets/                 # [New] 리소스 폴더
│   ├── icon.ico
│   └── icon.png
├── docs/                   # [New] 문서 폴더
│   ├── manuals/            # PDF 등 매뉴얼
│   └── reports/            # 기술 검토 보고서 등
├── logs/                   # (기존 유지)
├── tests/                  # (기존 유지)
├── requirements.txt
├── README.md
├── start.sh
└── crash.log               # (시스템 로그)
```

## 3. 실행 계획 (Action Plan)

이 구조 변경은 **코드의 import 경로 수정**을 동반하므로, 신중하게 진행해야
합니다.

1. **폴더 생성**: `src`, `assets`, `docs` 폴더 생성
2. **파일 이동**: 소스 코드 및 리소스 이동
3. **코드 수정**:
   - `main.py` 내의 `sys.path` 조정 또는 상대 경로 import 수정
   - `PyInstaller` 스펙 파일(`SmartFactoryLogger.spec`) 내의 경로 수정
4. **검증**: 실행 테스트 및 빌드 테스트

## 4. 결론 (Conclusion)

현재 프로젝트는 "초기 개발" 단계를 지나 "운영 및 유지보수" 단계로 진입하고
있습니다. 장기적인 프로젝트 관리를 위해 **폴더 구조 재정비는 필요한
시점**입니다. 다만, 당장 운영에 지장이 없다면 **차기 메이저 업데이트(v2.0 등)
시점**에 적용하는 것을 권장합니다.
