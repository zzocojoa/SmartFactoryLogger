from __future__ import annotations
from typing import Dict, List, Tuple

# Threshold Keys (Status Evaluator)
ALERT_HOLD_SEC = 2.0
ALERT_HOLD_LONG_SEC = 5.0

# Temperature Thresholds (Celsius)
SPOT_WARN_TEMP = 580.0
SPOT_HIGH_MIN = 540.0
SPOT_NORMAL_MIN = 480.0
MOLD_ALERT_THRESHOLD = 100.0

# Environment Thresholds
ENV_TEMP_HOT = 28.0
ENV_TEMP_COLD = 10.0
ENV_HUMID_HIGH = 60.0
ENV_HUMID_LOW = 30.0

# Level Thresholds
SPEED_IDLE_MAX = 0.05
SPEED_VERY_FAST_MIN = 8.0
SPEED_FAST_MIN = 6.0
SPEED_NORMAL_MIN = 4.0
SPEED_SLOW_MIN = 2.0

PRESS_IDLE_MAX = 0.1
PRESS_HIGH_MIN = 180.0
PRESS_NORMAL_MIN = 126.0

# Data Field Keys
FIELD_KEYS = [
    "Speed",
    "Press",
    "Spot",
    "Temp_F",
    "Temp_B",
    "Billet_Temp",
    "Billet_Length",
    "Count",
    "EndPos",
    "At_Temp",
    "At_Pre",
    "Mold1",
    "Mold2",
    "Mold3",
    "Mold4",
    "Mold5",
    "Mold6",
]

# Field Mapping & Aliases (lower_cased -> Field Key)
HEADER_ALIASES: Dict[str, str] = {
    "temperature": "Spot",
    "spot": "Spot",
    "spottemp": "Spot",
    "spottemperature": "Spot",
    "mainpress": "Press",
    "press": "Press",
    "speed": "Speed",
    "count": "Count",
    "endpos": "EndPos",
    "billetlength": "Billet_Length",
    "billettemp": "Billet_Temp",
    "tempf": "Temp_F",
    "tempb": "Temp_B",
    "attemp": "At_Temp",
    "atpre": "At_Pre",
    "mold1": "Mold1",
    "mold2": "Mold2",
    "mold3": "Mold3",
    "mold4": "Mold4",
    "mold5": "Mold5",
    "mold6": "Mold6",
    "메인압력": "Press",
    "현재속도": "Speed",
    "생산카운터": "Count",
    "압출종료위치": "EndPos",
    "빌렛길이": "Billet_Length",
    "빌렛온도": "Billet_Temp",
    "콘테이너온도앞쪽": "Temp_F",
    "콘테이너온도뒷쪽": "Temp_B",
    "환경온도": "At_Temp",
    "환경습도": "At_Pre",
}

# Verification Defaults
DEFAULT_ABS_TOLERANCE: Dict[str, float] = {
    "Speed": 0.2,
    "Press": 2.0,
    "Spot": 3.0,
    "Temp_F": 3.0,
    "Temp_B": 3.0,
    "Billet_Temp": 3.0,
    "Billet_Length": 1.0,
    "Count": 1.0,
    "EndPos": 1.0,
    "At_Temp": 1.0,
    "At_Pre": 2.0,
    "Mold1": 3.0,
    "Mold2": 3.0,
    "Mold3": 3.0,
    "Mold4": 3.0,
    "Mold5": 3.0,
    "Mold6": 3.0,
}
DEFAULT_PCT_TOLERANCE = 0.0

# Logic Defaults
CYCLE_SPEED_THRESHOLD = 0.1

# Driver Defaults
DRIVER_RETRY_INTERVAL = 1.0
DRIVER_RETRY_MAX = 8.0
DRIVER_TIMEOUT = 0.5
DRIVER_MERGE_FAIL_THRESHOLD = 3
DRIVER_MERGE_RETRY_SUCCESSES = 300
DRIVER_MERGE_RETRY_GROWTH = 2
