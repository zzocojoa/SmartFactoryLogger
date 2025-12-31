import socket
import struct
import time
from datetime import datetime
from typing import Optional, List, Dict
from urllib.request import urlopen

from .base_driver import BasePLCDriver
from ..models.data_model import FactoryData
from .. import config


class RealPLCDriver(BasePLCDriver):
    def __init__(self):
        super().__init__()
        # Extruder (Melsec) Socket
        self.sock_ext: Optional[socket.socket] = None
        self.ext_retry_interval = 1.0
        self.ext_retry_max = 8.0
        self.ext_next_retry = 0.0

        # LS (Temp) Socket
        self.sock_ls: Optional[socket.socket] = None
        self.ls_retry_interval = 1.0
        self.ls_retry_max = 8.0
        self.ls_next_retry = 0.0

        self.timeout = 0.5
        self.spot_timeout = 0.2
        self.last_spot: Optional[float] = None

    def _backoff_ext(self):
        self.ext_next_retry = time.time() + self.ext_retry_interval
        self.ext_retry_interval = min(self.ext_retry_interval * 2, self.ext_retry_max)

    def _backoff_ls(self):
        self.ls_next_retry = time.time() + self.ls_retry_interval
        self.ls_retry_interval = min(self.ls_retry_interval * 2, self.ls_retry_max)

    def connect(self) -> bool:
        """Connect to both PLCs."""
        ok_ext = self._connect_extruder()
        ok_ls = self._connect_ls()
        self.connected = ok_ext or ok_ls
        return self.connected

    def _connect_extruder(self) -> bool:
        now = time.time()
        if now < self.ext_next_retry:
            return False
        try:
            if self.sock_ext:
                try:
                    self.sock_ext.close()
                except Exception:
                    pass
            self.sock_ext = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock_ext.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock_ext.settimeout(self.timeout)
            self.sock_ext.connect((config.EXTRUDER_IP, config.EXTRUDER_PORT))
            self.ext_retry_interval = 1.0
            self.ext_next_retry = 0.0
            print(f"[RealDriver] Connected to Extruder ({config.EXTRUDER_IP})")
            return True
        except Exception as e:
            self.sock_ext = None
            self._backoff_ext()
            print(f"[RealDriver] Extruder Connection Failed: {e}")
            return False

    def _connect_ls(self) -> bool:
        now = time.time()
        if now < self.ls_next_retry:
            return False
        try:
            if self.sock_ls:
                try:
                    self.sock_ls.close()
                except Exception:
                    pass
            self.sock_ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock_ls.settimeout(self.timeout)
            self.sock_ls.connect((config.LS_IP, config.LS_PORT))
            self.ls_retry_interval = 1.0
            self.ls_next_retry = 0.0
            print(f"[RealDriver] Connected to LS PLC ({config.LS_IP})")
            return True
        except Exception as e:
            self.sock_ls = None
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
        if spot_val is None:
            spot_val = self.last_spot if self.last_spot is not None else 0.0
        else:
            self.last_spot = spot_val

        # Update connection status
        self.connected = bool(self.sock_ext or self.sock_ls)

        # 4. Merge & Return
        now = datetime.now()
        return FactoryData(
            Time=now.isoformat(),
            Status="Running" if self.connected else "Offline",

            # From Extruder
            Speed=ext_data.get("Speed", 0.0),
            Press=ext_data.get("Press", 0.0),
            Count=int(ext_data.get("Count", 0)),
            EndPos=ext_data.get("EndPos", 0.0),
            Billet_Length=ext_data.get("Billet", 0.0),
            Temp_F=ext_data.get("Temp_F", 0.0),
            Temp_B=ext_data.get("Temp_B", 0.0),

            # From LS
            Mold1=ls_data.get("Mold1", 0),
            Mold2=ls_data.get("Mold2", 0),
            Mold3=ls_data.get("Mold3", 0),
            Mold4=ls_data.get("Mold4", 0),
            Mold5=ls_data.get("Mold5", 0),
            Mold6=ls_data.get("Mold6", 0),
            Billet_Temp=ls_data.get("Billet_Temp", 0.0),
            At_Temp=ls_data.get("At_Temp", 0.0),
            At_Pre=ls_data.get("At_Pre", 0.0),

            # From SPOT
            Spot=spot_val,
        )

    # --- SPOT Logic ---
    def _read_spot(self) -> Optional[float]:
        try:
            with urlopen(config.SPOT_URL, timeout=self.spot_timeout) as resp:
                raw = resp.read().decode("ascii", errors="ignore").strip()
                if raw:
                    return float(raw)
        except Exception:
            return None
        return None

    # --- Melsec Logic ---
    def _read_extruder(self) -> Dict[str, float]:
        if not self.sock_ext:
            if not self._connect_extruder():
                return {}

        data: Dict[str, float] = {}
        try:
            # Optimized Block Read (Adapted from V1)
            # 1. Press/Temps (D20, 20 words)
            b1 = self._melsec_read("D0020", 20)
            if len(b1) > 14:
                data["Press"] = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]

            # 2. Speed (B1502, 1 word)
            b_spd = self._melsec_read("B1502", 1)
            if b_spd:
                data["Speed"] = b_spd[0] / 10.0

            # 3. Count (D1500, 20 words)
            b3 = self._melsec_read("D1500", 20)
            if len(b3) > 10:
                data["Count"] = b3[10]

            # 4. EndPos (D420, 10 words)
            b2 = self._melsec_read("D0420", 10)
            if len(b2) > 1:
                data["EndPos"] = b2[1] / 10.0

            # 5. Billet (D1900, 20 words)
            b4 = self._melsec_read("D1900", 20)
            if len(b4) > 11:
                data["Billet"] = b4[11]

        except Exception as e:
            print(f"[RealDriver] Extruder Read Error: {e}")
            self.sock_ext = None
            self._backoff_ext()

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
                raise ConnectionResetError("Empty response")

            resp_str = raw.decode("ascii", errors="replace").strip()
            if "OK" not in resp_str:
                return []

            parts = resp_str.split("OK", 1)
            if len(parts) < 2:
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
                return []
            return values
        except Exception as e:
            print(f"[RealDriver] Extruder Read Error: {e}")
            self.sock_ext = None
            self._backoff_ext()
            return []

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
            if values and len(values) == len(config.LS_TARGETS):
                for i, (addr, key) in enumerate(config.LS_TARGETS):
                    val = values[i]
                    if val is not None:
                        if key in ["At_Temp", "At_Pre"]:
                            data[key] = val / 100.0
                        else:
                            data[key] = val

        except Exception as e:
            print(f"[RealDriver] LS Read Error: {e}")
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
