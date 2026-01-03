from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os
import threading
import time
from typing import Any, Dict, Optional

from .plc_service import plc_service


def _format_ts(value: Optional[float]) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromtimestamp(value).isoformat(timespec="seconds")
    except Exception:
        return "-"


def _format_seconds(value: Optional[float]) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}s"
    except Exception:
        return "-"


def _short_text(value: Optional[str], max_len: int = 80) -> str:
    if not value:
        return "-"
    text = str(value).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


class CommMetricsLoggerService:
    def __init__(self, interval_sec: float | None = None) -> None:
        env_interval = os.getenv("SFL_COMM_LOG_INTERVAL_SEC")
        if interval_sec is None:
            if env_interval:
                try:
                    interval_sec = float(env_interval)
                except Exception:
                    interval_sec = 60.0
            else:
                interval_sec = 60.0
        self.interval_sec = max(5.0, float(interval_sec))
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self._file_path: Optional[str] = None
        self.logger = self._build_logger()
        self._last_ex_connected: Optional[bool] = None
        self._last_ls_connected: Optional[bool] = None
        self._last_ex_error_time: Optional[float] = None
        self._last_ls_error_time: Optional[float] = None
        self._last_spot_error_time: Optional[float] = None
        self._spot_in_error = False

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger("SmartFactoryLoggerV2.CommMetrics")
        if logger.handlers:
            for handler in logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    self._file_path = handler.baseFilename
                    break
            return logger
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        log_dir = None
        try:
            from .. import config

            if config.LOG_PATH:
                log_dir = config.LOG_PATH
        except Exception:
            log_dir = None
        if not log_dir:
            appdata = os.getenv("APPDATA")
            if appdata:
                log_dir = os.path.join(appdata, "SmartFactoryLogger", "logs")
            else:
                log_dir = os.path.join(os.getcwd(), "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = os.getcwd()
        file_path = os.path.join(log_dir, "comm_metrics.log")
        self._file_path = file_path
        handler = RotatingFileHandler(file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
        return logger

    def get_log_path(self) -> Optional[str]:
        return self._file_path

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="CommMetricsLogger", daemon=True)
        self.thread.start()
        self.logger.info("Comm metrics logger started (interval=%.1fs).", self.interval_sec)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.thread = None
        self.logger.info("Comm metrics logger stopped.")

    def _summarize_ex(self, metrics: Optional[Dict[str, Any]]) -> str:
        if not metrics:
            return "EX=no_data"
        connected = "1" if metrics.get("connected") else "0"
        failures = int(metrics.get("connect_failures", 0)) + int(metrics.get("read_failures", 0))
        invalid = int(metrics.get("invalid_responses", 0))
        skipped = int(metrics.get("skipped_reads", 0))
        backoff = _format_seconds(metrics.get("backoff_sec"))
        next_retry = _format_ts(metrics.get("next_retry_at"))
        last_err_time = _format_ts(metrics.get("last_error_time"))
        last_ok = _format_ts(metrics.get("last_success_time"))
        recovery = _format_seconds(metrics.get("last_recovery_sec"))
        recovery_count = int(metrics.get("recovery_count", 0))
        total_downtime = _format_seconds(metrics.get("total_downtime_sec"))
        current_downtime = _format_seconds(metrics.get("current_downtime_sec"))
        last_disconnect = _format_ts(metrics.get("last_disconnect_time"))
        last_recovery_at = _format_ts(metrics.get("last_recovery_at"))
        merge = metrics.get("merge_blocks")
        merge_state = "-" if merge is None else ("ON" if merge else "OFF")
        merge_fail = int(metrics.get("merge_failures", 0))
        last_err = _short_text(metrics.get("last_error"))
        return (
            "EX"
            f" conn={connected}"
            f" fail={failures}"
            f" invalid={invalid}"
            f" skip={skipped}"
            f" backoff={backoff}"
            f" next={next_retry}"
            f" last_ok={last_ok}"
            f" last_err={last_err_time}"
            f" recovery={recovery}"
            f" recov_cnt={recovery_count}"
            f" down_total={total_downtime}"
            f" down_now={current_downtime}"
            f" last_disc={last_disconnect}"
            f" last_rec={last_recovery_at}"
            f" merge={merge_state}"
            f" mfail={merge_fail}"
            f" err='{last_err}'"
        )

    def _summarize_ls(self, metrics: Optional[Dict[str, Any]]) -> str:
        if not metrics:
            return "LS=no_data"
        connected = "1" if metrics.get("connected") else "0"
        failures = int(metrics.get("connect_failures", 0)) + int(metrics.get("read_failures", 0))
        invalid = int(metrics.get("invalid_responses", 0))
        backoff = _format_seconds(metrics.get("backoff_sec"))
        next_retry = _format_ts(metrics.get("next_retry_at"))
        last_err_time = _format_ts(metrics.get("last_error_time"))
        last_ok = _format_ts(metrics.get("last_success_time"))
        recovery = _format_seconds(metrics.get("last_recovery_sec"))
        recovery_count = int(metrics.get("recovery_count", 0))
        total_downtime = _format_seconds(metrics.get("total_downtime_sec"))
        current_downtime = _format_seconds(metrics.get("current_downtime_sec"))
        last_disconnect = _format_ts(metrics.get("last_disconnect_time"))
        last_recovery_at = _format_ts(metrics.get("last_recovery_at"))
        last_err = _short_text(metrics.get("last_error"))
        return (
            "LS"
            f" conn={connected}"
            f" fail={failures}"
            f" invalid={invalid}"
            f" backoff={backoff}"
            f" next={next_retry}"
            f" last_ok={last_ok}"
            f" last_err={last_err_time}"
            f" recovery={recovery}"
            f" recov_cnt={recovery_count}"
            f" down_total={total_downtime}"
            f" down_now={current_downtime}"
            f" last_disc={last_disconnect}"
            f" last_rec={last_recovery_at}"
            f" err='{last_err}'"
        )

    def _summarize_spot(self, metrics: Optional[Dict[str, Any]]) -> str:
        if not metrics:
            return "SPOT=no_data"
        last_value = metrics.get("last_value")
        failures = int(metrics.get("read_failures", 0))
        last_err_time = _format_ts(metrics.get("last_error_time"))
        last_ok = _format_ts(metrics.get("last_success_time"))
        timeout = _format_seconds(metrics.get("timeout_sec"))
        return (
            "SPOT"
            f" val={last_value if last_value is not None else '-'}"
            f" fail={failures}"
            f" last_ok={last_ok}"
            f" last_err={last_err_time}"
            f" timeout={timeout}"
        )

    def _log_events(self, comm: Dict[str, Any]) -> None:
        extruder = comm.get("extruder") or {}
        ls_plc = comm.get("ls_plc") or {}
        spot = comm.get("spot") or {}

        ex_connected = bool(extruder.get("connected")) if extruder else None
        ls_connected = bool(ls_plc.get("connected")) if ls_plc else None

        if ex_connected is not None:
            if self._last_ex_connected is None:
                self._last_ex_connected = ex_connected
            elif ex_connected != self._last_ex_connected:
                if ex_connected:
                    self.logger.info(
                        "COMM_EVENT EX_RECOVERED recovery=%s count=%s down_total=%s last_ok=%s",
                        _format_seconds(extruder.get("last_recovery_sec")),
                        int(extruder.get("recovery_count", 0)),
                        _format_seconds(extruder.get("total_downtime_sec")),
                        _format_ts(extruder.get("last_success_time")),
                    )
                else:
                    failures = int(extruder.get("connect_failures", 0)) + int(extruder.get("read_failures", 0))
                    self.logger.warning(
                        "COMM_EVENT EX_DISCONNECTED fail=%s backoff=%s down_now=%s err='%s'",
                        failures,
                        _format_seconds(extruder.get("backoff_sec")),
                        _format_seconds(extruder.get("current_downtime_sec")),
                        _short_text(extruder.get("last_error")),
                    )
                self._last_ex_connected = ex_connected

        if ls_connected is not None:
            if self._last_ls_connected is None:
                self._last_ls_connected = ls_connected
            elif ls_connected != self._last_ls_connected:
                if ls_connected:
                    self.logger.info(
                        "COMM_EVENT LS_RECOVERED recovery=%s count=%s down_total=%s last_ok=%s",
                        _format_seconds(ls_plc.get("last_recovery_sec")),
                        int(ls_plc.get("recovery_count", 0)),
                        _format_seconds(ls_plc.get("total_downtime_sec")),
                        _format_ts(ls_plc.get("last_success_time")),
                    )
                else:
                    failures = int(ls_plc.get("connect_failures", 0)) + int(ls_plc.get("read_failures", 0))
                    self.logger.warning(
                        "COMM_EVENT LS_DISCONNECTED fail=%s backoff=%s down_now=%s err='%s'",
                        failures,
                        _format_seconds(ls_plc.get("backoff_sec")),
                        _format_seconds(ls_plc.get("current_downtime_sec")),
                        _short_text(ls_plc.get("last_error")),
                    )
                self._last_ls_connected = ls_connected

        ex_error_time = extruder.get("last_error_time")
        if ex_error_time and ex_error_time != self._last_ex_error_time:
            self._last_ex_error_time = ex_error_time
            self.logger.warning(
                "COMM_EVENT EX_ERROR at=%s err='%s'",
                _format_ts(ex_error_time),
                _short_text(extruder.get("last_error")),
            )

        ls_error_time = ls_plc.get("last_error_time")
        if ls_error_time and ls_error_time != self._last_ls_error_time:
            self._last_ls_error_time = ls_error_time
            self.logger.warning(
                "COMM_EVENT LS_ERROR at=%s err='%s'",
                _format_ts(ls_error_time),
                _short_text(ls_plc.get("last_error")),
            )

        spot_error_time = spot.get("last_error_time")
        if spot_error_time and spot_error_time != self._last_spot_error_time:
            self._last_spot_error_time = spot_error_time
            self._spot_in_error = True
            self.logger.warning(
                "COMM_EVENT SPOT_ERROR at=%s fail=%s",
                _format_ts(spot_error_time),
                int(spot.get("read_failures", 0)),
            )
        spot_success_time = spot.get("last_success_time")
        if self._spot_in_error and spot_success_time:
            if not spot_error_time or float(spot_success_time) > float(spot_error_time):
                self._spot_in_error = False
                self.logger.info(
                    "COMM_EVENT SPOT_RECOVERED at=%s",
                    _format_ts(spot_success_time),
                )

    def _loop(self) -> None:
        while self.running:
            try:
                health = plc_service.get_health()
                comm = health.get("comm") or {}
                mode = health.get("mode") or "-"
                parts = [
                    f"mode={mode}",
                    self._summarize_ex(comm.get("extruder")),
                    self._summarize_ls(comm.get("ls_plc")),
                    self._summarize_spot(comm.get("spot")),
                ]
                self._log_events(comm)
                self.logger.info("COMM_METRICS %s", " | ".join(parts))
            except Exception as exc:
                self.logger.warning("COMM_METRICS log failed: %s", exc)
            time.sleep(self.interval_sec)


comm_metrics_logger_service = CommMetricsLoggerService()
