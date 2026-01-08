from pydantic import BaseModel
from typing import Optional


class NetConfig(BaseModel):
    ip: Optional[str] = None
    port: Optional[int] = None


class SpotConfig(BaseModel):
    ip: Optional[str] = None
    refresh_interval: Optional[float] = None
    timeout: Optional[float] = None


class SettingsConfig(BaseModel):
    logpath: Optional[str] = None
    snapshotpath: Optional[str] = None
    autosave: Optional[bool] = None
    password: Optional[str] = None
    custom_notice: Optional[str] = None


class LoggingConfig(BaseModel):
    rotation_enabled: Optional[bool] = None
    rotation_mode: Optional[str] = None
    cycle_idle_time: Optional[float] = None
    cycle_threshold_press: Optional[float] = None


class ThresholdsValue(BaseModel):
    speed: Optional[str] = None
    press: Optional[str] = None
    spot: Optional[str] = None
    temp_f: Optional[str] = None
    temp_b: Optional[str] = None
    billet: Optional[str] = None
    billet_temp: Optional[str] = None
    at_temp: Optional[str] = None
    at_pre: Optional[str] = None
    count: Optional[str] = None
    endpos: Optional[str] = None


class ThresholdsEnable(BaseModel):
    master_on: Optional[bool] = None
    speed: Optional[bool] = None
    press: Optional[bool] = None
    spot: Optional[bool] = None
    temp_f: Optional[bool] = None
    temp_b: Optional[bool] = None
    billet: Optional[bool] = None
    billet_temp: Optional[bool] = None
    at_temp: Optional[bool] = None
    at_pre: Optional[bool] = None
    count: Optional[bool] = None
    endpos: Optional[bool] = None


class ThresholdsConfig(BaseModel):
    values: Optional[ThresholdsValue] = None
    enable: Optional[ThresholdsEnable] = None


class SystemConfig(BaseModel):
    interval_sec: Optional[float] = None


class ConfigUpdate(BaseModel):
    extruder: Optional[NetConfig] = None
    ls_plc: Optional[NetConfig] = None
    spot: Optional[SpotConfig] = None
    settings: Optional[SettingsConfig] = None
    logging: Optional[LoggingConfig] = None
    thresholds: Optional[ThresholdsConfig] = None
    system: Optional[SystemConfig] = None


class OverrideToggle(BaseModel):
    enabled: bool
    password: Optional[str] = None
    actor: Optional[str] = None
