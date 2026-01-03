import csv
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterable, Tuple

from .. import config
from ..models.data_model import FactoryData


class CSVLoggerService:
    def __init__(self) -> None:
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.queue: queue.Queue[Optional[FactoryData]] = queue.Queue(maxsize=5000)
        self.logger = logging.getLogger("SmartFactoryLoggerV2")
        self._config_lock = threading.Lock()
        self._config_version = 0
        self.active_log_dir = Path(config.LOG_PATH)
        self.fallback_log_dir = config.APP_DATA_DIR / "logs"
        self.auto_save = bool(config.AUTO_SAVE)
        self.rotation_enabled = bool(config.ROTATION_ENABLED)
        self.rotation_mode = (config.ROTATION_MODE or "DAILY").upper()
        self.cycle_idle_time = float(config.CYCLE_IDLE_TIME)
        self.cycle_threshold_press = float(config.CYCLE_THRESHOLD_PRESS)
        self.csv_header = self._parse_header(config.CSV_HEADER)
        self._logpath_warned = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="CSVLogger", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        if self.thread:
            self.thread.join(timeout=2.0)

    def enqueue(self, data: FactoryData) -> None:
        if not self.running:
            return
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            self.logger.warning("CSV log queue full. Dropping data.")

    def apply_config(
        self,
        *,
        log_path: Optional[Path] = None,
        auto_save: Optional[bool] = None,
        rotation_enabled: Optional[bool] = None,
        rotation_mode: Optional[str] = None,
        cycle_idle_time: Optional[float] = None,
        cycle_threshold_press: Optional[float] = None,
        csv_header: Optional[str] = None,
    ) -> bool:
        changed = False
        with self._config_lock:
            if log_path is not None:
                self.active_log_dir = Path(log_path)
                changed = True
            if auto_save is not None:
                self.auto_save = bool(auto_save)
                changed = True
            if rotation_enabled is not None:
                self.rotation_enabled = bool(rotation_enabled)
                changed = True
            if rotation_mode is not None:
                self.rotation_mode = (rotation_mode or "DAILY").upper()
                changed = True
            if cycle_idle_time is not None:
                try:
                    self.cycle_idle_time = float(cycle_idle_time)
                    changed = True
                except Exception:
                    pass
            if cycle_threshold_press is not None:
                try:
                    self.cycle_threshold_press = float(cycle_threshold_press)
                    changed = True
                except Exception:
                    pass
            if csv_header is not None:
                self.csv_header = self._parse_header(csv_header)
                changed = True
            if changed:
                self._config_version += 1
        return changed

    def _parse_header(self, header: str) -> list[str]:
        if not header:
            return []
        return [item.strip() for item in header.split(",") if item.strip()]

    def _ensure_dir(self, path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def _get_log_dir(self) -> Path:
        with self._config_lock:
            active_dir = self.active_log_dir
            fallback_dir = self.fallback_log_dir
            warned = self._logpath_warned
        if self._ensure_dir(active_dir):
            return active_dir
        if active_dir != fallback_dir:
            if not warned:
                self.logger.warning(
                    "LOG_PATH not usable: %s. Using fallback: %s",
                    active_dir,
                    fallback_dir,
                )
                warned = True
            active_dir = fallback_dir
            self._ensure_dir(active_dir)
            with self._config_lock:
                self.active_log_dir = active_dir
                self._logpath_warned = warned
        return active_dir

    def _open_log_file(self, timestamp_str: str, prefix: str) -> Tuple[Optional[object], Optional[csv.writer]]:
        if not self.auto_save:
            return None, None
        filename = f"{prefix}_{timestamp_str}.csv"
        log_dir = self._get_log_dir()
        full_path = log_dir / filename
        try:
            handle = full_path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(handle)
            if handle.tell() == 0 and self.csv_header:
                writer.writerow(self.csv_header)
                handle.flush()
            self.logger.info("CSV log file opened: %s", full_path)
            return handle, writer
        except Exception as exc:
            self.logger.error("Failed to open CSV log file: %s", exc)
            if log_dir != self.fallback_log_dir:
                fallback_path = self.fallback_log_dir / filename
                try:
                    self._ensure_dir(self.fallback_log_dir)
                    handle = fallback_path.open("a", newline="", encoding="utf-8-sig")
                    writer = csv.writer(handle)
                    if handle.tell() == 0 and self.csv_header:
                        writer.writerow(self.csv_header)
                        handle.flush()
                    self.logger.warning("CSV log fallback path used: %s", fallback_path)
                    self.active_log_dir = self.fallback_log_dir
                    return handle, writer
                except Exception as exc2:
                    self.logger.error("Failed to open CSV log file (fallback): %s", exc2)
        return None, None

    def _build_row(self, data: FactoryData, timestamp: datetime) -> Tuple[list, float]:
        date_s = timestamp.strftime("%Y-%m-%d")
        time_s = timestamp.strftime("%H:%M:%S.%f")[:-3]
        press_value = self._to_float(data.Press)
        row = [
            date_s,
            time_s,
            self._fmt(data.Spot),
            self._fmt(press_value),
            self._fmt(data.Billet_Length),
            self._fmt(data.Temp_F),
            self._fmt(data.Temp_B),
            self._fmt(data.Count),
            self._fmt(data.Speed),
            self._fmt(data.EndPos),
            self._fmt(data.Mold1),
            self._fmt(data.Mold2),
            self._fmt(data.Mold3),
            self._fmt(data.Mold4),
            self._fmt(data.Mold5),
            self._fmt(data.Mold6),
            self._fmt(data.Billet_Temp),
            self._fmt(data.At_Pre),
            self._fmt(data.At_Temp),
            data.Die_ID or "",
            data.Billet_Cycle_ID or "",
        ]
        return row, press_value

    def _parse_timestamp(self, data: FactoryData) -> datetime:
        try:
            if data.Time:
                return datetime.fromisoformat(data.Time)
        except Exception:
            pass
        return datetime.now()

    def _fmt(self, value: Optional[float]) -> str:
        if value is None:
            return ""
        try:
            if isinstance(value, (int, float)):
                if not isinstance(value, bool):
                    return str(value)
        except Exception:
            return ""
        return ""

    def _to_float(self, value: Optional[float]) -> float:
        try:
            return float(value) if value is not None else 0.0
        except Exception:
            return 0.0

    def _flush_buffer(
        self,
        writer: Optional[csv.writer],
        handle: Optional[object],
        buffer: Iterable[Tuple[list, datetime]],
    ) -> None:
        if not buffer:
            return
        if not self.auto_save or writer is None or handle is None:
            return
        writer.writerows([row for row, _ in buffer])
        handle.flush()

    def _loop(self) -> None:
        buffer: list[Tuple[list, datetime]] = []
        batch_size = 20
        flush_interval = 1.0
        last_flush_time = time.time()
        file_prefix = "Factory_Integrated_Log"

        f_handle = None
        writer = None
        current_date_str = datetime.now().strftime("%Y%m%d")

        cycle_idle_start = 0.0
        is_cycle_armed = False
        idle_threshold = 10.0
        current_config_version = -1

        while True:
            try:
                with self._config_lock:
                    auto_save = self.auto_save
                    rotation_enabled = self.rotation_enabled
                    rotation_mode = self.rotation_mode
                    cycle_idle_time = self.cycle_idle_time
                    cycle_threshold_press = self.cycle_threshold_press
                    config_version = self._config_version

                if config_version != current_config_version:
                    current_config_version = config_version
                    if f_handle:
                        try:
                            f_handle.close()
                        except Exception:
                            pass
                    f_handle = None
                    writer = None
                    current_date_str = datetime.now().strftime("%Y%m%d")
                    cycle_idle_start = 0.0
                    is_cycle_armed = False

                item = None
                try:
                    item = self.queue.get(timeout=0.2)
                except queue.Empty:
                    item = None

                if item is None:
                    if not self.running:
                        break
                else:
                    timestamp = self._parse_timestamp(item)
                    row, press_value = self._build_row(item, timestamp)
                    buffer.append((row, timestamp))

                    if rotation_enabled and rotation_mode == "BILLET":
                        if press_value < idle_threshold:
                            if cycle_idle_start == 0.0:
                                cycle_idle_start = time.time()
                            elif (time.time() - cycle_idle_start) > cycle_idle_time:
                                is_cycle_armed = True
                        else:
                            cycle_idle_start = 0.0
                            if is_cycle_armed and press_value >= cycle_threshold_press:
                                if f_handle:
                                    f_handle.close()
                                new_ts = timestamp.strftime("%Y%m%d_%H%M%S")
                                f_handle, writer = self._open_log_file(new_ts, prefix=file_prefix)
                                is_cycle_armed = False

                now = time.time()
                if buffer and (len(buffer) >= batch_size or (now - last_flush_time) > flush_interval):
                    if not f_handle or not writer:
                        ts = buffer[0][1].strftime("%Y%m%d_%H%M%S")
                        f_handle, writer = self._open_log_file(ts, prefix=file_prefix)

                    if rotation_enabled and rotation_mode == "DAILY":
                        first_ts = buffer[0][1]
                        today_str = first_ts.strftime("%Y%m%d")
                        if today_str != current_date_str:
                            if f_handle:
                                f_handle.close()
                            current_date_str = today_str
                            new_ts = first_ts.strftime("%Y%m%d_%H%M%S")
                            f_handle, writer = self._open_log_file(new_ts, prefix=file_prefix)

                    if auto_save:
                        self._flush_buffer(writer, f_handle, buffer)
                    buffer.clear()
                    last_flush_time = now
            except Exception as exc:
                self.logger.error("Error in CSV logger loop: %s", exc)
                if f_handle:
                    try:
                        f_handle.close()
                    except Exception:
                        pass
                f_handle, writer = None, None
                buffer.clear()
                time.sleep(0.5)

        if buffer:
            try:
                self._flush_buffer(writer, f_handle, buffer)
            except Exception:
                pass
        if f_handle:
            try:
                f_handle.close()
            except Exception:
                pass
        self.logger.info("CSV logger thread stopped.")


logger_service = CSVLoggerService()
