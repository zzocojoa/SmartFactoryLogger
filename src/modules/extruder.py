# modules/extruder.py
import socket
import time
from modules.schemas import ExtruderData

from modules.logger import sys_logger

class ExtruderClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.last_connect_time = 0
        self.base_retry = 1.0
        self.max_retry = 8.0
        self.retry_interval = self.base_retry
        self.timeout = 0.5
        self.merge_blocks = True
        self.max_merge_words = 512
        self.merge_failures = 0
        self.merge_fail_threshold = 3
        self.merge_retry_successes = 300
        self.merge_retry_current = self.merge_retry_successes
        self.merge_retry_growth = 2
        self.merge_retry_pending = False
        self.split_success_count = 0
        self.connect()

    def _reset_backoff(self):
        self.retry_interval = self.base_retry

    def _increase_backoff(self):
        self.retry_interval = min(self.max_retry, max(self.base_retry, self.retry_interval * 2))
        self.last_connect_time = time.time()

    def connect(self):
        now = time.time()
        if now - self.last_connect_time < self.retry_interval: return False
        self.last_connect_time = now
        try:
            if self.sock:
                try: self.sock.close()
                except: pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout) 
            self.sock.connect((self.ip, self.port))
            self._reset_backoff()
            sys_logger.info(f"[Extru] Connected to {self.ip}:{self.port}")
            return True
        except Exception as e:
            self.sock = None
            self._increase_backoff()
            sys_logger.debug(f"[Extru] Connection failed: {e}")
            return False

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None

    def _recv_until(self, terminator=b"\r\n", max_bytes=8192):
        if not self.sock:
            return b""
        data = bytearray()
        while len(data) < max_bytes:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data.extend(chunk)
            if terminator in data:
                break
        return bytes(data)

    def _read_merged(self):
        if not self.merge_blocks:
            return None

        d_main_start = 20
        d_main_end = 421
        d_aux_start = 1500
        d_aux_end = 1911
        d_main_count = d_main_end - d_main_start + 1
        d_aux_count = d_aux_end - d_aux_start + 1

        if d_main_count > self.max_merge_words or d_aux_count > self.max_merge_words:
            return None

        b_main = self._read_block(f"D{d_main_start:04}", d_main_count, min_count=d_main_count)
        b_aux = self._read_block(f"D{d_aux_start:04}", d_aux_count, min_count=d_aux_count)
        b_speed = self._read_block("B1502", 1, min_count=1)

        if not b_main or not b_aux or not b_speed:
            return None

        merged = {
            "Press": b_main[3] / 10.0,
            "Temp_F": b_main[11],
            "Temp_B": b_main[12],
            "EndPos": b_main[401] / 10.0,
            "Speed": b_speed[0] / 10.0,
            "Count": b_aux[10],
            "Billet": b_aux[411],
        }
        return merged

    def _read_block(self, addr_str, count, min_count=None):
        """ 
        주소 문자열(D0020, B1502 등)을 그대로 명령어에 사용 
        명령어: 01 + WRD + 주소 + 개수
        """
        if not self.sock: return []
        
        cmd = f"01WRD{addr_str} {count:02}\r\n".encode()
        
        try:
            self.sock.sendall(cmd)
            response = self._recv_until()
            if not response:
                sys_logger.warning(f"[Extru] Empty response on {addr_str}")
                return []
            resp_str = response.decode("ascii", errors="replace").strip()
            
            if "OK" not in resp_str:
                sys_logger.debug(f"[Extru] Invalid response on {addr_str}: {resp_str}")
                return []

            data_part = resp_str.split("OK")[1]
            values = []
            for i in range(0, len(data_part), 4):
                hex_val = data_part[i:i+4]
                if len(hex_val) == 4:
                    try: values.append(int(hex_val, 16))
                    except: values.append(None)
            if min_count is not None and len(values) < min_count:
                sys_logger.warning(
                    f"[Extru] Incomplete response on {addr_str}: {len(values)}/{min_count}"
                )
                return []
            return values
        except Exception as e:
            sys_logger.error(f"[Extru] IO Error on {addr_str}: {e}")
            self._increase_backoff()
            self.close()
        return []

    def get_data(self):
        data = {"Press": None, "Temp_F": None, "Temp_B": None, "Speed": None, "EndPos": None, "Count": None, "Billet": None}
        if self.sock is None:
            if not self.connect(): return data

        try:
            if self.merge_blocks:
                merged = self._read_merged()
                if merged is not None:
                    data.update(merged)
                    self.merge_failures = 0
                    self.merge_retry_pending = False
                    self.merge_retry_current = self.merge_retry_successes
                    self.split_success_count = 0
                    try:
                        validated = ExtruderData(**data)
                        return validated.dict()
                    except Exception as e:
                        sys_logger.warning(f"[Extru] Validation Warn: {e}")
                        return data
                else:
                    self.merge_failures += 1
                    if self.merge_failures >= self.merge_fail_threshold:
                        self.merge_blocks = False
                        if self.merge_retry_pending:
                            self.merge_retry_current *= self.merge_retry_growth
                        self.merge_retry_pending = False
                        self.merge_failures = 0
                        self.split_success_count = 0
                        sys_logger.warning(
                            f"[Extru] Block merge disabled after {self.merge_fail_threshold} failures. "
                            f"Retry after {self.merge_retry_current} successful split cycles."
                        )

            if self.sock is None:
                return data

            # 1. [D0020~] 압력, 온도 (20개 읽기)
            # D23=idx3(압력), D31=idx11(온도앞), D32=idx12(온도뒤)
            b1 = self._read_block("D0020", 20)
            if len(b1) > 14:
                data["Press"]  = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]
            elif self.sock is None: return data

            # 2. [B1502~] 속도 (B영역 읽기)
            b_speed = self._read_block("B1502", 1)
            if len(b_speed) > 0:
                data["Speed"] = b_speed[0] / 10.0

            # 3. [D0420~] 종료위치
            b2 = self._read_block("D0420", 10)
            if len(b2) > 1: data["EndPos"] = b2[1] / 10.0

            # 4. [D1500~] 카운터
            b3 = self._read_block("D1500", 20)
            if len(b3) > 10: data["Count"] = b3[10]

            # 5. [D1900~] 빌렛길이
            b4 = self._read_block("D1900", 20)
            if len(b4) > 10: data["Billet"] = b4[11]

            if not self.merge_blocks:
                split_ok = self.sock is not None and any(
                    v is not None for v in (
                        data.get("Press"), data.get("Temp_F"), data.get("Temp_B"),
                        data.get("Speed"), data.get("EndPos"), data.get("Count"), data.get("Billet")
                    )
                )
                if split_ok:
                    self.split_success_count += 1
                    if self.split_success_count >= self.merge_retry_current:
                        self.merge_blocks = True
                        self.merge_retry_pending = True
                        self.split_success_count = 0
                        self.merge_failures = 0
                        sys_logger.info(
                            f"[Extru] Block merge retry enabled after {self.merge_retry_current} successful split cycles."
                        )
                else:
                    self.split_success_count = 0

        except Exception as e:
            sys_logger.error(f"[Extru] Data Loop Error: {e}")
            self._increase_backoff()
            self.close()
            
        # Pydantic Validation
        try:
            validated = ExtruderData(**data)
            return validated.dict()
        except Exception as e:
            sys_logger.warning(f"[Extru] Validation Warn: {e}")
            return data
