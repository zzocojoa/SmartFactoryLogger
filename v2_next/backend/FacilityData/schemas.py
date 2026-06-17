import re
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import Optional, Dict, Any

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")
PRODUCT_NO_RE = re.compile(r"^DW-[A-Za-z0-9][A-Za-z0-9._-]{0,36}$")
OPERATOR_MOLD_NO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def _normalize_operator_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


class OperatorMetadataBase(BaseModel):
    product_no: str = ""
    operator_mold_no: str = ""

    @field_validator("product_no", "operator_mold_no", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return _normalize_operator_text(value)

    @field_validator("product_no")
    @classmethod
    def validate_product_no(cls, value: str) -> str:
        if not value:
            return ""
        if _has_control_character(value):
            raise ValueError("product_no must not contain control characters")
        if value[0] in CSV_INJECTION_PREFIXES:
            raise ValueError("product_no must not start with a CSV formula character")
        if not PRODUCT_NO_RE.match(value):
            raise ValueError("product_no must match DW- followed by 1-37 letters, digits, dots, underscores, or hyphens")
        return value

    @field_validator("operator_mold_no")
    @classmethod
    def validate_operator_mold_no(cls, value: str) -> str:
        if not value:
            return ""
        if _has_control_character(value):
            raise ValueError("operator_mold_no must not contain control characters")
        if value[0] in CSV_INJECTION_PREFIXES:
            raise ValueError("operator_mold_no must not start with a CSV formula character")
        if not OPERATOR_MOLD_NO_RE.match(value):
            raise ValueError("operator_mold_no must be 1-32 characters and start with a letter or digit")
        return value


class OperatorMetadataUpdate(OperatorMetadataBase):
    @model_validator(mode="after")
    def require_required_fields(self):
        if not self.product_no or not self.operator_mold_no:
            raise ValueError("product_no and operator_mold_no are required")
        return self


class OperatorMetadata(OperatorMetadataBase):
    valid: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    updated_at: Optional[str] = None
    source: str = "operator_input"

    @model_validator(mode="after")
    def derive_validity(self):
        missing: list[str] = []
        if not self.product_no:
            missing.append("product_no")
        if not self.operator_mold_no:
            missing.append("operator_mold_no")
        self.missing_fields = missing
        self.valid = not missing
        return self

class FactoryData(BaseModel):
    # System
    Time: str
    Status: str = "Running"
    timestamp_ms: Optional[int] = None
    captured_at_extruder: Optional[float] = None
    captured_at_ls: Optional[float] = None
    captured_at_spot: Optional[float] = None
    extruder_snapshot_error: Optional[str] = None
    ls_snapshot_error: Optional[str] = None
    spot_snapshot_error: Optional[str] = None
    
    # KPIs
    Speed: Optional[float] = None
    Press: Optional[float] = None
    Count: Optional[int] = None
    EndPos: Optional[float] = None
    MainRamPosition_D0010: Optional[float] = None
    ContainerPosition_D0012: Optional[float] = None
    Billet_Length: Optional[float] = None
    Die_ID: Optional[str] = None
    Billet_Cycle_ID: Optional[str] = None
    Die_ID_derived: Optional[bool] = None
    Billet_Cycle_ID_derived: Optional[bool] = None
    derivation_version: Optional[str] = None
    cycle_confidence: Optional[float] = None
    cycle_state: Optional[str] = None
    Product_No_operator: Optional[str] = None
    Mold_No_operator: Optional[str] = None
    operator_metadata_valid: Optional[bool] = None
    operator_metadata_missing_fields: Optional[list[str]] = None
    operator_metadata_updated_at: Optional[str] = None
    
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
        "MainRamPosition_D0010",
        "ContainerPosition_D0012",
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


class FactoryDataHistorySample(BaseModel):
    timestamp_ms: int
    data: FactoryData


class FactoryDataHistoryResponse(BaseModel):
    samples: list[FactoryDataHistorySample]
    oldest_timestamp_ms: Optional[int] = None
    newest_timestamp_ms: Optional[int] = None
    history_instance_id: str
    truncated: bool
