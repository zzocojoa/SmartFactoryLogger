from pydantic import BaseModel, Field, validator, field_validator, ValidationInfo
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
    # 명시적 필드 정의 (검증 강화 -> Soft Validation으로 변경)
    # 기존 strict constraints(le=1000) 제거 -> validator에서 처리
    Mold1: Optional[int] = Field(None, description="금형1 온도")
    Mold2: Optional[int] = Field(None)
    Mold3: Optional[int] = Field(None)
    Mold4: Optional[int] = Field(None)
    Mold5: Optional[int] = Field(None)
    Mold6: Optional[int] = Field(None)
    
    Billet_Temp: Optional[int] = Field(None, description="빌렛 온도")
    At_Pre: Optional[float] = Field(None, description="공기압/습도")
    At_Temp: Optional[float] = Field(None, description="대기 온도")

    # 동적 필드 허용
    class Config:
        extra = 'allow'

    @field_validator('Mold1', 'Mold2', 'Mold3', 'Mold4', 'Mold5', 'Mold6', 'Billet_Temp', check_fields=False)
    @classmethod
    def validate_temp_range(cls, v, info: ValidationInfo):
        """
        Soft Validation:
        범위를 벗어난 값이 들어오면 에러를 발생시키는 대신(System Crash),
        None을 반환하고 로그를 남겨 시스템 지속성을 보장함.
        """
        if v is None:
            return None
        
        # 물리적 한계 (0 ~ 1000도)
        if not (0 <= v <= 1000):
            # Console에만 출력하거나, 필요 시 sys_logger 연결 가능
            # 여기서는 Pydantic 모델 내부이므로 print로 경고만 남김 (상위에서 로깅됨)
            print(f"[Schema Warning] {info.field_name} value {v} is out of range (0-1000). Set to None.")
            return None
        return v
