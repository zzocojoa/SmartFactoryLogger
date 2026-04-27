import struct
import time
import select
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
import socket

print(">>> REAL DRIVER V5 (NON-BLOCKING/SELECT) LOADED <<<") # VERSION CHECK

import httpx

from .base import BasePLCDriver
from .spot_api import get_cached_spot_temp
from backend.FacilityData.schemas import FactoryData
from backend import config
from ..processor import LogicProcessor
from backend.Observability.service import observability_service
from backend import constants


class MelsecResponseError(ValueError):
    pass


def _melsec_response_error(addr: str, count: int, raw: bytes, chunk: str, offset: int, reason: str) -> MelsecResponseError:
    return MelsecResponseError(
        f"MELSEC response parse failed addr={addr} count={count} raw={raw!r} "
        f"chunk={chunk!r} offset={offset} reason={reason}"
    )


def _parse_melsec_values(addr: str, count: int, raw: bytes, response: str) -> List[int]:
    if "OK" not in response:
        raise _melsec_response_error(addr, count, raw, "", 0, "missing OK marker")

    hex_data = response.split("OK", 1)[1]
    values: List[int] = []
    for offset in range(0, len(hex_data), 4):
        chunk = hex_data[offset : offset + 4]
        if len(chunk) != 4:
            raise _melsec_response_error(addr, count, raw, chunk, offset, "incomplete hex word")
        try:
            values.append(int(chunk, 16))
        except ValueError as exc:
            raise _melsec_response_error(addr, count, raw, chunk, offset, "invalid hex word") from exc

    if len(values) < count:
        raise _melsec_response_error(addr, count, raw, "", len(hex_data), "short response")

    return values


