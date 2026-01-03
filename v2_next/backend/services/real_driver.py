import socket
import struct
import time
from datetime import datetime
from typing import Optional, List, Dict
from urllib.request import urlopen

from .base_driver import BasePLCDriver
from ..models.data_model import FactoryData
from .. import config
from .logic_processor import LogicProcessor
from .observability_service import observability_service


class RealPLCDriver(BasePLCDriver):
    def __init__(self):
        super().__init__()
        # Extruder (Melsec) Socket
        self.sock_ext: Optional[socket.socket] = None
        self.ext_retry_interval = 1.0
        self.ext_retry_max = 8.0
        self.ext_next_retry = 0.0
        self.ext_timeout = 0.5
        self.ext_merge_blocks = True
        self.ext_merge_failures = 0
        self.ext_merge_fail_threshold = 3
        self.ext_merge_retry_successes = 300
        self.ext_merge_retry_current = self.ext_merge_retry_successes
        self.ext_merge_retry_growth = 2
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
        self.ls_retry_interval = 1.0
        self.ls_retry_max = 8.0
        self.ls_next_retry = 0.0
        self.ls_timeout = 0.5
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

        self.spot_timeout = 0.2
        self.last_spot: Optional[float] = None
        self.spot_read_failures = 0
        self.spot_last_error_time: Optional[float] = None
        self.spot_last_success_time: Optional[float] = None
        self.logic = LogicProcessor()

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
            self.sock_ext.settimeout(self.ext_timeout)
            self.sock_ext.connect((config.EXTRUDER_IP, config.EXTRUDER_PORT))
            self.ext_retry_interval = 1.0
            self.ext_next_retry = 0.0
            print(f"[RealDriver] Connected to Extruder ({config.EXTRUDER_IP})")
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
        print("[RealDriver] All Connections Closed.")

    def read_data(self) -> FactoryData:
        # 1. Read Extruder (Melsec ASCII)
        ext_data = self._read_extruder()

        # 2. Read LS (XGT Binary)
        ls_data = self._read_ls()

        # 3. Read SPOT Temp (HTTP)
        spot_val = self._read_spot()
        if spot_val is not None:
            self.last_spot = spot_val

        # Update connection status
        self.connected = bool(self.sock_ext or self.sock_ls)

        # 4. Merge & Return
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

    # --- SPOT Logic ---
    def _read_spot(self) -> Optional[float]:
        try:
            with urlopen(config.SPOT_URL, timeout=self.spot_timeout) as resp:
                raw = resp.read().decode("ascii", errors="ignore").strip()
                if raw:
                    value = float(raw)
                    self._mark_spot_success()
                    return value
        except Exception as exc:
            self._mark_spot_error(str(exc))
            return None
        return None

    # --- Melsec Logic ---
    def _read_extruder(self) -> Dict[str, float]:
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
                merged = self._read_extruder_merged()
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

            # Split reads
            b1 = self._melsec_read("D0020", 20)
            if len(b1) > 14:
                data["Press"] = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]

            b_spd = self._melsec_read("B1502", 1)
            if b_spd:
                data["Speed"] = b_spd[0] / 10.0

            b3 = self._melsec_read("D1500", 20)
            if len(b3) > 10:
                data["Count"] = b3[10]

            b2 = self._melsec_read("D0420", 10)
            if len(b2) > 1:
                data["EndPos"] = b2[1] / 10.0

            b4 = self._melsec_read("D1900", 20)
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
            self.sock_ext = None
            self._backoff_ext()
            self.ext_skip_counter = 5

        return data

    def _recv_until(self, terminator: bytes = b"\r\n", max_bytes: int = 8192) -> bytes:
        if not self.sock_ext:
            return b""
        data = bytearray()
        while len(data) < max_bytes:
            try:
                chunk = self.sock_ext.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data.extend(chunk)
            if terminator in data:
                break
        return bytes(data)

    def _melsec_read(self, addr: str, count: int) -> List[int]:
        if not self.sock_ext:
            return []
        cmd = f"01WRD{addr} {count:02}\r\n".encode()
        try:
            self.sock_ext.sendall(cmd)
            raw = self._recv_until()
            if not raw:
                self.ext_invalid_responses += 1
                raise ConnectionResetError("Empty response")

            resp_str = raw.decode("ascii", errors="replace").strip()
            if "OK" not in resp_str:
                self.ext_invalid_responses += 1
                return []

            parts = resp_str.split("OK", 1)
            if len(parts) < 2:
                self.ext_invalid_responses += 1
                return []

            hex_data = parts[1]
            values: List[int] = []
            for i in range(0, len(hex_data), 4):
                chunk = hex_data[i : i + 4]
                if len(chunk) == 4:
                    try:
                        values.append(int(chunk, 16))
                    except Exception:
                        values.append(0)
            if len(values) < count:
                self.ext_invalid_responses += 1
                return []
            return values
        except Exception as e:
            print(f"[RealDriver] Extruder Read Error: {e}")
            self._mark_ext_error(str(e))
            self.sock_ext = None
            self._backoff_ext()
            self.ext_skip_counter = 5
            return []

    def _read_extruder_merged(self) -> Optional[Dict[str, float]]:
        b1 = self._melsec_read("D0020", 16)
        if not b1:
            return None
        b2 = self._melsec_read("D0420", 6)
        if not b2:
            return None
        b3 = self._melsec_read("D1500", 16)
        if not b3:
            return None
        b4 = self._melsec_read("D1900", 16)
        if not b4:
            return None
        b_spd = self._melsec_read("B1502", 1)
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

    # --- LS Logic ---
    def _read_ls(self) -> Dict[str, float]:
        if not self.sock_ls:
            if not self._connect_ls():
                return {}

        data: Dict[str, float] = {}
        try:
            targets = [t[0] for t in config.LS_TARGETS]
            req = self._ls_create_packet(targets)
            self.sock_ls.sendall(req)

            header = self._ls_recv_exact(20)
            if not header:
                raise ConnectionResetError("No Header")

            body_len = struct.unpack("<H", header[16:18])[0]
            if body_len > 8192:
                raise ValueError("Body too large")

            body = self._ls_recv_exact(body_len)
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

    def _ls_recv_exact(self, size: int) -> Optional[bytes]:
        if not self.sock_ls:
            return None
        data = bytearray()
        while len(data) < size:
            try:
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
            },
            "spot": {
                "last_value": self.last_spot,
                "read_failures": self.spot_read_failures,
                "last_error_time": self.spot_last_error_time,
                "last_success_time": self.spot_last_success_time,
                "timeout_sec": self.spot_timeout,
            },
        }
