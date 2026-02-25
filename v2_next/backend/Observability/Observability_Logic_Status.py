from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional

from backend.FacilityData.FacilityData_Structure import FactoryData

from .. import constants


def _is_finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


class StatusEvaluator:
    def __init__(self) -> None:
        self._last_valid: Dict[str, float] = {}
        self._spot_since: Optional[float] = None
        self._spot_warning = False
        self._jam_since: Optional[float] = None

    def _pick(self, key: str, value: Optional[float]) -> Optional[float]:
        if not _is_finite(value):
            return self._last_valid.get(key)
        self._last_valid[key] = float(value)
        return float(value)

    def _parse_threshold(self, raw: Any) -> Optional[float]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None

    def _threshold_hit(
        self,
        key: str,
        value: Optional[float],
        thresholds: Dict[str, Any],
    ) -> bool:
        enable = thresholds.get("enable", {})
        values = thresholds.get("values", {})
        if not enable.get("master_on", False):
            return False
        if not enable.get(key, False):
            return False
        threshold = self._parse_threshold(values.get(key))
        if threshold is None or not _is_finite(value):
            return False
        return value >= threshold

    def _update_sustained(
        self, condition: bool, duration_sec: float, since: Optional[float]
    ) -> tuple[Optional[float], bool]:
        now = time.monotonic()
        if condition:
            if since is None:
                since = now
            if now - since >= duration_sec:
                return since, True
            return since, False
        return None, False

    def evaluate(
        self,
        data: FactoryData,
        thresholds: Dict[str, Any],
        press_threshold: float,
    ) -> Dict[str, Any]:
        speed = self._pick("Speed", data.Speed)
        press = self._pick("Press", data.Press)
        count = self._pick("Count", float(data.Count) if isinstance(data.Count, (int, float)) else None)
        endpos = self._pick("EndPos", data.EndPos)
        billet_len = self._pick("Billet_Length", data.Billet_Length)
        spot = self._pick("Spot", data.Spot)
        temp_f = self._pick("Temp_F", data.Temp_F)
        temp_b = self._pick("Temp_B", data.Temp_B)
        billet_temp = self._pick("Billet_Temp", data.Billet_Temp)
        at_temp = self._pick("At_Temp", data.At_Temp)
        at_pre = self._pick("At_Pre", data.At_Pre)
        mold1 = self._pick("Mold1", data.Mold1)
        mold2 = self._pick("Mold2", data.Mold2)
        mold3 = self._pick("Mold3", data.Mold3)
        mold4 = self._pick("Mold4", data.Mold4)
        mold5 = self._pick("Mold5", data.Mold5)
        mold6 = self._pick("Mold6", data.Mold6)

        # Jam detection
        jam_condition = _is_finite(speed) and _is_finite(press) and speed == 0 and press >= press_threshold
        if jam_condition:
            if self._jam_since is None:
                self._jam_since = time.monotonic()
            elapsed = time.monotonic() - self._jam_since
            jam_warn = elapsed >= constants.ALERT_HOLD_SEC
            jam_danger = elapsed >= constants.ALERT_HOLD_LONG_SEC
        else:
            self._jam_since = None
            jam_warn = False
            jam_danger = False

        jam_level = "danger" if jam_danger else "warn" if jam_warn else "none"

        # Spot warning (sustained)
        spot_condition = _is_finite(spot) and spot >= constants.SPOT_WARN_TEMP
        self._spot_since, self._spot_warning = self._update_sustained(
            spot_condition, constants.ALERT_HOLD_SEC, self._spot_since
        )

        # Speed level
        if _is_finite(speed):
            if abs(speed) < constants.SPEED_IDLE_MAX:
                speed_level = "idle"
            elif speed >= constants.SPEED_VERY_FAST_MIN:
                speed_level = "very_fast"
            elif speed >= constants.SPEED_FAST_MIN:
                speed_level = "fast"
            elif speed >= constants.SPEED_NORMAL_MIN:
                speed_level = "normal"
            elif speed >= constants.SPEED_SLOW_MIN:
                speed_level = "slow"
            else:
                speed_level = "very_slow"
        else:
            speed_level = "idle"

        # Press level
        if _is_finite(press):
            if abs(press) < constants.PRESS_IDLE_MAX:
                press_level = "idle"
            elif press >= constants.PRESS_HIGH_MIN:
                press_level = "high"
            elif press >= constants.PRESS_NORMAL_MIN:
                press_level = "normal"
            else:
                press_level = "low"
        else:
            press_level = "idle"

        # Spot level
        if _is_finite(spot):
            if abs(spot) < 0.1:
                spot_level = "idle"
            elif spot >= constants.SPOT_WARN_TEMP and self._spot_warning:
                spot_level = "warning"
            elif spot >= constants.SPOT_HIGH_MIN:
                spot_level = "high"
            elif spot >= constants.SPOT_NORMAL_MIN:
                spot_level = "normal"
            else:
                spot_level = "low"
        else:
            spot_level = "idle"

        # Environment
        if _is_finite(at_temp):
            if at_temp >= constants.ENV_TEMP_HOT:
                env_temp_level = "hot"
            elif at_temp < constants.ENV_TEMP_COLD:
                env_temp_level = "cold"
            else:
                env_temp_level = "comfort"
        else:
            env_temp_level = "unknown"

        if _is_finite(at_pre):
            if at_pre >= constants.ENV_HUMID_HIGH:
                env_pre_level = "humid"
            elif at_pre < constants.ENV_HUMID_LOW:
                env_pre_level = "dry"
            else:
                env_pre_level = "comfort"
        else:
            env_pre_level = "unknown"

        def mold_level(value: Optional[float]) -> str:
            if not _is_finite(value):
                return "muted"
            return "alert" if value >= constants.MOLD_ALERT_THRESHOLD else "normal"

        computed_thresholds = {
            "speed": self._threshold_hit("speed", speed, thresholds),
            "press": self._threshold_hit("press", press, thresholds),
            "spot": self._threshold_hit("spot", spot, thresholds),
            "temp_f": self._threshold_hit("temp_f", temp_f, thresholds),
            "temp_b": self._threshold_hit("temp_b", temp_b, thresholds),
            "billet": self._threshold_hit("billet", billet_len, thresholds),
            "billet_temp": self._threshold_hit("billet_temp", billet_temp, thresholds),
            "at_temp": self._threshold_hit("at_temp", at_temp, thresholds),
            "at_pre": self._threshold_hit("at_pre", at_pre, thresholds),
            "count": self._threshold_hit("count", count, thresholds),
            "endpos": self._threshold_hit("endpos", endpos, thresholds),
        }

        return {
            "speed_level": speed_level,
            "press_level": press_level,
            "spot_level": spot_level,
            "spot_warning": bool(self._spot_warning),
            "env_temp_level": env_temp_level,
            "env_pre_level": env_pre_level,
            "mold_levels": {
                "Mold1": mold_level(mold1),
                "Mold2": mold_level(mold2),
                "Mold3": mold_level(mold3),
                "Mold4": mold_level(mold4),
                "Mold5": mold_level(mold5),
                "Mold6": mold_level(mold6),
            },
            "jam_level": jam_level,
            "thresholds": computed_thresholds,
        }