class RealPLCDriver(BasePLCDriver):
    def __init__(self):
        super().__init__()
        # Extruder (Melsec) Socket
        self.sock_ext: Optional[socket.socket] = None
        self.ext_retry_interval = constants.DRIVER_RETRY_INTERVAL
        self.ext_retry_max = constants.DRIVER_RETRY_MAX
        self.ext_next_retry = 0.0
        self.ext_timeout = constants.DRIVER_TIMEOUT
        self.ext_merge_blocks = True
        self.ext_merge_failures = 0
        self.ext_merge_fail_threshold = constants.DRIVER_MERGE_FAIL_THRESHOLD
        self.ext_merge_retry_successes = constants.DRIVER_MERGE_RETRY_SUCCESSES
        self.ext_merge_retry_current = self.ext_merge_retry_successes
        self.ext_merge_retry_growth = constants.DRIVER_MERGE_RETRY_GROWTH
        self.ext_merge_retry_pending = False
        self.ext_split_success_count = 0
        self.ext_skip_counter = 0
        self.ext_connect_attempts = 0
        self.ext_connect_failures = 0
        self.ext_read_failures = 0
        self.ext_invalid_responses = 0
        self.ext_skipped_reads = 0
        self.ext_backoff_count = 0
        self.ext_last_error: Optional[str] = None
        self.ext_last_error_time: Optional[float] = None
        self.ext_last_success_time: Optional[float] = None
        self.ext_last_recovery_sec: Optional[float] = None
        self.ext_recovery_count = 0
        self.ext_total_downtime_sec = 0.0
        self.ext_last_disconnect_time: Optional[float] = None
        self.ext_last_recovery_at: Optional[float] = None
        self.ext_error_started: Optional[float] = None
        self.ext_in_error = False

        # LS (Temp) Socket
        self.sock_ls: Optional[socket.socket] = None
        self.ls_retry_interval = constants.DRIVER_RETRY_INTERVAL
        self.ls_retry_max = constants.DRIVER_RETRY_MAX
        self.ls_next_retry = 0.0
        self.ls_timeout = constants.DRIVER_TIMEOUT
        self.ls_connect_attempts = 0
        self.ls_connect_failures = 0
        self.ls_read_failures = 0
        self.ls_invalid_responses = 0
        self.ls_backoff_count = 0
        self.ls_last_error: Optional[str] = None
        self.ls_last_error_time: Optional[float] = None
        self.ls_last_success_time: Optional[float] = None
        self.ls_last_recovery_sec: Optional[float] = None
        self.ls_recovery_count = 0
        self.ls_total_downtime_sec = 0.0
        self.ls_last_disconnect_time: Optional[float] = None
        self.ls_last_recovery_at: Optional[float] = None
        self.ls_error_started: Optional[float] = None
        self.ls_in_error = False

        self.spot_timeout = config.SPOT_TIMEOUT
        self.last_spot: Optional[float] = 0.0
        self.spot_read_failures = 0
        self.spot_last_error_time: Optional[float] = None
        self.spot_last_success_time: Optional[float] = None
        self.logic = LogicProcessor()
        self._snapshot_lock = threading.Lock()
        self._worker_stop = threading.Event()
        self._worker_threads: list[threading.Thread] = []
        self._ext_snapshot: Dict[str, float] = {}
        self._ext_snapshot_at: Optional[float] = None
        self._ext_snapshot_error: Optional[str] = None
        self._ls_snapshot: Dict[str, float] = {}
        self._ls_snapshot_at: Optional[float] = None
        self._ls_snapshot_error: Optional[str] = None
        self._spot_snapshot: Optional[float] = None
        self._spot_snapshot_at: Optional[float] = None
        self._spot_snapshot_error: Optional[str] = None
        self._connected_state = False
        self._connected_failure_count = 0
        self._connected_recovery_count = 0

    def _backoff_ext(self):
        self.ext_next_retry = time.time() + self.ext_retry_interval
        self.ext_retry_interval = min(self.ext_retry_interval * 2, self.ext_retry_max)
        self.ext_backoff_count += 1

    def _backoff_ls(self):
        self.ls_next_retry = time.time() + self.ls_retry_interval
        self.ls_retry_interval = min(self.ls_retry_interval * 2, self.ls_retry_max)
        self.ls_backoff_count += 1

    def _mark_ext_error(self, message: str, count_read_failure: bool = True) -> None:
        now = time.time()
        if not self.ext_in_error:
            self.ext_error_started = now
            self.ext_last_disconnect_time = now
        self.ext_in_error = True
        self.ext_last_error = message
        self.ext_last_error_time = now
        if count_read_failure:
            self.ext_read_failures += 1
        try:
            observability_service.record_error(
                "extruder",
                message,
                detail=f"{config.EXTRUDER_IP}:{config.EXTRUDER_PORT}",
            )
        except Exception:
            pass

    def _mark_ext_success(self) -> None:
        now = time.time()
        self.ext_last_success_time = now
        if self.ext_in_error and self.ext_error_started is not None:
            recovery_sec = now - self.ext_error_started
            self.ext_last_recovery_sec = recovery_sec
            self.ext_last_recovery_at = now
            self.ext_recovery_count += 1
            self.ext_total_downtime_sec += recovery_sec
        self.ext_in_error = False
        self.ext_error_started = None

    def _mark_ls_error(self, message: str, count_read_failure: bool = True) -> None:
        now = time.time()
        if not self.ls_in_error:
            self.ls_error_started = now
            self.ls_last_disconnect_time = now
        self.ls_in_error = True
        self.ls_last_error = message
        self.ls_last_error_time = now
        if count_read_failure:
            self.ls_read_failures += 1
        try:
            observability_service.record_error(
                "ls_plc",
                message,
                detail=f"{config.LS_IP}:{config.LS_PORT}",
            )
        except Exception:
            pass

    def _mark_ls_success(self) -> None:
        now = time.time()
        self.ls_last_success_time = now
        if self.ls_in_error and self.ls_error_started is not None:
            recovery_sec = now - self.ls_error_started
            self.ls_last_recovery_sec = recovery_sec
            self.ls_last_recovery_at = now
            self.ls_recovery_count += 1
            self.ls_total_downtime_sec += recovery_sec
        self.ls_in_error = False
        self.ls_error_started = None

    def _mark_spot_error(self, message: str | None = None) -> None:
        self.spot_read_failures += 1
        now = time.time()
        self.spot_last_error_time = now
        try:
            observability_service.record_error(
                "spot",
                message or "SPOT read error",
                detail=config.SPOT_URL,
            )
        except Exception:
            pass

    def _mark_spot_success(self) -> None:
        self.spot_last_success_time = time.time()

    def connect(self) -> bool:
        """Connect to both PLCs."""
        ok_ext = self._connect_extruder()
        ok_ls = self._connect_ls()
        self.connected = ok_ext or ok_ls
        self._connected_state = self.connected
        self._connected_failure_count = 0
        self._connected_recovery_count = 0
        self._start_workers()
        return self.connected

    def apply_connection_config(self) -> None:
        # Force reconnect on next read with updated config values.
        if self.sock_ext:
            try:
                self.sock_ext.close()
            except Exception:
                pass
            self.sock_ext = None
        if self.sock_ls:
            try:
                self.sock_ls.close()
            except Exception:
                pass
            self.sock_ls = None
        self.connected = False
        self._connected_state = False
        self._connected_failure_count = 0
        self._connected_recovery_count = 0

    def _connect_extruder(self) -> bool:
        now = time.time()
        if now < self.ext_next_retry:
            return False
        try:
            self.ext_connect_attempts += 1
            if self.sock_ext:
                try:
                    self.sock_ext.close()
                except Exception:
                    pass
            self.sock_ext = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock_ext.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Non-Blocking Connect (Force Timeout)
            self.sock_ext.setblocking(False)
            err = self.sock_ext.connect_ex((config.EXTRUDER_IP, config.EXTRUDER_PORT))
            
            if err != 0:
                # Wait for writeability (connection success)
                _, writable, _ = select.select([], [self.sock_ext], [], self.ext_timeout)
                if not writable:
                    raise socket.timeout("Connect timeout (Non-Blocking)")
                
                # Check for socket errors
                err = self.sock_ext.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if err != 0:
                     raise OSError(err, "Connect failed")

            # CRITICAL: Keep Non-Blocking Mode permanently!
            # self.sock_ext.setblocking(True)  <-- REMOVED
            # self.sock_ext.settimeout(...)    <-- REMOVED
            
            self.ext_retry_interval = 1.0
            self.ext_next_retry = 0.0
            # print(f"[RealDriver] Connected to Extruder ({config.EXTRUDER_IP})")
            return True
        except Exception as e:
            self.sock_ext = None
            self.ext_connect_failures += 1
            self._mark_ext_error(str(e), count_read_failure=False)
            self._backoff_ext()
            print(f"[RealDriver] Extruder Connection Failed: {e}")
            return False

    def _connect_ls(self) -> bool:
        now = time.time()
        if now < self.ls_next_retry:
            return False
        try:
            self.ls_connect_attempts += 1
            if self.sock_ls:
                try:
                    self.sock_ls.close()
                except Exception:
                    pass
            self.sock_ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock_ls.settimeout(self.ls_timeout)
            self.sock_ls.connect((config.LS_IP, config.LS_PORT))
            self.ls_retry_interval = 1.0
            self.ls_next_retry = 0.0
            print(f"[RealDriver] Connected to LS PLC ({config.LS_IP})")
            return True
        except Exception as e:
            self.sock_ls = None
            self.ls_connect_failures += 1
            self._mark_ls_error(str(e), count_read_failure=False)
            self._backoff_ls()
            print(f"[RealDriver] LS PLC Connection Failed: {e}")
            return False

    def close(self):
        self._worker_stop.set()
        for thread in self._worker_threads:
            thread.join(timeout=1.0)
        self._worker_threads = []
        if self.sock_ext:
            try:
                self.sock_ext.close()
            except Exception:
                pass
        if self.sock_ls:
            try:
                self.sock_ls.close()
            except Exception:
                pass
        self.connected = False
        self._connected_state = False
        self._connected_failure_count = 0
        self._connected_recovery_count = 0
        print("[RealDriver] All Connections Closed.")

    def read_data(self) -> FactoryData:
        ext_data, ls_data, spot_val = self._read_cached_snapshot()

        self.connected = self._update_connected_state(time.time())

        now = datetime.now()

        die_id, billet_cycle_id = self.logic.update(
            ext_data.get("Count"),
            ext_data.get("Press"),
            ext_data.get("Speed"),
            now,
        )

        return FactoryData(
            Time=now.isoformat(),
            Status="Running" if self.connected else "Offline",

            # From Extruder
            Speed=ext_data.get("Speed"),
            Press=ext_data.get("Press"),
            Count=ext_data.get("Count"),
            EndPos=ext_data.get("EndPos"),
            Billet_Length=ext_data.get("Billet"),
            Die_ID=die_id,
            Billet_Cycle_ID=billet_cycle_id,
            Temp_F=ext_data.get("Temp_F"),
            Temp_B=ext_data.get("Temp_B"),

            # From LS
            Mold1=ls_data.get("Mold1"),
            Mold2=ls_data.get("Mold2"),
            Mold3=ls_data.get("Mold3"),
            Mold4=ls_data.get("Mold4"),
            Mold5=ls_data.get("Mold5"),
            Mold6=ls_data.get("Mold6"),
            Billet_Temp=ls_data.get("Billet_Temp"),
            At_Temp=ls_data.get("At_Temp"),
            At_Pre=ls_data.get("At_Pre"),

            # From SPOT
            Spot=spot_val,
        )

    def _start_workers(self) -> None:
        if self._worker_threads:
            return
        self._worker_stop.clear()
        self._worker_threads = [
            threading.Thread(target=self._ext_worker_loop, name="RealPLC-Extruder", daemon=True),
            threading.Thread(target=self._ls_worker_loop, name="RealPLC-LS", daemon=True),
            threading.Thread(target=self._spot_worker_loop, name="RealPLC-SPOT", daemon=True),
        ]
        for thread in self._worker_threads:
            thread.start()

    def _connector_poll_interval_sec(self) -> float:
        return max(0.25, float(config.INTERVAL_SEC))

    def _spot_poll_interval_sec(self) -> float:
        return max(0.5, float(config.SPOT_REFRESH_INTERVAL or 1.0))

    def _sleep_until_next_cycle(self, started_at: float, interval_sec: float) -> None:
        elapsed_sec = time.time() - started_at
        sleep_sec = max(0.0, interval_sec - elapsed_sec)
        if sleep_sec > 0:
            self._worker_stop.wait(sleep_sec)

    def _update_ext_snapshot(self, payload: Dict[str, float], captured_at: float) -> None:
        with self._snapshot_lock:
            self._ext_snapshot = dict(payload)
            self._ext_snapshot_at = captured_at
            self._ext_snapshot_error = None

    def _update_ls_snapshot(self, payload: Dict[str, float], captured_at: float) -> None:
        with self._snapshot_lock:
            self._ls_snapshot = dict(payload)
            self._ls_snapshot_at = captured_at
            self._ls_snapshot_error = None

    def _update_spot_snapshot(self, value: float, captured_at: float) -> None:
        with self._snapshot_lock:
            self._spot_snapshot = value
            self._spot_snapshot_at = captured_at
            self._spot_snapshot_error = None

    def _record_ext_snapshot_error(self, message: str) -> None:
        with self._snapshot_lock:
            self._ext_snapshot_error = message

    def _record_ls_snapshot_error(self, message: str) -> None:
        with self._snapshot_lock:
            self._ls_snapshot_error = message

    def _record_spot_snapshot_error(self, message: str) -> None:
        with self._snapshot_lock:
            self._spot_snapshot_error = message

    def _read_cached_snapshot(self) -> tuple[Dict[str, float], Dict[str, float], Optional[float]]:
        with self._snapshot_lock:
            ext_data = dict(self._ext_snapshot)
            ls_data = dict(self._ls_snapshot)
            spot_val = self._spot_snapshot
        if spot_val is not None:
            self.last_spot = spot_val
        return ext_data, ls_data, spot_val if spot_val is not None else self.last_spot

    def _connected_grace_sec(self) -> float:
        poll_interval_sec = self._connector_poll_interval_sec()
        timeout_sec = max(self.ext_timeout, self.ls_timeout, 1.0)
        return max(poll_interval_sec * 3.0, timeout_sec * 2.0)

    def _has_recent_snapshot(self, snapshot_at: Optional[float], now: float, grace_sec: float) -> bool:
        if snapshot_at is None:
            return False
        return max(0.0, now - snapshot_at) <= grace_sec

    def _compute_connected(self, now: float) -> bool:
        if self.sock_ext is not None or self.sock_ls is not None:
            return True
        with self._snapshot_lock:
            ext_snapshot_at = self._ext_snapshot_at
            ls_snapshot_at = self._ls_snapshot_at
        grace_sec = self._connected_grace_sec()
        return self._has_recent_snapshot(ext_snapshot_at, now, grace_sec) or self._has_recent_snapshot(ls_snapshot_at, now, grace_sec)

    def _update_connected_state(self, now: float) -> bool:
        candidate_connected = self._compute_connected(now)
        if candidate_connected:
            self._connected_failure_count = 0
            if self._connected_state:
                self._connected_recovery_count = 0
                return True
            self._connected_recovery_count += 1
            if self._connected_recovery_count >= 2:
                self._connected_state = True
                self._connected_recovery_count = 0
            return self._connected_state

        self._connected_recovery_count = 0
        if not self._connected_state:
            self._connected_failure_count = 0
            return False
        self._connected_failure_count += 1
        if self._connected_failure_count >= 2:
            self._connected_state = False
            self._connected_failure_count = 0
        return self._connected_state

    def _ext_worker_loop(self) -> None:
        while not self._worker_stop.is_set():
            started_at = time.time()
            try:
                payload = self._read_extruder(started_at + max(self.ext_timeout, 1.0))
                if payload:
                    self._update_ext_snapshot(payload, time.time())
                elif self.ext_last_error:
                    self._record_ext_snapshot_error(self.ext_last_error)
            except Exception as exc:
                self._record_ext_snapshot_error(str(exc))
            self._sleep_until_next_cycle(started_at, self._connector_poll_interval_sec())

    def _ls_worker_loop(self) -> None:
        while not self._worker_stop.is_set():
            started_at = time.time()
            try:
                payload = self._read_ls(started_at + max(self.ls_timeout, 1.0))
                if payload:
                    self._update_ls_snapshot(payload, time.time())
                elif self.ls_last_error:
                    self._record_ls_snapshot_error(self.ls_last_error)
            except Exception as exc:
                self._record_ls_snapshot_error(str(exc))
            self._sleep_until_next_cycle(started_at, self._connector_poll_interval_sec())

    def _spot_worker_loop(self) -> None:
        while not self._worker_stop.is_set():
            started_at = time.time()
            try:
                spot_val = self._read_spot()
                if spot_val > 0:
                    self._update_spot_snapshot(spot_val, time.time())
                elif self.spot_last_error_time is not None:
                    self._record_spot_snapshot_error("spot_read_failed")
            except Exception as exc:
                self._record_spot_snapshot_error(str(exc))
            self._sleep_until_next_cycle(started_at, self._spot_poll_interval_sec())

    def _read_spot(self) -> float:
        val = get_cached_spot_temp()
        if val > 0:
            self.last_spot = val
            self._mark_spot_success()
        return val

    def _remaining_timeout(self, deadline: float, base_timeout: float, context: str) -> float:
        remaining = deadline - time.time()
        if remaining <= 0 or base_timeout <= 0:
            raise socket.timeout(f"{context} timeout")
        return min(base_timeout, remaining)

    def _read_extruder(self, deadline: float) -> Dict[str, float]:
        if time.time() >= deadline:
            self._mark_ext_error("Extruder cycle timeout", count_read_failure=False)
            return {}
        if self.ext_skip_counter > 0:
            self.ext_skip_counter -= 1
            self.ext_skipped_reads += 1
            return {}
        if not self.sock_ext:
            if not self._connect_extruder():
                return {}

        data: Dict[str, float] = {}
        try:
            if self.ext_merge_blocks:
                merged = self._read_extruder_merged(deadline)
                if merged is not None:
                    data.update(merged)
                    self.ext_merge_failures = 0
                    self.ext_merge_retry_pending = False
                    self.ext_merge_retry_current = self.ext_merge_retry_successes
                    self.ext_split_success_count = 0
                    self._mark_ext_success()
                    return data
                self.ext_merge_failures += 1
                if self.ext_merge_failures >= self.ext_merge_fail_threshold:
                    self.ext_merge_blocks = False
                    if self.ext_merge_retry_pending:
                        self.ext_merge_retry_current *= self.ext_merge_retry_growth
                    self.ext_merge_retry_pending = False
                    self.ext_merge_failures = 0
                    self.ext_split_success_count = 0
                    print(
                        f"[RealDriver] Block merge disabled after {self.ext_merge_fail_threshold} failures. "
                        f"Retry after {self.ext_merge_retry_current} successful split cycles."
                    )

            if not self.sock_ext:
                return data

            b1 = self._melsec_read("D0020", 20, deadline)
            if len(b1) > 14:
                data["Press"] = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]

            b_spd = self._melsec_read("B1502", 1, deadline)
            if b_spd:
                data["Speed"] = b_spd[0] / 10.0

            b3 = self._melsec_read("D1500", 20, deadline)
            if len(b3) > 10:
                data["Count"] = b3[10]

            b2 = self._melsec_read("D0420", 10, deadline)
            if len(b2) > 1:
                data["EndPos"] = b2[1] / 10.0

            b4 = self._melsec_read("D1900", 20, deadline)
            if len(b4) > 11:
                data["Billet"] = b4[11]

            if data:
                self._mark_ext_success()

            if not self.ext_merge_blocks:
                split_ok = self.sock_ext is not None and any(
                    v is not None for v in (
                        data.get("Press"),
                        data.get("Temp_F"),
                        data.get("Temp_B"),
                        data.get("Speed"),
                        data.get("EndPos"),
                        data.get("Count"),
                        data.get("Billet"),
                    )
                )
                if split_ok:
                    self.ext_split_success_count += 1
                    if self.ext_split_success_count >= self.ext_merge_retry_current:
                        self.ext_merge_blocks = True
                        self.ext_merge_retry_pending = True
                        self.ext_split_success_count = 0
                        self.ext_merge_failures = 0
                        print(
                            f"[RealDriver] Block merge retry enabled after {self.ext_merge_retry_current} successful split cycles."
                        )
                else:
                    self.ext_split_success_count = 0


        except Exception as e:
            print(f"[RealDriver] Extruder Read Error: {e}")
            self._mark_ext_error(str(e))
            self._backoff_ext()
            self.ext_skip_counter = 5

        return data

    def _recv_until(self, terminator: bytes, max_bytes: int, deadline: float, context: str) -> bytes:
        if not self.sock_ext:
            return b""
        data = bytearray()
        start_time = time.time()
        loop_count = 0
        while len(data) < max_bytes:
            loop_count += 1
            elapsed = time.time() - start_time
            remaining = self._remaining_timeout(deadline, self.ext_timeout - elapsed, "Extruder recv")

            if elapsed > 0.3:
                msg = (
                    f"[recv_until] context={context}, loop={loop_count}, elapsed_sec={elapsed:.3f}, "
                    f"remaining_sec={remaining:.3f}, bytes={len(data)}, max_bytes={max_bytes}"
                )
                print(msg)
                config._config_log("WARNING", msg)

            try:
                t_select_start = time.time()
                r, _, _ = select.select([self.sock_ext], [], [], remaining)
                t_select_end = time.time()
                
                if not r:
                    msg = (
                        f"[recv_until] context={context}, select_timeout=true, loop={loop_count}, "
                        f"waited_sec={t_select_end - t_select_start:.3f}, bytes={len(data)}, max_bytes={max_bytes}"
                    )
                    print(msg)
                    config._config_log("WARNING", msg)
                    raise socket.timeout("Select timeout (Recv Guard)")

                t_recv_start = time.time()
                chunk = self.sock_ext.recv(4096)
                t_recv_end = time.time()

                recv_duration = t_recv_end - t_recv_start
                if recv_duration > 0.1:
                    msg = (
                        f"[recv_until] context={context}, recv_blocked_sec={recv_duration:.3f}, "
                        f"loop={loop_count}, chunk_len={len(chunk)}, bytes_before={len(data)}"
                    )
                    print(msg)
                    config._config_log("WARNING", msg)
                    
            except socket.timeout:
                msg = (
                    f"[recv_until] context={context}, socket_timeout=true, loop={loop_count}, "
                    f"elapsed_sec={time.time() - start_time:.3f}, bytes={len(data)}"
                )
                print(msg)
                config._config_log("WARNING", msg)
                raise

            if not chunk:
                break
            data.extend(chunk)
            if terminator in data:
                break
        return bytes(data)

    def _send_with_timeout(self, data: bytes, deadline: float) -> None:
        if not self.sock_ext:
            raise ConnectionError("No socket")

        total_sent = 0
        total_len = len(data)
        start_time = time.time()

        while total_sent < total_len:
            elapsed = time.time() - start_time
            remaining = self._remaining_timeout(deadline, self.ext_timeout - elapsed, "Extruder send")

            try:
                _, writable, _ = select.select([], [self.sock_ext], [], remaining)
                if not writable:
                    raise socket.timeout("Select timeout (Send Guard)")

                sent = self.sock_ext.send(data[total_sent:])
                if sent == 0:
                    raise ConnectionResetError("Socket connection broken (send returned 0)")
                total_sent += sent
            except BlockingIOError:
                continue

    def _melsec_read(self, addr: str, count: int, deadline: float) -> List[int]:
        if not self.sock_ext:
            return []
        cmd = f"01WRD{addr} {count:02}\r\n".encode()
        t_start = time.time()
        t_after_send = t_start
        t_after_recv = t_start
        raw_len = 0
        result_status = "OK"
        try:
            self._send_with_timeout(cmd, deadline)
            t_after_send = time.time()
            t_after_recv = t_after_send
            raw = self._recv_until(b"\r\n", 8192, deadline, f"MELSEC addr={addr} count={count}")
            t_after_recv = time.time()
            raw_len = len(raw)
            if not raw:
                self.ext_invalid_responses += 1
                result_status = "EMPTY"
                raise ConnectionResetError("Empty response")

            try:
                resp_str = raw.decode("ascii").strip()
            except UnicodeDecodeError as exc:
                self.ext_invalid_responses += 1
                result_status = "DECODE_ERR"
                raise _melsec_response_error(addr, count, raw, "", 0, "non-ascii response") from exc

            try:
                values = _parse_melsec_values(addr, count, raw, resp_str)
            except MelsecResponseError:
                self.ext_invalid_responses += 1
                result_status = "PARSE_ERR"
                raise
            return values
        except (ConnectionError, OSError, MelsecResponseError) as e:
            result_status = f"ERR:{type(e).__name__}"
            print(f"[RealDriver] Extruder Read Error: {e}")
            self._mark_ext_error(str(e))
            self.sock_ext = None
            self._backoff_ext()
            self.ext_skip_counter = 5
            return []
        finally:
            elapsed = time.time() - t_start
            if elapsed > 0.3:
                try:
                    t_send = t_after_send - t_start
                    t_recv = t_after_recv - t_after_send
                    t_parse = elapsed - t_send - t_recv
                    msg = (
                        f"[MelsecRead] addr={addr}, count={count}, elapsed_sec={elapsed:.2f}, "
                        f"send_sec={t_send:.2f}, recv_sec={t_recv:.2f}, parse_sec={t_parse:.2f}, "
                        f"raw_len={raw_len}, status={result_status}"
                    )
                    print(f"[WARNING] {msg}")
                    config._config_log("WARNING", msg)
                except OSError:
                    pass

    def _read_extruder_merged(self, deadline: float) -> Optional[Dict[str, float]]:
        b1 = self._melsec_read("D0020", 16, deadline)
        if not b1:
            return None
        b2 = self._melsec_read("D0420", 6, deadline)
        if not b2:
            return None
        b3 = self._melsec_read("D1500", 16, deadline)
        if not b3:
            return None
        b4 = self._melsec_read("D1900", 16, deadline)
        if not b4:
            return None
        b_spd = self._melsec_read("B1502", 1, deadline)
        if not b_spd:
            return None
        return {
            "Press": b1[3] / 10.0,
            "Temp_F": b1[11],
            "Temp_B": b1[12],
            "EndPos": b2[1] / 10.0,
            "Count": b3[10],
            "Billet": b4[11],
            "Speed": b_spd[0] / 10.0,
        }

    def _read_ls(self, deadline: float) -> Dict[str, float]:
        if time.time() >= deadline:
            self._mark_ls_error("LS cycle timeout", count_read_failure=False)
            return {}
        if not self.sock_ls:
            if not self._connect_ls():
                return {}

        data: Dict[str, float] = {}
        try:
            targets = [t[0] for t in config.LS_TARGETS]
            self.sock_ls.settimeout(self._remaining_timeout(deadline, self.ls_timeout, "LS send"))
            req = self._ls_create_packet(targets)
            self.sock_ls.sendall(req)

            header = self._ls_recv_exact(20, deadline)
            if not header:
                raise ConnectionResetError("No Header")

            body_len = struct.unpack("<H", header[16:18])[0]
            if body_len > 8192:
                raise ValueError("Body too large")

            body = self._ls_recv_exact(body_len, deadline)
            if not body:
                raise ConnectionResetError("No Body")

            values = self._ls_parse_body(body)
            if not values:
                self.ls_invalid_responses += 1
            elif len(values) != len(config.LS_TARGETS):
                self.ls_invalid_responses += 1
            else:
                for i, (addr, key) in enumerate(config.LS_TARGETS):
                    val = values[i]
                    if val is not None:
                        if key in ["At_Temp", "At_Pre"]:
                            data[key] = val / 100.0
                        else:
                            data[key] = val
                if data:
                    self._mark_ls_success()

        except Exception as e:
            print(f"[RealDriver] LS Read Error: {e}")
            self._mark_ls_error(str(e))
            self.sock_ls = None
            self._backoff_ls()

        return data

    def _ls_create_packet(self, var_names: List[str]) -> bytes:
        body = bytearray()
        body += b"\x54\x00"  # Cmd
        body += b"\x02\x00"  # DataType
        body += b"\x00\x00"
        body += struct.pack("<H", len(var_names))

        for name in var_names:
            vb = name.encode("ascii")
            body += struct.pack("<H", len(vb)) + vb

        header = bytearray(b"LSIS-XGT")
        header += b"\x00\x00" * 2
        header += b"\xA0\x33\x00\x01"
        header += struct.pack("<H", len(body))
        header += b"\x00\x00"

        return header + body

    def _ls_recv_exact(self, size: int, deadline: float) -> Optional[bytes]:
        if not self.sock_ls:
            return None
        data = bytearray()
        while len(data) < size:
            try:
                self.sock_ls.settimeout(self._remaining_timeout(deadline, self.ls_timeout, "LS recv"))
                chunk = self.sock_ls.recv(size - len(data))
            except socket.timeout:
                return None
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def _ls_parse_body(self, body: bytes) -> List[Optional[int]]:
        if len(body) < 10:
            return []

        block_cnt = struct.unpack("<H", body[8:10])[0]
        values: List[Optional[int]] = []
        offset = 10

        for _ in range(block_cnt):
            if offset + 2 > len(body):
                break
            d_len = struct.unpack("<H", body[offset : offset + 2])[0]
            offset += 2

            if offset + d_len > len(body):
                break
            raw = body[offset : offset + d_len]
            if len(raw) == 2:
                values.append(struct.unpack("<H", raw)[0])
            else:
                values.append(None)
            offset += d_len
        return values

    def get_comm_metrics(self) -> Dict[str, Dict[str, object]]:
        now = time.time()
        ext_current_downtime_sec = 0.0
        if self.ext_in_error and self.ext_error_started is not None:
            ext_current_downtime_sec = max(0.0, now - self.ext_error_started)
        ls_current_downtime_sec = 0.0
        if self.ls_in_error and self.ls_error_started is not None:
            ls_current_downtime_sec = max(0.0, now - self.ls_error_started)
        with self._snapshot_lock:
            ext_snapshot_at = self._ext_snapshot_at
            ext_snapshot_error = self._ext_snapshot_error
            ls_snapshot_at = self._ls_snapshot_at
            ls_snapshot_error = self._ls_snapshot_error
            spot_snapshot_at = self._spot_snapshot_at
            spot_snapshot_error = self._spot_snapshot_error
        return {
            "extruder": {
                "connected": self.sock_ext is not None,
                "connect_attempts": self.ext_connect_attempts,
                "connect_failures": self.ext_connect_failures,
                "read_failures": self.ext_read_failures,
                "invalid_responses": self.ext_invalid_responses,
                "skipped_reads": self.ext_skipped_reads,
                "backoff_count": self.ext_backoff_count,
                "backoff_sec": self.ext_retry_interval,
                "next_retry_at": self.ext_next_retry,
                "last_error": self.ext_last_error,
                "last_error_time": self.ext_last_error_time,
                "last_success_time": self.ext_last_success_time,
                "last_recovery_sec": self.ext_last_recovery_sec,
                "recovery_count": self.ext_recovery_count,
                "total_downtime_sec": self.ext_total_downtime_sec,
                "current_downtime_sec": ext_current_downtime_sec,
                "last_disconnect_time": self.ext_last_disconnect_time,
                "last_recovery_at": self.ext_last_recovery_at,
                "merge_blocks": self.ext_merge_blocks,
                "merge_failures": self.ext_merge_failures,
                "snapshot_at": ext_snapshot_at,
                "snapshot_age_sec": max(0.0, now - ext_snapshot_at) if ext_snapshot_at is not None else None,
                "snapshot_error": ext_snapshot_error,
            },
            "ls_plc": {
                "connected": self.sock_ls is not None,
                "connect_attempts": self.ls_connect_attempts,
                "connect_failures": self.ls_connect_failures,
                "read_failures": self.ls_read_failures,
                "invalid_responses": self.ls_invalid_responses,
                "backoff_count": self.ls_backoff_count,
                "backoff_sec": self.ls_retry_interval,
                "next_retry_at": self.ls_next_retry,
                "last_error": self.ls_last_error,
                "last_error_time": self.ls_last_error_time,
                "last_success_time": self.ls_last_success_time,
                "last_recovery_sec": self.ls_last_recovery_sec,
                "recovery_count": self.ls_recovery_count,
                "total_downtime_sec": self.ls_total_downtime_sec,
                "current_downtime_sec": ls_current_downtime_sec,
                "last_disconnect_time": self.ls_last_disconnect_time,
                "last_recovery_at": self.ls_last_recovery_at,
                "snapshot_at": ls_snapshot_at,
                "snapshot_age_sec": max(0.0, now - ls_snapshot_at) if ls_snapshot_at is not None else None,
                "snapshot_error": ls_snapshot_error,
            },
            "spot": {
                "last_value": self.last_spot,
                "read_failures": self.spot_read_failures,
                "last_error_time": self.spot_last_error_time,
                "last_success_time": self.spot_last_success_time,
                "timeout_sec": self.spot_timeout,
                "snapshot_at": spot_snapshot_at,
                "snapshot_age_sec": max(0.0, now - spot_snapshot_at) if spot_snapshot_at is not None else None,
                "snapshot_error": spot_snapshot_error,
            },
        }
