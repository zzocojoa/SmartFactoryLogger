from pydantic import BaseModel, field_validator, ValidationInfo
from typing import Optional, Dict, Any

class FactoryData(BaseModel):
    # System
    Time: str
    Status: str = "Running"
    
    # KPIs
    Speed: Optional[float] = None
    Press: Optional[float] = None
    Count: Optional[int] = None
    EndPos: Optional[float] = None
    Billet_Length: Optional[float] = None
    Die_ID: Optional[str] = None
    Billet_Cycle_ID: Optional[str] = None
    
    # Temperatures
    Spot: Optional[float] = None
    Temp_F: Optional[float] = None
    Temp_B: Optional[float] = None
    Billet_Temp: Optional[float] = None
    
    # Molds
    Mold1: Optional[float] = None
    Mold2: Optional[float] = None
    Mold3: Optional[float] = None
    Mold4: Optional[float] = None
    Mold5: Optional[float] = None
    Mold6: Optional[float] = None
    
    # Environment
    At_Temp: Optional[float] = None
    At_Pre: Optional[float] = None

    # Computed status (backend-derived)
    Computed: Optional[Dict[str, Any]] = None

    @field_validator(
        "Speed",
        "Press",
        "EndPos",
        "Billet_Length",
        "Temp_F",
        "Temp_B",
        "Billet_Temp",
        "Mold1",
        "Mold2",
        "Mold3",
        "Mold4",
        "Mold5",
        "Mold6",
        "At_Temp",
        "At_Pre",
        "Spot",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def coerce_float(cls, value, info: ValidationInfo):
        if value is None or value == "":
            return None
        try:
            val = float(value)
        except Exception:
            return None
        name = info.field_name

        if name in {"At_Temp"}:
            if not (-40 <= val <= 100):
                return None
            return val
        if name in {"At_Pre"}:
            if not (0 <= val <= 100):
                return None
            return val
        if name in {"Spot"}:
            if val > 2000:
                return None
            return val
        if name in {"Temp_F", "Temp_B"}:
            if not (0 <= val <= 1000):
                return None
            return val
        if name in {"Billet_Temp", "Mold1", "Mold2", "Mold3", "Mold4", "Mold5", "Mold6"}:
            if not (0 <= val <= 1000):
                return None
            return val
        if val < 0:
            return None
        return val

    @field_validator("Count", mode="before")
    @classmethod
    def coerce_int(cls, value):
        if value is None or value == "":
            return None
        try:
            val = int(value)
        except Exception:
            return None
        if val < 0:
            return None
        return val

class SystemStatus(BaseModel):
    connection: bool
    mode: str  # REAL / MOCK
    message: str
