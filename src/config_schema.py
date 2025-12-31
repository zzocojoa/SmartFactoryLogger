from pydantic import BaseModel, Field, validator
from typing import Optional, Dict

class SystemConfig(BaseModel):
    DeviceName: str = Field(..., min_length=1)
    IntervalSec: float = Field(0.2, gt=0.0, description="데이터 수집 주기(초)")

    class Config:
        alias_generator = lambda s: s.lower()
        populate_by_name = True

class NetworkConfig(BaseModel):
    IP: str = Field(..., pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    Port: int = Field(..., ge=1, le=65535)

    class Config:
        alias_generator = lambda s: s.lower()
        populate_by_name = True

class SpotConfig(BaseModel):
    IP: str = Field(..., pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    # [Dual-IP Support] Actuator might be on a different IP (e.g. .60 vs .50)
    ActuatorIP: Optional[str] = Field(None, pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    Port: int = Field(80, ge=1, le=65535) # Optional, default 80
    RefreshInterval: float = Field(3.0, gt=0.0)
    ImageURL: str
    CrosshairX: float = Field(0.5, ge=0.0, le=1.0)
    CrosshairY: float = Field(0.5, ge=0.0, le=1.0)
    # [Visuals] Crosshair Customization
    CrosshairColor: str = "lime" # Foreground color
    CrosshairThickness: int = Field(2, ge=1)
    CrosshairSize: int = Field(20, ge=5) # Arm length
    CrosshairGap: int = Field(5, ge=0)   # Center gap
    FocusURL: Optional[str] = None
    FocusStep: int = Field(50, ge=1)
    # [Actuator] Step Size for Position Control
    ActuatorStep: int = Field(5, ge=1, le=100, description="Step size for Actuator (1-100)")
    WidgetWidth: int = Field(512, ge=100)
    WidgetHeight: int = Field(288, ge=100)

    class Config:
        alias_generator = lambda s: s.lower()
        populate_by_name = True

class SettingsConfig(BaseModel):
    Password: str
    LogPath: str
    SnapshotPath: str
    AutoSave: bool = True

    class Config:
        alias_generator = lambda s: s.lower()
        populate_by_name = True

class ThresholdsValue(BaseModel):
    # Dynamic fields but listing known ones helps validation/IDE
    # Using extra='allow' to support any key
    class Config:
        extra = 'allow'

class LoggingConfig(BaseModel):
    RotationMode: str = "DAILY" # BILLET, DAILY
    CycleIdleTime: int = 10
    CycleThresholdPress: float = 20.0
    
    class Config:
        alias_generator = lambda s: s.lower()
        populate_by_name = True

class ThresholdsEnable(BaseModel):
    class Config:
        extra = 'allow'

class AppConfig(BaseModel):
    SYSTEM: SystemConfig
    EXTRUDER: NetworkConfig
    SPOT: SpotConfig
    LS_PLC: NetworkConfig
    SETTINGS: SettingsConfig
    LOGGING: Optional[LoggingConfig] = Field(default_factory=LoggingConfig)
    THRESHOLDS_VALUE: Optional[ThresholdsValue] = Field(default_factory=ThresholdsValue)
    THRESHOLDS_ENABLE: Optional[ThresholdsEnable] = Field(default_factory=ThresholdsEnable)
