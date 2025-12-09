from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any

# 압출기 데이터 모델
class ExtruderData(BaseModel):
    Press: Optional[float] = Field(None, ge=0.0, description="메인 압력")
    Temp_F: Optional[float] = Field(None, ge=0.0, le=1000.0, description="컨테이너 앞 온도")
    Temp_B: Optional[float] = Field(None, ge=0.0, le=1000.0, description="컨테이너 뒤 온도")
    Speed: Optional[float] = Field(None, ge=0.0, description="압출 속도")
    EndPos: Optional[float] = Field(None, ge=0.0, description="종료 위치")
    Count: Optional[int] = Field(None, ge=0, description="생산 카운트")
    Billet: Optional[int] = Field(None, ge=0, description="빌렛 길이")

# SPOT 데이터 모델
class SpotData(BaseModel):
    temperature: Optional[float] = None

    @validator('temperature')
    def check_range(cls, v):
        # 2000도 초과는 에러(None) 처리
        if v is not None and v > 2000.0:
            return None
        return v

# LS PLC 데이터 모델
class LSPLCData(BaseModel):
    # 명시적 필드 정의 (검증 강화)
    Mold1: Optional[int] = Field(None, ge=0, le=1000, description="금형1 온도")
    Mold2: Optional[int] = Field(None, ge=0, le=1000)
    Mold3: Optional[int] = Field(None, ge=0, le=1000)
    Mold4: Optional[int] = Field(None, ge=0, le=1000)
    Mold5: Optional[int] = Field(None, ge=0, le=1000)
    Mold6: Optional[int] = Field(None, ge=0, le=1000)
    
    Billet_Temp: Optional[int] = Field(None, ge=0, le=1000, description="빌렛 온도")
    At_Pre: Optional[float] = Field(None, ge=0.0, description="공기압/습도")
    At_Temp: Optional[float] = Field(None, ge=-50.0, le=100.0, description="대기 온도")

    # 동적 필드 허용 (config.ini에 따라 키가 변할 수 있음)
    class Config:
        extra = 'allow'
