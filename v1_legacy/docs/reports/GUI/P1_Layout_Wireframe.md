# GUI P1 레이아웃 와이어프레임 (Wireframe)

이미지 로딩 문제로 인해, 텍스트 기반의 다이어그램(Mermaid)으로 화면 구성을
명확히 시각화합니다.

## 레이아웃 구조도

```mermaid
graph TD
    classDef container fill:#2d2d2d,stroke:#555,color:white;
    classDef sidebar fill:#252526,stroke:#333,color:white;
    classDef header fill:#007acc,stroke:#333,color:white,height:40px;
    classDef card fill:#333,stroke:#444,color:white;
    classDef gauge fill:#252526,stroke:#4ec9b0,stroke-width:2px,color:white;

    subgraph "전체 화면 (1920x1080)"
        
        %% 1. 상단 상태바
        Header[🟦 상단 상태 바 / Status Bar]:::header
        
        subgraph "콘텐츠 영역 (Row 2)"
            direction LR
            
            %% 2. 좌측 사이드바 (핵심 운전 지표)
            subgraph "좌측 사이드바 (Left Column)"
                MainP((🟢 Main Press)):::gauge
                Speed((🟢 Speed)):::gauge
                Count[Output Count]:::card
                Pos[End Position]:::card
            end

            %% 3. 메인 그리드 (온도 모니터링)
            subgraph "메인 그리드 (Right Area)"
                direction TB
                
                %% 상단: 가장 중요한 SPOT 온도
                SPOT[🔥 SPOT Temp (Large Card)]:::card
                
                %% 중앙: 금형 온도 그리드
                subgraph "금형 온도 (Mold Temp Grid)"
                    direction LR
                    M1[Mold 1]:::card
                    M2[Mold 2]:::card
                    M3[Mold 3]:::card
                    M4[Mold 4]:::card
                    M5[Mold 5]:::card
                    M6[Mold 6]:::card
                end
                
                %% 하단: 그래프
                Graph[📈 Real-time Trend Graph (Wide)]:::card
            end
        end
    end

    style Header width:100%
    style SPOT width:100%,height:150px
```

## 구성 설명

1. **좌측 사이드바 (운전 지표)**:
   - **형태**: 세로로 긴 컬럼.
   - **내용**: 운영자가 기계를 조작하며 가장 자주 보는 **압력(Pressure)**과
     **속도(Speed)**를 큼직한 **원형 게이지(Gauge)**로 최상단에 배치합니다.
2. **중앙 상단 (핵심 온도)**:
   - **형태**: 가장 눈에 띄는 대형 카드.
   - **내용**: 품질에 직결되는 **SPOT 온도**를 그래프(스파크라인)와 함께
     배치하여 즉각적인 이상 감지를 유도합니다.
3. **우측/중앙 (상세 온도)**:
   - **형태**: 작은 카드들의 바둑판비율(Grid).
   - **내용**: **금형(Mold) 1~6번** 온도를 2열 또는 3열로 정돈합니다. 정상일 땐
     존재감이 없다가, 이상 발생 시에만 붉게 강조됩니다.
